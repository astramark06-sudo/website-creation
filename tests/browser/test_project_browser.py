"""Verify per-project browser evidence and failure boundaries."""
from pathlib import Path
import tempfile
import unittest

from browser_engine import browser_engine

from scripts.creator_browser import check_browser
from scripts.creator_project import build, read_spec

ROOT = Path(__file__).resolve().parents[2]


class ProjectBrowserTests(unittest.TestCase):
    def test_all_pages_all_widths(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        spec["pages"][0]["sections"][0]["kind"] = "faq"
        spec["pages"][0]["sections"][1].update(kind="links", body="Workspace | workspace\nHome | home")
        spec["pages"][0]["title"] = "LongTitle" * 10
        report = check_browser(spec, engine=browser_engine())
        self.assertEqual(report["status"], "passed", report["findings"])
        self.assertEqual(len(report["results"]), 6)
        self.assertEqual(report["viewports"], [360, 768, 1440])
        self.assertEqual(len(report["project_sha256"]), 64)
        self.assertTrue(any(r["checks"].get("task_persistence") for r in report["results"]))
        for result in report["results"]:
            self.assertTrue(result["checks"]["unique_ids"])
            self.assertTrue(result["checks"]["labeled_form_controls"])
            self.assertTrue(result["checks"]["skip_target_focus"])
            self.assertTrue(result["checks"]["named_buttons_and_links"])
            self.assertTrue(result["checks"]["page_links"])
            self.assertEqual(result["diagnostics"], [])

    def test_refuse_tampered_output(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            build(spec, output)
            (output / "index.html").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                check_browser(spec, output, engine=browser_engine())

    def test_requires_publication_approval_when_requested(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        with self.assertRaises(ValueError):
            check_browser(spec, publish=True, engine=browser_engine())


if __name__ == "__main__":
    unittest.main()
