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
    from .creator_components import validate_component, render_component, component_css, links
    from .creator_search import SEARCH_PANEL, SEARCH_CSS, SEARCH_JS
except ImportError:
    from creator_build import CSS, JS, THEMES, inspect_html
    from creator_design import design_for, design_css
    from creator_components import validate_component, render_component, component_css, links
    from creator_search import SEARCH_PANEL, SEARCH_CSS, SEARCH_JS

MAX_SPEC = 128 * 1024
SLUG = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
RESERVED = {"index", "style", "app", "creator-manifest", "favicon", "search", "con", "prn", "aux", "nul"} | {f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)}
FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#09645e"/><path d="M8 9h16v5H8zm0 9h7v5H8zm11 0h5v5h-5z" fill="white"/></svg>\n'


def read_spec(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_SPEC + 1)
    if len(data) > MAX_SPEC:
        raise ValueError("Project specification exceeds 128 KiB")
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError("Non-finite JSON number")


def require_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text, at most {limit} characters")
    if any(ord(c) < 32 and c not in "\t\n\r" or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f"{label} contains unsupported control characters or Unicode")
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
    if not isinstance(spec["theme"], str) or spec["theme"] not in THEMES:
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
        if page["interaction"] not in ("none", "tasks", "search"):
            raise ValueError("Unsupported interaction")
        sections = page["sections"]
        if not isinstance(sections, list) or not 1 <= len(sections) <= 12:
            raise ValueError("Use 1 to 12 sections on each page")
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("Section must be an object")
            require_text(section.get("heading"), "Section heading", 120)
            require_text(section.get("body"), "Section body", 4000)
            validate_component(section)
    for page in pages:
        for section in page["sections"]:
            if section.get("kind") == "links" and any(target not in seen for _, target in links(section["body"])):
                raise ValueError("Page link points to an unknown page address")
    if pages[0]["slug"] != "home":
        raise ValueError("The first page must have slug home")
    if len(spec_bytes(spec)) > MAX_SPEC:
        raise ValueError("Project specification exceeds 128 KiB")


def spec_bytes(spec):
    return json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


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
    cards = "".join(render_component(section) for section in page["sections"])
    tasks = page["interaction"] == "tasks"
    search = page["interaction"] == "search"
    script = '<script src="app.js" defer></script>' if tasks else '<script src="search.js" defer></script>' if search else ""
    section_id = ' id="page-sections"' if search else ""
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{e(spec["description"])}">
<title>{e(page["title"])} | {e(spec["title"])}</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="stylesheet" href="style.css">{script}</head>
<body><a class="skip" href="#main">Skip to content</a>
<header><div class="wrap nav"><strong>{e(spec["title"])}</strong><nav aria-label="Main navigation">{nav}</nav></div></header>
<main class="wrap" id="main" tabindex="-1"><section class="hero"><h1>{e(page["title"])}</h1><p>{e(page["intro"])}</p></section>
{SEARCH_PANEL if search else ""}<section{section_id} aria-label="Page sections" class="grid">{cards}</section>
{TASKS if tasks else ""}</main>
<footer><div class="wrap">{e(spec["title"])}</div></footer></body></html>
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assemble(spec):
    validate_spec(spec)
    files = {filename(page): render_page(spec, page) for page in spec["pages"]}
    files["style.css"] = CSS.replace("ACCENT", THEMES[spec["theme"]]) + design_css(spec) + component_css(spec)
    if any(p["interaction"] == "tasks" for p in spec["pages"]):
        files["app.js"] = JS
    if any(p["interaction"] == "search" for p in spec["pages"]):
        files["search.js"] = SEARCH_JS
        files["style.css"] += SEARCH_CSS
    files["favicon.svg"] = FAVICON
    files[".nojekyll"] = ""
    return files


def expected_manifest(spec, files):
    return {
        "version": 1, "origin": "original-structured-project",
        "publish_approved": all(spec["review"].values()),
        "backend": None, "network_dependencies": [],
        "files": {name: digest(body.encode("utf-8")) for name, body in sorted(files.items())},
        "limitations": ["Human originality and rights review required",
                        "No server-side persistence or authentication",
                        "Browser accessibility and performance checks are separate"],
    }


def build(spec, out, publish=False):
    validate_spec(spec, publish=publish)
    files = assemble(spec)
    manifest = expected_manifest(spec, files)
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
    # Compare canonical JSON, not Python equality (where True equals 1).
    if spec_bytes(manifest) != spec_bytes(expected_manifest(spec, expected)):
        raise ValueError("Manifest does not match the project")
    for name, body in expected.items():
        data = body.encode("utf-8")
        with (out / name).open("rb") as stream:
            actual = stream.read(len(data) + 1)
        if actual != data:
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
