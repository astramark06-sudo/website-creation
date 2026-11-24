"""Positive search coverage for adjacent semantic elements and Unicode."""
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import expect, sync_playwright
from scripts.creator_project import read_spec, build
from scripts.creator_browser import check_browser
from test_studio import QuietFiles, serve

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
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            out = Path(tmp) / "site"
            build(spec, out)
            browser = pw.chromium.launch()
            try:
                with serve(lambda port: lambda *args, **kw: QuietFiles(*args, directory=str(out), **kw)) as url:
                    page = browser.new_page()
                    page.goto(url)
                    search = page.locator("#section-query")
                    for term in ("first value", "RE\u0301SUME\u0301"):
                        search.fill(term)
                        expect(page.locator("#section-search-status")).to_have_text("1 of 2 sections shown.")
                        expect(page.locator("#page-sections > *").first).to_be_visible()
                        expect(page.locator("#page-sections > *").nth(1)).to_be_hidden()
                    page.locator("#section-reset").click()
                    expect(page.locator("#section-search-status")).to_have_text("2 of 2 sections shown.")
            finally:
                browser.close()
