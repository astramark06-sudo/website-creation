"""Generate original websites and inspect authorized, locally saved HTML.

No network calls, third-party asset copying, or execution of inspected HTML.
"""
from __future__ import annotations

import argparse
from collections import Counter
import html
from html.parser import HTMLParser
import json
from pathlib import Path

MAX_HTML_BYTES = 2 * 1024 * 1024
MODES = ("landing", "portfolio", "documentation", "task-dashboard")
THEMES = {"blue": "#164a9b", "teal": "#09645e", "plum": "#643a85"}


class StructureParser(HTMLParser):
    """Report structural metadata without retaining text, URLs or field values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = Counter()
        self.heading_levels = []
        self.images_without_alt = 0
        self.language_present = False
        self.viewport_present = False
        self.external_scripts = 0
        self.form_controls = Counter()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags[tag] += 1
        if tag == "html":
            self.language_present |= bool(attrs.get("lang"))
        if tag == "meta" and (attrs.get("name") or "").lower() == "viewport":
            self.viewport_present = True
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if len(self.heading_levels) < 200:
                self.heading_levels.append(int(tag[1]))
        if tag == "img" and "alt" not in attrs:
            self.images_without_alt += 1
        if tag == "script" and "src" in attrs:
            self.external_scripts += 1
        if tag in {"input", "button", "select", "textarea"}:
            self.form_controls[tag] += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def inspect_html(source: str) -> dict:
    if len(source.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("HTML exceeds the 2 MiB analysis limit")
    parser = StructureParser()
    parser.feed(source)
    parser.close()
    return {
        "mode": "static-html-structure",
        "elements": dict(sorted(parser.tags.items())),
        "heading_levels": parser.heading_levels,
        "language_present": parser.language_present,
        "viewport_present": parser.viewport_present,
        "images_without_alt_attribute": parser.images_without_alt,
        "script_elements_with_src": parser.external_scripts,
        "form_controls": dict(parser.form_controls),
        "limits": [
            "No browser rendering or computed styles",
            "No network requests or JavaScript execution",
            "No source text, URL, form value or asset reproduction",
            "Does not recover backend logic or prove accessibility",
        ],
    }


def inspect_file(path: Path) -> dict:
    with path.open("rb") as stream:
        data = stream.read(MAX_HTML_BYTES + 1)
    if len(data) > MAX_HTML_BYTES:
        raise ValueError("HTML exceeds the 2 MiB analysis limit")
    return inspect_html(data.decode("utf-8-sig"))


CSS = """* { box-sizing: border-box; }
:root { color-scheme: light; --accent: ACCENT; --ink: #182332; --muted: #526275; --border: #d7dfe8; }
body { margin: 0; color: var(--ink); background: #f7f9fc; font: 1rem/1.6 system-ui, sans-serif; }
a { color: var(--accent); }
a:focus-visible, button:focus-visible, input:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.skip { position: absolute; left: 1rem; top: -5rem; background: white; padding: .5rem; z-index: 2; }
.skip:focus { top: 1rem; }
header, footer { background: white; border-block: 1px solid var(--border); }
.wrap { max-width: 68rem; width: calc(100% - 2rem); margin-inline: auto; }
.nav { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; padding-block: 1rem; }
nav { display: flex; flex-wrap: wrap; gap: 1rem; }
nav a { text-decoration: underline; }
main { padding-block: 3rem; }
.hero { max-width: 48rem; margin-bottom: 3rem; }
h1 { font-size: clamp(2rem, 5vw, 3.8rem); line-height: 1.12; letter-spacing: -.035em; overflow-wrap: anywhere; }
h2 { line-height: 1.25; }
p { overflow-wrap: anywhere; }
.eyebrow { color: var(--accent); font-weight: 700; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: 1rem; }
.card { background: white; border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; }
.button, button { display: inline-block; background: var(--accent); color: white; border: 0; border-radius: .6rem; font: inherit; padding: .65rem 1rem; cursor: pointer; text-decoration: none; }
input { font: inherit; width: 100%; max-width: 28rem; padding: .65rem; border: 1px solid #718096; border-radius: .5rem; }
form { display: flex; flex-wrap: wrap; gap: .75rem; align-items: center; }
form label { width: 100%; font-weight: 600; }
li.task { display: flex; flex-wrap: wrap; gap: .75rem; align-items: center; padding-block: .5rem; }
li.task span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.done { text-decoration: line-through; }
footer .wrap { padding-block: 1rem; color: var(--muted); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
"""

JS = """'use strict';
const form = document.querySelector('#task-form');
const list = document.querySelector('#tasks');
const input = document.querySelector('#task-title');
const status = document.querySelector('#status');
const key = 'original-creator-task-dashboard-v1:' + location.pathname;
let tasks = [];
let persistent = true;
try {
  const stored = JSON.parse(localStorage.getItem(key) || '[]');
  if (Array.isArray(stored)) {
    tasks = stored.filter(t => t && typeof t.title === 'string' &&
      typeof t.done === 'boolean').slice(0, 200).map(t => ({title: t.title.slice(0, 160), done: t.done}));
  }
} catch (_) { persistent = false; }
function save() {
  try { localStorage.setItem(key, JSON.stringify(tasks)); }
  catch (_) { persistent = false; }
}
function render() {
  list.replaceChildren();
  tasks.forEach((task, index) => {
    const row = document.createElement('li');
    row.className = 'task';
    const text = document.createElement('span');
    text.textContent = task.title;
    if (task.done) text.className = 'done';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.textContent = task.done ? 'Undo' : 'Complete';
    toggle.setAttribute('aria-label', toggle.textContent + ': ' + task.title);
    toggle.addEventListener('click', () => { tasks[index].done = !task.done; save(); render(); list.querySelectorAll('button')[index * 2]?.focus(); });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', 'Remove: ' + task.title);
    remove.addEventListener('click', () => { tasks.splice(index, 1); save(); render(); input.focus(); });
    row.append(text, toggle, remove);
    list.append(row);
  });
  status.textContent = tasks.length + ' tasks, ' + tasks.filter(t => t.done).length + ' completed.' +
    (persistent ? '' : ' Local storage unavailable; changes last only for this session.');
}
form.addEventListener('submit', event => {
  event.preventDefault();
  const title = input.value.trim();
  if (!title) return;
  if (tasks.length >= 200) { status.textContent = 'Task limit reached. Remove a task first.'; return; }
  tasks.push({title: title.slice(0, 160), done: false});
  input.value = '';
  save();
  render();
  input.focus();
});
render();
"""

SECTIONS = {
    "landing": [("What we offer", "Describe your primary service or product."),
                ("How it works", "Explain the steps a visitor should take."),
                ("Why choose us", "Add accurate, verifiable benefits.")],
    "portfolio": [("Selected work", "Describe a project and its outcome."),
                  ("Experience", "Add your relevant skills and experience."),
                  ("About", "Introduce your work in your own words.")],
    "documentation": [("Getting started", "Describe the first steps."),
                      ("Guides", "Write instructions for common tasks."),
                      ("Reference", "Document interfaces and options.")],
}


def build_site(output: Path, title: str, description: str, mode: str, theme: str) -> list[str]:
    if mode not in MODES or theme not in THEMES:
        raise ValueError("Unknown site mode or theme")
    if not title.strip() or not description.strip():
        raise ValueError("Title and description are required")
    if len(title) > 120 or len(description) > 1000:
        raise ValueError("Title or description is too long")
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    dynamic = mode == "task-dashboard"
    if dynamic:
        content = """<section id="content" class="card" aria-labelledby="tasks-heading">
<h2 id="tasks-heading">Your tasks</h2>
<p>Tasks are stored in this browser when local storage is available. Do not enter sensitive information.</p>
<form id="task-form"><label for="task-title">New task</label>
<input id="task-title" required maxlength="160" autocomplete="off">
<button type="submit">Add task</button></form>
<p id="status" role="status" aria-live="polite"></p><ul id="tasks"></ul>
<noscript>Enable JavaScript to use the task list.</noscript></section>"""
    else:
        cards = "".join(f'<article class="card"><h2>{heading}</h2><p>{text}</p></article>'
                        for heading, text in SECTIONS[mode])
        content = f'<section id="content" aria-label="Website sections" class="grid">{cards}</section>'
    script = '<script src="app.js" defer></script>' if dynamic else ""
    page = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{safe_description}">
<title>{safe_title}</title><link rel="stylesheet" href="style.css">{script}</head>
<body><a class="skip" href="#main">Skip to content</a>
<header><div class="wrap nav"><strong>{safe_title}</strong>
<nav aria-label="Main navigation"><a href="#main">Home</a><a href="#content">Explore</a></nav></div></header>
<main id="main" class="wrap"><section class="hero"><p class="eyebrow">{"Workspace" if dynamic else "Welcome"}</p>
<h1>{safe_title}</h1><p>{safe_description}</p><a class="button" href="#content">{"Open tasks" if dynamic else "Explore"}</a></section>
{content}</main><footer><div class="wrap">{safe_title}</div></footer></body></html>
"""
    files = {"index.html": page, "style.css": CSS.replace("ACCENT", THEMES[theme])}
    if dynamic:
        files["app.js"] = JS
    files["creator-manifest.json"] = json.dumps({
        "mode": mode, "theme": theme, "origin": "original-creator-template",
        "network_dependencies": [], "backend": None,
        "persistence": "browser-local-storage" if dynamic else "none",
        "content_status": "starter; review and replace placeholders",
    }, indent=2) + "\n"
    # Refuse to overwrite an existing site, even an empty directory.
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_text(body, encoding="utf-8")
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect authorized local HTML only")
    inspect.add_argument("file", type=Path)
    build = commands.add_parser("build", help="Generate an original website in a new directory")
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--title", required=True)
    build.add_argument("--description", required=True)
    build.add_argument("--mode", required=True, choices=MODES)
    build.add_argument("--theme", default="teal", choices=THEMES)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_file(args.file)
        else:
            result = {"files": build_site(args.output, args.title, args.description, args.mode, args.theme)}
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
