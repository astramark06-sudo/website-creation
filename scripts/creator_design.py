"""Original, finite design presets for structured website projects.

Only fixed, project-owned CSS is emitted. No arbitrary user CSS or asset URLs.
"""
DESIGN_CHOICES = {
    "layout": ("grid", "editorial", "showcase", "compact"),
    "typeface": ("system", "editorial"),
    "density": ("comfortable", "spacious"),
    "surface": ("rounded", "square", "flat"),
}
DEFAULT_DESIGN = {key: values[0] for key, values in DESIGN_CHOICES.items()}
LAYOUTS = {
    "grid": "",
    "editorial": """
.wrap { max-width: 60rem; }
.hero { max-width: 42rem; }
.grid { grid-template-columns: minmax(0, 1fr); max-width: 48rem; }
.grid .card { padding-block: 1.75rem; }
""",
    "showcase": """
.wrap { max-width: 76rem; }
.hero { max-width: none; text-align: center; padding: clamp(1rem, 5vw, 4rem) 0; }
.hero p { max-width: 42rem; margin-inline: auto; }
.grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr)); }
@media (min-width: 900px) { .grid .card:first-child { grid-column: span 2; } }
""",
    "compact": """
main { padding-block: 1.5rem; }
.hero { margin-bottom: 1.5rem; }
h1 { font-size: clamp(1.8rem, 4vw, 2.75rem); }
.grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 13rem), 1fr)); gap: .75rem; }
""",
}
TYPEFACES = {
    "system": "",
    "editorial": "h1, h2 { font-family: Georgia, 'Times New Roman', serif; letter-spacing: -.02em; }",
}
DENSITIES = {
    "comfortable": "",
    "spacious": "main { padding-block: 4rem; } .grid { gap: 1.75rem; } .card { padding: clamp(1.25rem, 4vw, 2.5rem); }",
}
SURFACES = {
    "rounded": "",
    "square": ".card, .button, button, input { border-radius: 0; }",
    "flat": ".grid .card { border: 0; border-top: 2px solid var(--accent); border-radius: 0; background: transparent; padding-inline: 0; }",
}


def design_for(spec):
    design = spec.get("design", DEFAULT_DESIGN)
    if not isinstance(design, dict) or set(design) != set(DESIGN_CHOICES):
        raise ValueError("Invalid design fields")
    for key, options in DESIGN_CHOICES.items():
        if not isinstance(design[key], str) or design[key] not in options:
            raise ValueError("Unsupported design option: " + key)
    return dict(design)


def design_css(spec):
    design = design_for(spec)
    parts = [LAYOUTS[design["layout"]], TYPEFACES[design["typeface"]],
             DENSITIES[design["density"]], SURFACES[design["surface"]]]
    return "".join("\n" + part.strip() + "\n" for part in parts if part)
