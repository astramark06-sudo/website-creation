"""Original design choices, compatibility and contrast checks."""
import itertools
from pathlib import Path
import unittest

from scripts.creator_build import THEMES
from scripts.creator_design import DESIGN_CHOICES, DEFAULT_DESIGN, design_css
from scripts.creator_project import assemble, read_spec, validate_spec

ROOT = Path(__file__).resolve().parents[1]


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")

    def test_legacy_default_unchanged(self):
        baseline = assemble(self.spec)
        self.spec["design"] = DEFAULT_DESIGN.copy()
        self.assertEqual(baseline, assemble(self.spec))

    def test_all_design_combinations(self):
        for values in itertools.product(*DESIGN_CHOICES.values()):
            self.spec["design"] = dict(zip(DESIGN_CHOICES, values))
            validate_spec(self.spec)
            result = assemble(self.spec)
            self.assertIn("index.html", result)
            self.assertNotIn("url(", design_css(self.spec))

    def test_invalid_design_rejected(self):
        self.spec["design"] = {**DEFAULT_DESIGN, "layout": "url(https://example.org)"}
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_unknown_design_key_rejected(self):
        self.spec["design"] = {**DEFAULT_DESIGN, "custom_css": "body {}"}
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_accent_contrast(self):
        def luminance(color):
            channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
            return sum(x * w for x, w in zip(linear, (0.2126, 0.7152, 0.0722)))
        for name, value in THEMES.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(1.05 / (luminance(value) + 0.05), 4.5)
                self.assertGreaterEqual((luminance("#f7f9fc") + 0.05) / (luminance(value) + 0.05), 4.5)


if __name__ == "__main__":
    unittest.main()
