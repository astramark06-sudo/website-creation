"""Verify per-project browser evidence and failure boundaries."""
from pathlib import Path
import tempfile
import unittest

from scripts.creator_browser import check_browser
from scripts.creator_project import build, read_spec

ROOT = Path(__file__).resolve().parents[2]


class ProjectBrowserTests(unittest.TestCase):
    def test_all_pages_all_widths(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        spec["pages"][0]["sections"][0]["kind"] = "faq"
        spec["pages"][0]["title"] = "LongTitle" * 10
        report = check_browser(spec)
        self.assertEqual(report["status"], "passed", report["findings"])
        self.assertEqual(len(report["results"]), 6)
        self.assertEqual(report["viewports"], [360, 768, 1440])
        self.assertEqual(len(report["project_sha256"]), 64)
        self.assertTrue(any(r["checks"].get("task_persistence") for r in report["results"]))

    def test_refuse_tampered_output(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            build(spec, output)
            (output / "index.html").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                check_browser(spec, output)

    def test_requires_publication_approval_when_requested(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        with self.assertRaises(ValueError):
            check_browser(spec, publish=True)


if __name__ == "__main__":
    unittest.main()
