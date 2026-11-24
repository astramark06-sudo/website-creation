"""Check a downloaded draft and its evidence offline, without browser execution."""
import argparse
import json
from pathlib import Path

try:
    from .creator_bundle import MAX_ARCHIVE, read_verified_bundle, parse_json
    from .creator_project import filename, spec_bytes
    from .creator_release import release_report
    from .creator_browser import ENGINES, VIEWPORTS
except ImportError:
    from creator_bundle import MAX_ARCHIVE, read_verified_bundle, parse_json
    from creator_project import filename, spec_bytes
    from creator_release import release_report
    from creator_browser import ENGINES, VIEWPORTS

MAX_REPORT = 2 * 1024 * 1024
BASE_CHECKS = frozenset({
    "response", "heading", "landmark", "navigation", "no_horizontal_overflow",
    "stylesheet_loaded", "keyboard_skip_link", "skip_target_focus", "unique_ids",
    "labeled_form_controls", "meaningful_document_metadata", "named_buttons_and_links",
    "faq_disclosures", "page_links", "navigation_click", "no_unexpected_requests",
    "no_browser_errors",
})
INTERACTION_CHECKS = {
    "none": frozenset(),
    "tasks": frozenset({"task_create", "task_complete", "task_persistence", "task_remove"}),
    "search": frozenset({"search_initial", "search_positive_result", "search_empty_result", "search_reset"}),
}


def bounded_file(path, limit):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected a regular preflight artifact file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError("Preflight artifact exceeds its size limit or is empty")
    return data


def verify_browser_claims(spec, bundle, reports):
    if not isinstance(reports, list) or not 1 <= len(reports) <= len(ENGINES):
        raise ValueError("Missing or excessive browser evidence")
    coverage = {(filename(page), width): BASE_CHECKS | INTERACTION_CHECKS[page["interaction"]]
                for page in spec["pages"] for width in VIEWPORTS}
    engines = []
    for report in reports:
        if (not isinstance(report, dict) or set(report) != {
                "version", "status", "project_sha256", "files", "browser",
                "browser_version", "viewports", "results", "findings", "limitations"}
                or type(report["version"]) is not int or report["version"] != 1
                or report["status"] != "passed" or report["findings"] != []
                or report["project_sha256"] != bundle["project_sha256"]
                or report["files"] != bundle["files"]
                or report["browser"] not in ENGINES or report["browser"] in engines
                or not isinstance(report["browser_version"], str)
                or not report["browser_version"].strip()
                or len(report["browser_version"]) > 120
                or spec_bytes(report["viewports"]) != spec_bytes(list(VIEWPORTS))
                or not isinstance(report["limitations"], list)
                or not report["limitations"]
                or any(not isinstance(item, str) or not item.strip() for item in report["limitations"])):
            raise ValueError("Browser claim does not match the verified draft")
        rows = report["results"]
        if not isinstance(rows, list) or len(rows) != len(coverage):
            raise ValueError("Incomplete browser page and viewport coverage")
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"page", "width", "checks", "diagnostics"}
                    or not isinstance(row["page"], str) or type(row["width"]) is not int
                    or row["diagnostics"] != []):
                raise ValueError("Invalid passing browser result")
            key = row["page"], row["width"]
            if (key not in coverage or key in seen or not isinstance(row["checks"], dict)
                    or set(row["checks"]) != coverage[key]
                    or any(value is not True for value in row["checks"].values())):
                raise ValueError("Missing, duplicate or inconsistent browser checks")
            seen.add(key)
        engines.append(report["browser"])
    return engines


def check_preflight(directory, *, required_engines=()):
    """Validate bytes, current generator output and report consistency only."""
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Select a real preflight directory")
    try:
        archive = bounded_file(root / "creator-project.zip", MAX_ARCHIVE)
        report = parse_json(bounded_file(root / "preflight-report.json", MAX_REPORT))
        spec, bundle = read_verified_bundle(archive)
        if (not isinstance(report, dict) or set(report) != {
                "version", "status", "scope", "publication_ready", "bundle", "release", "bundle_available"}
                or type(report["version"]) is not int or report["version"] != 1
                or report["status"] != "passed" or report["scope"] != "verified unapproved static draft"
                or report["publication_ready"] is not False or report["bundle_available"] is not True
                or spec_bytes(report["bundle"]) != spec_bytes(bundle)):
            raise ValueError("Preflight evidence does not match the verified archive")
        release = report["release"]
        if not isinstance(release, dict):
            raise ValueError("Missing release evidence")
        engines = verify_browser_claims(spec, bundle, release["browser_reports"])
        if required_engines and set(required_engines) != set(engines):
            raise ValueError("Reported engines do not match required coverage")
        # Recompute all static gates. Only the historical browser claims are
        # supplied by the downloaded report; they are not rerun or authenticated.
        expected = release_report(spec)
        expected["browser_reports"] = release["browser_reports"]
        gate = next(g for g in expected["gates"] if g["name"] == "Project-specific browser and responsive testing")
        gate["status"] = "passed"
        gate["evidence"] = "Fresh smoke checks: " + ", ".join(engines) + ". Not a complete audit."
        expected["limitations"][1] = "Selected local browser smoke checks only; no complete accessibility, performance or security audit."
        if spec_bytes(expected) != spec_bytes(release):
            raise ValueError("Release summary differs from the verified draft")
    except (TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise ValueError("Invalid preflight evidence") from exc
    return {
        "version": 1, "status": "passed", "archive_sha256": bundle["archive_sha256"],
        "project_sha256": bundle["project_sha256"], "pages": bundle["pages"],
        "reported_engines": engines, "browser_tests_rerun": False,
        "report_authenticity_verified": False, "publication_ready": False,
        "limitations": ["Checks current generator bytes and internal evidence consistency only.",
                        "Browser results are historical claims, not proof of actual execution or authenticity.",
                        "No extraction, browser execution, publication or certification."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--engine", action="append", choices=ENGINES, default=[],
                        help="Require this exact set of reported engines")
    args = parser.parse_args()
    try:
        if len(set(args.engine)) != len(args.engine):
            raise ValueError("Select distinct required engines")
        report = check_preflight(args.directory, required_engines=args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
