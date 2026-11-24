"""Create a verified portable draft and matching project evidence; never deploy."""
import argparse
import json
from pathlib import Path

try:
    from .creator_project import read_spec
    from .creator_studio import export_zip, draft_spec
    from .creator_bundle import read_verified_bundle
    from .creator_release import release_report
    from .creator_browser import ENGINES
except ImportError:
    from creator_project import read_spec
    from creator_studio import export_zip, draft_spec
    from creator_bundle import read_verified_bundle
    from creator_release import release_report
    from creator_browser import ENGINES


def prepare_draft(spec, output, *, engines):
    """Create a new evidence directory. Failed browser checks retain only evidence."""
    if not isinstance(engines, (list, tuple)) or not engines:
        raise ValueError("Select at least one browser engine")
    if any(engine not in ENGINES for engine in engines) or len(set(engines)) != len(engines):
        raise ValueError("Select distinct supported browser engines")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new preflight output directory")
    draft = draft_spec(spec)
    archive = export_zip(draft)
    reopened, bundle = read_verified_bundle(archive)
    if reopened != draft:
        raise ValueError("Verified bundle did not preserve the draft")
    release = release_report(reopened, engines=engines)
    if (release["project_sha256"] != bundle["project_sha256"]
            or release["files"] != bundle["files"]
            or [item["browser"] for item in release["browser_reports"]] != list(engines)):
        raise ValueError("Release evidence does not match the portable draft")
    passed = all(item["status"] == "passed" for item in release["browser_reports"])
    report = {
        "version": 1, "status": "passed" if passed else "failed",
        "scope": "verified unapproved static draft",
        "publication_ready": False,
        "bundle": bundle, "release": release,
        "bundle_available": passed,
    }
    output.mkdir(exist_ok=False)
    # Write the archive before claiming it is available. The CI artifact step
    # requires a completed evidence report; incomplete output is not uploaded.
    if passed:
        (output / "creator-project.zip").write_bytes(archive)
    (output / "preflight-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", action="append", choices=ENGINES, required=True)
    args = parser.parse_args()
    try:
        report = prepare_draft(read_spec(args.spec), args.output, engines=args.engine)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print("Draft preflight " + report["status"] + "; no site published.")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
