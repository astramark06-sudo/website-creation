"""Independently authored, bounded section components for original websites."""
import html

KINDS = ("card", "article", "callout", "faq", "list", "steps")

COMPONENT_CSS = """
.component-article, .component-callout, .component-faq, .component-list, .component-steps { min-width: 0; }
.component-article h2, .component-callout h2, .component-faq h2, .component-list h2, .component-steps h2 { overflow-wrap: anywhere; margin-top: 0; }
.grid .component-article { grid-column: 1 / -1; border: 0; background: transparent; padding-inline: 0; }
.component-article p { max-width: 68ch; white-space: pre-line; }
.grid .component-callout { grid-column: 1 / -1; border: 2px solid var(--accent); background: white; padding: clamp(1rem, 3vw, 2rem); }
.component-callout h2 { color: var(--accent); }
.component-faq summary { cursor: pointer; padding: .25rem 0; }
.component-faq summary h2 { display: inline; font-size: 1.15rem; }
.component-faq summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.component-list li, .component-steps li { margin-block: .5rem; overflow-wrap: anywhere; }
"""


def validate_component(section):
    if not isinstance(section, dict):
        raise ValueError("Section must be an object")
    if set(section) not in ({"heading", "body"}, {"heading", "body", "kind"}):
        raise ValueError("Invalid section fields")
    kind = section.get("kind", "card")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Unknown component type")
    if kind in ("list", "steps") and isinstance(section["body"], str):
        items = [line.strip() for line in section["body"].splitlines() if line.strip()]
        if not 1 <= len(items) <= 30:
            raise ValueError("List and steps components require 1 to 30 nonempty lines")


def render_component(section):
    validate_component(section)
    kind = section.get("kind", "card")
    heading = html.escape(section["heading"])
    body = html.escape(section["body"])
    if kind == "card":
        # Preserve exact legacy output for existing specs.
        return f'<article class="card"><h2>{heading}</h2><p>{body}</p></article>'
    if kind == "faq":
        return f'<details class="card component-faq"><summary><h2>{heading}</h2></summary><p>{body}</p></details>'
    if kind in ("list", "steps"):
        tag = "ul" if kind == "list" else "ol"
        items = "".join(f"<li>{html.escape(line.strip())}</li>" for line in section["body"].splitlines() if line.strip())
        return f'<article class="card component-{kind}"><h2>{heading}</h2><{tag}>{items}</{tag}></article>'
    return f'<article class="card component-{kind}"><h2>{heading}</h2><p>{body}</p></article>'


def component_css(spec):
    return COMPONENT_CSS if any(
        section.get("kind", "card") != "card"
        for page in spec["pages"] for section in page["sections"]
    ) else ""
