"""Use bounded, coarse screenshot observations to propose an original design.

Only aggregate measurements are accepted. No image bytes, OCR, source
content, assets, exact colors or logos are retained or emitted.
"""
try:
    from .creator_project import require_text, validate_spec
    from .creator_design import DEFAULT_DESIGN
except ImportError:
    from creator_project import require_text, validate_spec
    from creator_design import DEFAULT_DESIGN

FAMILIES = ("neutral", "warm", "cool", "mixed")
SHAPES = ("portrait", "landscape", "square")


def visual_plan(observations, title, objective, authorized):
    if authorized is not True:
        raise ValueError("Confirm permission to analyze the reference")
    if not isinstance(observations, dict) or set(observations) != {
            "shape", "palette_family", "density", "lightness"}:
        raise ValueError("Invalid screenshot observations")
    if observations["shape"] not in SHAPES or observations["palette_family"] not in FAMILIES:
        raise ValueError("Invalid screenshot classification")
    if observations["density"] not in ("low", "medium", "high") or observations["lightness"] not in ("light", "mixed", "dark"):
        raise ValueError("Invalid screenshot measurement")
    title = require_text(title, "Website name", 120)
    objective = require_text(objective, "Objective", 1000)
    # Deliberately choose a fixed, independently designed palette, not sampled colors.
    theme = {"neutral": "teal", "warm": "plum", "cool": "forest", "mixed": "blue"}[observations["palette_family"]]
    design = dict(DEFAULT_DESIGN)
    design["layout"] = {"low": "editorial", "medium": "showcase", "high": "compact"}[observations["density"]]
    design["density"] = "spacious" if observations["density"] == "low" else "comfortable"
    design["surface"] = "flat" if observations["shape"] == "portrait" else "rounded"
    draft = {
        "version": 1, "title": title, "description": objective, "theme": theme, "design": design,
        "pages": [{"slug": "home", "title": "Home", "intro": objective,
                   "sections": [
                       {"heading": "Overview", "body": "Describe your own purpose and audience in original language.", "kind": "article"},
                       {"heading": "Explore", "body": "Introduce your own offerings, ideas or examples.", "kind": "card"},
                       {"heading": "Next steps", "body": "Explain the legitimate next step for your visitors.", "kind": "callout"}
                   ], "interaction": "none"}],
        "review": {"content_rights_confirmed": False, "originality_reviewed": False, "publish_approved": False}
    }
    validate_spec(draft)
    return {
        "observations": dict(observations), "project": draft,
        "suggestions": ["Use the proposed original design tokens as a starting point.",
                        "Write independent content and arrange sections around the actual visitor needs.",
                        "Review responsive layout and replace all starter content."],
        "limitations": ["Coarse visual statistics only, not semantic vision, OCR, layout reconstruction or code extraction.",
                        "Screenshot dimensions and color variation do not reliably establish the reference's structure.",
                        "No source image, artwork, exact colors, text or credentials are copied.",
                        "The draft is unapproved; human rights, originality and release review remain necessary."]
    }
