"""Verify a fresh authenticated staging export without accessing existing data."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import zipfile

try:
    from .creator_authenticated_export import export_authenticated, SOURCE_FILES
    from .creator_relational import read_schema, validate_schema
except ImportError:
    from creator_authenticated_export import export_authenticated, SOURCE_FILES
    from creator_relational import read_schema, validate_schema

ENGINES = ("chromium", "firefox", "webkit")
WORKER = Path(__file__).with_name("authenticated_check_worker.py")
NAMES = set(SOURCE_FILES) | {"scripts/__init__.py", "workspace-config.json", ".gitignore", "README.md", "bundle-manifest.json"}


def check_authenticated(title, description, schema, engine="chromium"):
    if engine not in ENGINES:
        raise ValueError("Unknown browser engine")
    bundle = export_authenticated(title, description, validate_schema(schema))
    report = {
        "version": 1, "profile": "authenticated-local-staging", "engine": engine,
        "status": "failed", "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "scope": "fresh generated bundle with temporary synthetic accounts and records",
        "public_deployment": False,
        "limitations": ["No existing databases or real accounts inspected",
                        "No public hosting, TLS, rate limiting or production identity assurance verified",
                        "Not an accessibility, performance or security certification"],
    }
    with tempfile.TemporaryDirectory(prefix="creator-auth-check-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            if set(archive.namelist()) != NAMES or len(archive.namelist()) != len(NAMES):
                raise ValueError("Unexpected generated bundle")
            manifest = json.loads(archive.read("bundle-manifest.json"))
            hashes = manifest["files"]
            if manifest["public_deployment"] is not False or set(hashes) != NAMES - {"bundle-manifest.json"}:
                raise ValueError("Unexpected bundle manifest")
            for name in sorted(NAMES):
                data = archive.read(name)
                if name in hashes and hashlib.sha256(data).hexdigest() != hashes[name]:
                    raise ValueError("Generated bundle fingerprint mismatch")
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            report["files"] = hashes
        (root / "audit_worker.py").write_bytes(WORKER.read_bytes())
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.update(CREATOR_STAGING_SECRET=secrets.token_urlsafe(48),
                   CREATOR_STAGING_DB=str(root / "audit.sqlite3"),
                   DJANGO_SETTINGS_MODULE="staging_auth.settings")
        try:
            proc = subprocess.run(
                [sys.executable, "-E", "-s", str(root / "audit_worker.py"), engine],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=150, check=False,
            )
            # Only accept the worker's small structured result; never surface raw
            # process logs, which could contain temporary authentication details.
            if len(proc.stdout) <= 32768:
                result = json.loads(proc.stdout)
                if not isinstance(result, dict):
                    raise ValueError("Invalid worker result")
                if proc.returncode == 0 and result.get("status") == "passed":
                    report.update({key: result[key] for key in ("status", "checks", "tables", "browser_version")})
                else:
                    report["diagnostic"] = str(result.get("diagnostic", "Worker failed"))[:300]
            else:
                report["diagnostic"] = "Unexpected worker result size"
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            report["diagnostic"] = "Worker unavailable, invalid result or execution limit reached"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--engine", choices=ENGINES, default="chromium")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = check_authenticated(args.title, args.description, read_schema(args.schema), args.engine)
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return 0 if report["status"] == "passed" else 1
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
