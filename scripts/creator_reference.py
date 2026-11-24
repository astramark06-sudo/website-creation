"""Convert structural observations into independent project planning suggestions.

No source content, scripts, URLs, styling or assets are reproduced.
"""
from __future__ import annotations

try:
    from .creator_build import inspect_html
    from .creator_project import require_text, validate_spec
except ImportError:
    from creator_build import inspect_html
    from creator_project import require_text, validate_spec

REFERENCE_LIMIT = 64 * 1024
MAX_REFERENCE_PAGES = 5
STANDARD_TAGS = frozenset("header nav main section article aside footer h1 h2 h3 h4 h5 h6 p img picture figure figcaption a button form input select textarea table th td ul ol li details summary video audio script".split())


def reference_plan(source, title, objective, authorized):
    if authorized is not True:
        raise ValueError("Confirm permission to analyze the reference")
    if not isinstance(source, str) or len(source.encode("utf-8")) > REFERENCE_LIMIT:
        raise ValueError("Reference exceeds 64 KiB")
    title = require_text(title, "Website name", 120)
    objective = require_text(objective, "Objective", 1000)
    raw = inspect_html(source)
    counts = {tag: count for tag, count in raw["elements"].items() if tag in STANDARD_TAGS}
    suggestions = [
        "Write a distinct visual identity and original content.",
        "Use the user's objective as the source of truth.",
    ]
    sections = [{"heading": "Overview", "body": "Explain the purpose of your own website in original language."}]
    if counts.get("article", 0) or counts.get("section", 0) or counts.get("img", 0):
        sections.append({"heading": "Explore", "body": "Describe your own offerings or examples using original material."})
        suggestions.append("Consider grouped content with independently designed cards or sections.")
    if counts.get("table", 0):
        suggestions.append("If the product needs structured data, define its own fields and accessible table behavior.")
    if counts.get("form", 0) or raw["form_controls"]:
        suggestions.append("Define required interactions independently; do not recreate credential forms or collect sensitive data from a reference.")
    if counts.get("nav", 0):
        suggestions.append("Plan navigation around your own information architecture.")
    sections.append({"heading": "Next steps", "body": "Describe the legitimate action visitors should take."})
    spec = {"version": 1, "title": title, "description": objective, "theme": "teal",
            "pages": [{"slug": "home", "title": "Home", "intro": objective,
                       "sections": sections, "interaction": "none"}],
            "review": {"content_rights_confirmed": False, "originality_reviewed": False, "publish_approved": False}}
    validate_spec(spec)
    return {"observations": {"standard_element_counts": counts,
                             "heading_levels": raw["heading_levels"],
                             "viewport_present": raw["viewport_present"],
                             "images_without_alt_attribute": raw["images_without_alt_attribute"]},
            "suggestions": suggestions, "project": spec,
            "limitations": ["Structural hints only; no remote fetch, rendering, source copying or backend inference.",
                            "The new project is an unapproved starter; replace placeholder content and review design before publishing."]}


def reference_batch_plan(sources, title, objective, authorized):
    """Analyze several authorized local pages without retaining source identifiers."""
    if authorized is not True:
        raise ValueError("Confirm permission to analyze all references")
    if not isinstance(sources, list) or not 2 <= len(sources) <= MAX_REFERENCE_PAGES:
        raise ValueError("Choose two to five local HTML references")
    if any(not isinstance(source, str) for source in sources):
        raise ValueError("References must be text")
    if any(len(source) > REFERENCE_LIMIT for source in sources) or sum(
            len(source.encode("utf-8")) for source in sources) > REFERENCE_LIMIT:
        raise ValueError("Combined references exceed 64 KiB")
    results = [reference_plan(source, title, objective, True) for source in sources]
    draft = results[0]["project"]
    pages = []
    observations = []
    suggestions = []
    for index, result in enumerate(results, start=1):
        observations.append({"reference_number": index, **result["observations"]})
        for suggestion in result["suggestions"]:
            if suggestion not in suggestions:
                suggestions.append(suggestion)
        page = result["project"]["pages"][0].copy()
        if index > 1:
            page["slug"] = f"topic-{index}"
            page["title"] = f"Topic {index}"
        pages.append(page)
    draft["pages"] = pages
    validate_spec(draft)
    return {
        "observations": {"reference_count": len(sources), "pages": observations},
        "suggestions": suggestions + [
            "Rename and organize proposed pages around the actual audience; the generic topic names are not taken from the references."],
        "project": draft,
        "limitations": [
            "Local structural observations only; source names, text, links, scripts, styling and assets are not copied.",
            "The input order supplies generic draft pages, not inferred navigation, private functionality or a reconstructed site.",
            "No remote retrieval, rendering, authentication or backend inference.",
            "The draft remains unapproved; replace placeholders and review independently before publishing.",
        ],
    }
