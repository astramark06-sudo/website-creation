"""Independently authored, bounded section components for original websites."""
import html

KINDS = ("card", "article", "callout", "faq", "list", "steps", "metrics", "timeline", "table")

COMPONENT_CSS = """
.component-article, .component-callout, .component-faq, .component-list, .component-steps,
.component-metrics, .component-timeline, .component-table { min-width: 0; }
.component-article h2, .component-callout h2, .component-faq h2, .component-list h2,
.component-steps h2, .component-metrics h2, .component-timeline h2, .component-table h2 {
  overflow-wrap: anywhere; margin-top: 0;
}
.grid .component-article { grid-column: 1 / -1; border: 0; background: transparent; padding-inline: 0; }
.component-article p { max-width: 68ch; white-space: pre-line; }
.grid .component-callout { grid-column: 1 / -1; border: 2px solid var(--accent); background: white; padding: clamp(1rem, 3vw, 2rem); }
.component-callout h2 { color: var(--accent); }
.component-faq summary { cursor: pointer; padding: .25rem 0; }
.component-faq summary h2 { display: inline; font-size: 1.15rem; }
.component-faq summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.component-list li, .component-steps li, .component-timeline li { margin-block: .5rem; overflow-wrap: anywhere; }
.component-metrics dl { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,10rem),1fr)); gap: 1rem; margin: 0; }
.component-metrics dt { color: var(--muted); font-weight: 600; }
.component-metrics dd { margin: .2rem 0 0; font-size: 1.4rem; font-weight: 700; overflow-wrap: anywhere; }
.component-timeline strong, .component-timeline span { display: block; }
.component-timeline span { color: var(--muted); }
.grid .component-table { grid-column: 1 / -1; }
.component-table .table-wrap { overflow-x: auto; }
.component-table table { width: 100%; border-collapse: collapse; }
.component-table th, .component-table td { border: 1px solid var(--border); padding: .6rem; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.component-table th { background: #f2f5f8; }
.component-caption { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
"""


def lines(body):
    return [line.strip() for line in body.splitlines() if line.strip()]


def pairs(body, label, maximum=20):
    result = []
    for line in lines(body):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"{label} lines must use Label | Value")
        result.append(parts)
    if not 1 <= len(result) <= maximum:
        raise ValueError(f"{label} components require 1 to {maximum} rows")
    return result


def table_rows(body):
    result = []
    for line in lines(body):
        parts = [part.strip() for part in line.split("|")]
        if not 2 <= len(parts) <= 6 or not all(parts):
            raise ValueError("Table rows require 2 to 6 nonempty pipe-separated cells")
        result.append(parts)
    if not 2 <= len(result) <= 31:
        raise ValueError("Tables require one header row and 1 to 30 data rows")
    width = len(result[0])
    if any(len(row) != width for row in result):
        raise ValueError("Every table row must have the same number of cells")
    return result


def validate_component(section):
    if not isinstance(section, dict):
        raise ValueError("Section must be an object")
    if set(section) not in ({"heading", "body"}, {"heading", "body", "kind"}):
        raise ValueError("Invalid section fields")
    kind = section.get("kind", "card")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Unknown component type")
    body = section.get("body")
    if not isinstance(body, str):
        return
    if kind in ("list", "steps"):
        items = lines(body)
        if not 1 <= len(items) <= 30:
            raise ValueError("List and steps components require 1 to 30 nonempty lines")
    elif kind == "metrics":
        pairs(body, "Metrics", 12)
    elif kind == "timeline":
        pairs(body, "Timeline", 20)
    elif kind == "table":
        table_rows(body)


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
        items = "".join(f"<li>{html.escape(line)}</li>" for line in lines(section["body"]))
        return f'<article class="card component-{kind}"><h2>{heading}</h2><{tag}>{items}</{tag}></article>'
    if kind == "metrics":
        values = "".join(
            f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"
            for label, value in pairs(section["body"], "Metrics", 12)
        )
        return f'<article class="card component-metrics"><h2>{heading}</h2><dl>{values}</dl></article>'
    if kind == "timeline":
        items = "".join(
            f"<li><strong>{html.escape(label)}</strong><span>{html.escape(value)}</span></li>"
            for label, value in pairs(section["body"], "Timeline", 20)
        )
        return f'<article class="card component-timeline"><h2>{heading}</h2><ol>{items}</ol></article>'
    if kind == "table":
        rows = table_rows(section["body"])
        head = "".join(f'<th scope="col">{html.escape(cell)}</th>' for cell in rows[0])
        data = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in rows[1:])
        return (f'<article class="card component-table"><h2>{heading}</h2><div class="table-wrap">'
                f'<table><caption class="component-caption">{heading}</caption><thead><tr>{head}</tr></thead>'
                f'<tbody>{data}</tbody></table></div></article>')
    return f'<article class="card component-{kind}"><h2>{heading}</h2><p>{body}</p></article>'


def component_css(spec):
    return COMPONENT_CSS if any(
        section.get("kind", "card") != "card"
        for page in spec["pages"] for section in page["sections"]
    ) else ""
