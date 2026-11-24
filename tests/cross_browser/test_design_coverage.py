"""Cross-engine checks of original component and layout combinations."""
import os
from pathlib import Path
import unittest

from scripts.creator_browser import check_browser
from scripts.creator_project import read_spec

ROOT = Path(__file__).resolve().parents[2]


class DesignCoverage(unittest.TestCase):
    def test_component_layout_combinations(self):
        engine = os.environ.get("ENGINE", "chromium")
        for layout in ("grid", "editorial", "showcase", "compact"):
            with self.subTest(layout=layout, engine=engine):
                spec = read_spec(ROOT / "projects" / "example.json")
                spec["design"] = {"layout": layout, "typeface": "system",
                                  "density": "comfortable", "surface": "rounded"}
                spec["pages"][0]["interaction"] = "search"
                spec["pages"][0]["sections"] = [
                    {"kind": kind, "heading": "Original " + kind,
                     "body": "First example\nSecond example"}
                    for kind in ("card", "article", "callout", "faq", "list", "steps")
                ]
                report = check_browser(spec, engine=engine)
                self.assertEqual(report["status"], "passed", report["findings"])
                self.assertEqual(len(report["results"]), len(spec["pages"]) * 3)
