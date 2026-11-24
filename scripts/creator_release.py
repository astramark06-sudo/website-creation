"""Project-specific release evidence, not a certification or publishing action."""
import argparse
from collections import Counter
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import tempfile

try:
    from .creator_project import build, read_spec, validate_spec, assemble, filename, verify
    from .creator_browser import check_browser, ENGINES, VIEWPORTS
except ImportError:
    from creator_project import build, read_spec, validate_spec, assemble, filename, verify
    from creator_browser import check_browser, ENGINES, VIEWPORTS

PLACEHOLDERS = {
    "my website", "describe your website.", "write an original introduction.",
    "add original content.", "new section", "new page",
    "explain the purpose of your own website in original language.",
    "describe your own offerings or examples using original material.",
    "describe the legitimate action visitors should take.",
    "describe your own purpose and audience in original language.",
    "introduce your own offerings, ideas or examples.",
    "explain the legitimate next step for your visitors.",
}


def release_report(spec, *, engines=(), output=None):
    validate_spec(spec)
    if not isinstance(engines, (list, tuple)) or any(engine not in ENGINES for engine in engines) or len(set(engines)) != len(engines):
        raise ValueError("Select distinct supported browser engines")
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    project_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    files = {name: hashlib.sha256(body.encode("utf-8")).hexdigest()
             for name, body in sorted(assemble(spec).items())}
    browser_reports = []
    # Existing output is verified read-only; otherwise use a disposable build.
    with (tempfile.TemporaryDirectory() if output is None else nullcontext(None)) as tmp:
        if output is None:
            output = Path(tmp) / "site"
            report = build(spec, output)
        else:
            output = Path(output)
            report = verify(spec, output)
        for engine in engines:
            evidence = check_browser(spec, output=output, engine=engine)
            if (evidence["project_sha256"] != project_sha256 or evidence["files"] != files
                    or evidence["browser"] != engine or evidence["status"] not in ("passed", "failed")):
                raise ValueError("Browser evidence does not match the verified project")
            expected = {(filename(page), width) for page in spec["pages"] for width in VIEWPORTS}
            actual = [(entry["page"], entry["width"]) for entry in evidence["results"]]
            if set(actual) != expected or len(actual) != len(expected):
                raise ValueError("Browser evidence has incomplete page and viewport coverage")
            if evidence["status"] == "passed" and (evidence["findings"] or any(
                    not entry["checks"] or any(value is not True for value in entry["checks"].values())
                    for entry in evidence["results"])):
                raise ValueError("Browser evidence contains inconsistent passing checks")
            browser_reports.append(evidence)
    warnings = []
    titles = Counter(p["title"].strip().casefold() for p in spec["pages"])
    if any(count > 1 for count in titles.values()):
        warnings.append("Duplicate page titles: review navigation labels.")
    if spec["title"].strip().casefold() in PLACEHOLDERS or spec["description"].strip().casefold() in PLACEHOLDERS:
        warnings.append("Project title or description contains a known starter placeholder.")
    for page in spec["pages"]:
        slug = page["slug"]
        values = [page["title"], page["intro"]]
        for section in page["sections"]:
            values.extend([section["heading"], section["body"]])
        if any(value.strip().casefold() in PLACEHOLDERS for value in values):
            warnings.append(f"{slug}: known starter placeholder remains.")
        headings = Counter(s["heading"].strip().casefold() for s in page["sections"])
        if any(count > 1 for count in headings.values()):
            warnings.append(f"{slug}: duplicate section headings; review clarity.")
    gates = [
        {"name": "Project schema", "status": "passed", "evidence": "Validated structured specification."},
        {"name": "Build integrity", "status": "passed", "evidence": "Generated files verified against their specification and hashes."},
        {"name": "Basic document structure", "status": "passed", "evidence": "Generated HTML checked for one main heading, document language and viewport metadata."},
        {"name": "Starter content review", "status": "review" if warnings else "passed", "evidence": "Exact starter-placeholder and repeated-heading checks only."},
    ]
    for key, label in (
        ("content_rights_confirmed", "Content rights"),
        ("originality_reviewed", "Originality"),
        ("publish_approved", "Publication approval"),
    ):
        gates.append({"name": label, "status": "declared" if spec["review"][key] else "review",
                      "evidence": "Human declaration only; not independently verified."})
    browser_status = ("not-tested" if not browser_reports else
                      "passed" if all(item["status"] == "passed" for item in browser_reports) else "failed")
    gates.append({"name": "Project-specific browser and responsive testing", "status": browser_status,
                  "evidence": ("Fresh smoke checks: " + ", ".join(engines) + ". Not a complete audit."
                               if engines else "Requires separate evidence for this project.")})
    for label in ("Accessibility review", "Performance and security review", "Public deployment verification"):
        gates.append({"name": label, "status": "not-tested", "evidence": "Requires separate evidence for this project."})
    return {
        "version": 1,
        "project_sha256": project_sha256,
        "files": files,
        "browser_reports": browser_reports,
        "pages": report["pages"], "generated_files": report["files"],
        "gates": gates, "warnings": warnings,
        "publication_ready": False,
        "limitations": ["No internet plagiarism search or similarity certification.",
                        ("Selected local browser smoke checks only; no complete accessibility, performance or security audit."
                         if engines else "No browser check was run."),
                        "No public deployment test was run.",
                        "This report never approves or publishes a website."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--engine", action="append", choices=ENGINES, default=[],
                        help="Run a fresh optional local browser check; repeat for distinct engines")
    parser.add_argument("--output", type=Path, help="Verify an existing generated output directory without changing it")
    parser.add_argument("--require-reviewed", action="store_true",
                        help="Require reviewed input, at least one browser engine and no known starter-content warnings")
    parser.add_argument("--report", type=Path, help="Write new JSON evidence file (never overwrite)")
    args = parser.parse_args()
    try:
        if args.output is not None and args.report is not None:
            if args.report.resolve().is_relative_to(args.output.resolve()):
                raise ValueError("Keep release evidence outside the verified site directory")
        spec = read_spec(args.spec)
        if args.require_reviewed:
            validate_spec(spec, publish=True)
            if not args.engine:
                raise ValueError("Reviewed release gate requires at least one browser engine")
        report = release_report(spec, engines=args.engine, output=args.output)
        data = json.dumps(report, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                stream.write(data)
        print(data, end="")
        if (any(item["status"] != "passed" for item in report["browser_reports"])
                or (args.require_reviewed and report["warnings"])):
            raise SystemExit(1)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
