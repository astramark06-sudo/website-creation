"""Test original multi-page projects and release gates."""
import copy
from pathlib import Path
import tempfile
import unittest

from scripts.creator_project import build, read_spec, validate_spec, verify

ROOT = Path(__file__).resolve().parents[1]


class CreatorProjectTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")

    def test_build_and_verify_multi_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            result = build(self.spec, out)
            self.assertEqual(result["pages"], 2)
            self.assertFalse(result["browser_tested"])
            self.assertIn('href="workspace.html"', (out / "index.html").read_text())
            self.assertIn('src="app.js"', (out / "workspace.html").read_text())
            self.assertTrue((out / ".nojekyll").exists())
            self.assertEqual(verify(self.spec, out)["status"], "passed")

    def test_publish_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            with self.assertRaises(ValueError):
                build(self.spec, out, publish=True)
            self.assertFalse(out.exists())
            approved = copy.deepcopy(self.spec)
            approved["review"] = {key: True for key in approved["review"]}
            self.assertTrue(build(approved, out, publish=True)["publish_approved"])

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(self.spec, out)
            (out / "index.html").write_text("changed")
            with self.assertRaises(ValueError):
                verify(self.spec, out)

    def test_extra_files_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(self.spec, out)
            (out / "unreviewed.txt").write_text("extra")
            with self.assertRaises(ValueError):
                verify(self.spec, out)

    def test_path_traversal_rejected(self):
        self.spec["pages"][1]["slug"] = "../outside"
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_html_escaped(self):
        self.spec["pages"][0]["sections"][0]["body"] = "<script>bad()</script>"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(self.spec, out)
            self.assertIn("&lt;script&gt;", (out / "index.html").read_text())
            self.assertNotIn("<script>bad()", (out / "index.html").read_text())

    def test_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(self.spec, out)
            with self.assertRaises(FileExistsError):
                build(self.spec, out)


if __name__ == "__main__":
    unittest.main()
