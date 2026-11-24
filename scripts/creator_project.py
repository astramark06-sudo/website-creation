"""Build original multi-page projects and validate publishable static output.

Only local, structured input. No remote retrieval, arbitrary HTML, or AI API.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re

try:
    from .creator_build import CSS, JS, THEMES, inspect_html
    from .creator_design import design_for, design_css
except ImportError:
    from creator_build import CSS, JS, THEMES, inspect_html
    from creator_design import design_for, design_css

MAX_SPEC = 128 * 1024
SLUG = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
RESERVED = {"index", "style", "app", "creator-manifest"}


def read_spec(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_SPEC + 1)
    if len(data) > MAX_SPEC:
        raise ValueError("Project specification exceeds 128 KiB")
    return json.loads(data.decode("utf-8"))


def require_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text, at most {limit} characters")
    return value.strip()


def exact_keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) != set(allowed):
        raise ValueError(f"Invalid {label} fields")


def validate_spec(spec, publish=False):
    fields = {"version", "title", "description", "theme", "pages", "review"}
    if isinstance(spec, dict) and "design" in spec:
        fields.add("design")
    exact_keys(spec, fields, "project")
    design_for(spec)
    if type(spec["version"]) is not int or spec["version"] != 1:
        raise ValueError("Unsupported specification version")
    require_text(spec["title"], "Title", 120)
    require_text(spec["description"], "Description", 1000)
    if spec["theme"] not in THEMES:
        raise ValueError("Unknown theme")
    review = spec["review"]
    exact_keys(review, {"content_rights_confirmed", "originality_reviewed", "publish_approved"}, "review")
    if any(type(v) is not bool for v in review.values()):
        raise ValueError("Review fields must be booleans")
    if publish and not all(review.values()):
        raise ValueError("Publishing requires explicit content rights, originality and release approval")
    pages = spec["pages"]
    if not isinstance(pages, list) or not 1 <= len(pages) <= 20:
        raise ValueError("Use 1 to 20 pages")
    seen = set()
    for page in pages:
        exact_keys(page, {"slug", "title", "intro", "sections", "interaction"}, "page")
        slug = page["slug"]
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or slug in RESERVED or slug in seen:
            raise ValueError("Invalid, reserved or duplicate page slug")
        seen.add(slug)
        require_text(page["title"], "Page title", 120)
        require_text(page["intro"], "Page introduction", 1000)
        if page["interaction"] not in ("none", "tasks"):
            raise ValueError("Unsupported interaction")
        sections = page["sections"]
        if not isinstance(sections, list) or not 1 <= len(sections) <= 12:
            raise ValueError("Use 1 to 12 sections on each page")
        for section in sections:
            exact_keys(section, {"heading", "body"}, "section")
            require_text(section["heading"], "Section heading", 120)
            require_text(section["body"], "Section body", 4000)
    if pages[0]["slug"] != "home":
        raise ValueError("The first page must have slug home")


def filename(page):
    return "index.html" if page["slug"] == "home" else page["slug"] + ".html"


TASKS = """<section id="content" class="card" aria-labelledby="tasks-heading">
<h2 id="tasks-heading">Task workspace</h2>
<p>Data stays in this browser when storage is available. Do not enter sensitive information.</p>
<form id="task-form"><label for="task-title">New task</label>
<input id="task-title" required maxlength="160" autocomplete="off">
<button type="submit">Add task</button></form>
<p id="status" role="status" aria-live="polite"></p><ul id="tasks"></ul>
<noscript>Enable JavaScript to use this task workspace.</noscript></section>"""


def render_page(spec, page):
    e = html.escape
    nav_items = []
    for item in spec["pages"]:
        current = ' aria-current="page"' if item["slug"] == page["slug"] else ""
        nav_items.append(f'<a href="{filename(item)}"{current}>{e(item["title"])}</a>')
    nav = "".join(nav_items)
    cards = "".join(f'<article class="card"><h2>{e(s["heading"])}</h2><p>{e(s["body"])}</p></article>'
                    for s in page["sections"])
    tasks = page["interaction"] == "tasks"
    script = '<script src="app.js" defer></script>' if tasks else ""
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(spec["description"])}">
<title>{e(page["title"])} | {e(spec["title"])}</title>
<link rel="stylesheet" href="style.css">{script}</head>
<body><a class="skip" href="#main">Skip to content</a>
<header><div class="wrap nav"><strong>{e(spec["title"])}</strong><nav aria-label="Main navigation">{nav}</nav></div></header>
<main class="wrap" id="main"><section class="hero"><h1>{e(page["title"])}</h1><p>{e(page["intro"])}</p></section>
<section aria-label="Page sections" class="grid">{cards}</section>
{TASKS if tasks else ""}</main>
<footer><div class="wrap">{e(spec["title"])}</div></footer></body></html>
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assemble(spec):
    validate_spec(spec)
    files = {filename(page): render_page(spec, page) for page in spec["pages"]}
    files["style.css"] = CSS.replace("ACCENT", THEMES[spec["theme"]]) + design_css(spec)
    if any(p["interaction"] == "tasks" for p in spec["pages"]):
        files["app.js"] = JS
    files[".nojekyll"] = ""
    return files


def build(spec, out, publish=False):
    validate_spec(spec, publish=publish)
    files = assemble(spec)
    manifest = {
        "version": 1, "origin": "original-structured-project",
        "publish_approved": all(spec["review"].values()),
        "backend": None, "network_dependencies": [],
        "files": {name: digest(body.encode("utf-8")) for name, body in sorted(files.items())},
        "limitations": ["Human originality and rights review required",
                        "No server-side persistence or authentication",
                        "Browser accessibility and performance checks are separate"],
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (out / name).write_bytes(body.encode("utf-8"))
    (out / "creator-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return verify(spec, out, publish=publish)


def verify(spec, out, publish=False):
    validate_spec(spec, publish=publish)
    expected = assemble(spec)
    if out.is_symlink() or not out.is_dir():
        raise ValueError("Output must be a real directory")
    children = list(out.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in children):
        raise ValueError("Unexpected directory or symbolic link in output")
    if {p.name for p in children} != set(expected) | {"creator-manifest.json"}:
        raise ValueError("Unexpected or missing generated files")
    manifest = read_spec(out / "creator-manifest.json")
    hashes = {name: digest(body.encode("utf-8")) for name, body in sorted(expected.items())}
    if manifest.get("files") != hashes or manifest.get("origin") != "original-structured-project":
        raise ValueError("Manifest does not match the project")
    if manifest.get("publish_approved") is not all(spec["review"].values()):
        raise ValueError("Manifest approval does not match the project")
    for name, body in expected.items():
        if (out / name).read_bytes() != body.encode("utf-8"):
            raise ValueError("Generated file differs from original build: " + name)
        if name.endswith(".html"):
            report = inspect_html(body)
            if report["heading_levels"].count(1) != 1 or not report["viewport_present"] or not report["language_present"]:
                raise ValueError("Missing required page structure: " + name)
    return {"status": "passed", "pages": len(spec["pages"]), "files": len(expected),
            "publish_approved": manifest["publish_approved"], "browser_tested": False,
            "deployment_confirmed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        spec = read_spec(args.spec)
        operation = build if args.command == "build" else verify
        print(json.dumps(operation(spec, args.output, publish=args.publish), indent=2))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
