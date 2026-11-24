"""Positive search coverage for adjacent semantic elements and Unicode."""
from pathlib import Path
import unittest
from scripts.creator_project import read_spec
from scripts.creator_browser import check_browser

ROOT = Path(__file__).resolve().parents[2]


class SearchBoundaryTests(unittest.TestCase):
    def test_heading_and_adjacent_text_search(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        spec["pages"][0]["interaction"] = "search"
        spec["pages"][0]["sections"] = [
            {"heading": "Résumé", "body": "First | Value\nSecond | Other", "kind": "metrics"},
            {"heading": "Other section", "body": "Separate text"},
        ]
        report = check_browser(spec)
        self.assertEqual(report["status"], "passed", report["results"])
        self.assertEqual(sum(result["checks"].get("search_positive_result", False)
                             for result in report["results"]), 3)
