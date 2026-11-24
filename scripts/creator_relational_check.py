"""Verify a freshly generated relational application with isolated synthetic data."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

try:
    from .creator_relational_export import export_relational
    from .creator_relational import read_schema, validate_schema
except ImportError:
    from creator_relational_export import export_relational
    from creator_relational import read_schema, validate_schema

ENGINES = ("chromium", "firefox", "webkit")
NAMES = {"server.py", "creator_relational.py", "index.html", "app.js",
         "style.css", "config.json", "README.md", ".gitignore"}
WORKER = Path(__file__).with_name("relational_check_worker.py")


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def check_relational(title, description, schema, engine="chromium"):
    """Run only the current trusted generator's output; never accept an executable ZIP."""
    if engine not in ENGINES:
        raise ValueError("Unknown browser engine")
    schema = validate_schema(schema)
    bundle = export_relational(title, description, schema)
    with tempfile.TemporaryDirectory(prefix="creator-relational-audit-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            if set(archive.namelist()) != NAMES or len(archive.namelist()) != len(NAMES):
                raise ValueError("Unexpected generated bundle")
            hashes = {}
            for name in sorted(NAMES):
                content = archive.read(name)
                hashes[name] = fingerprint(content)
                (root / name).write_bytes(content)
        (root / "audit_worker.py").write_bytes(WORKER.read_bytes())
        report = {"version": 1, "engine": engine, "files": hashes,
                  "project_sha256": hashes["config.json"], "status": "failed",
                  "scope": "fresh local export using synthetic records",
                  "limitations": ["Does not inspect existing user databases",
                                  "Not an accessibility, security or performance certification",
                                  "No public deployment or production authentication verified"]}
        try:
            proc = subprocess.run(
                [sys.executable, "-E", "-s", str(root / "audit_worker.py"), engine],
                cwd=root, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120, check=False,
            )
            if proc.returncode == 0:
                result = json.loads(proc.stdout)
                if result.get("status") != "passed":
                    raise ValueError("Worker did not report a passing result")
                report.update(result)
            else:
                report["diagnostic"] = (proc.stderr.strip() or "Browser worker failed")[-2500:]
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            report["diagnostic"] = str(exc)[:1000]
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
        report = check_relational(args.title, args.description, read_schema(args.schema), args.engine)
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
