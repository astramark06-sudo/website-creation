"""Project-specific release evidence, not a certification or publishing action."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

try:
    from .creator_project import build, read_spec, validate_spec
except ImportError:
    from creator_project import build, read_spec, validate_spec

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


def release_report(spec):
    validate_spec(spec)
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with tempfile.TemporaryDirectory() as tmp:
        report = build(spec, Path(tmp) / "site")
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
    for label in ("Project-specific browser and responsive testing", "Accessibility review",
                  "Performance and security review", "Public deployment verification"):
        gates.append({"name": label, "status": "not-tested", "evidence": "Requires separate evidence for this project."})
    return {
        "version": 1,
        "project_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "pages": report["pages"], "generated_files": report["files"],
        "gates": gates, "warnings": warnings,
        "publication_ready": False,
        "limitations": ["No internet plagiarism search or similarity certification.",
                        "No actual browser, accessibility, performance or public deployment test was run.",
                        "This report never approves or publishes a website."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(release_report(read_spec(args.spec)), indent=2))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
