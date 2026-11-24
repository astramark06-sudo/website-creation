"""Tests for original generation and offline structural analysis."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.creator_build import MAX_HTML_BYTES, MODES, build_site, inspect_file, inspect_html


class CreatorBuildTests(unittest.TestCase):
    def test_original_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in MODES:
                with self.subTest(mode=mode):
                    out = Path(tmp) / mode
                    files = build_site(out, "Example", "Description", mode, "blue")
                    page = (out / "index.html").read_text()
                    self.assertIn('<html lang="en">', page)
                    self.assertNotIn("https://", page)
                    self.assertIn("index.html", files)
                    report = inspect_file(out / "index.html")
                    self.assertEqual(report["heading_levels"][0], 1)
                    self.assertTrue(report["viewport_present"])
                    manifest = json.loads((out / "creator-manifest.json").read_text())
                    self.assertEqual(manifest["network_dependencies"], [])
                    self.assertEqual("app.js" in files, mode == "task-dashboard")

    def test_title_and_description_are_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build_site(out, "<script>alert(1)</script>", '" onclick="bad()', "landing", "teal")
            page = (out / "index.html").read_text()
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertIn("&quot; onclick=&quot;", page)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build_site(out, "Original", "Text", "landing", "teal")
            with self.assertRaises(FileExistsError):
                build_site(out, "Replacement", "Text", "portfolio", "teal")
            self.assertIn("Original", (out / "index.html").read_text())

    def test_inspector_omits_sensitive_content(self):
        report = inspect_html('<html lang="en"><h1>Secret text</h1><img src="secret.png">'
                              '<script src="private.js"></script><input value="privatevalue">')
        result = json.dumps(report)
        self.assertEqual(report["images_without_alt_attribute"], 1)
        self.assertEqual(report["script_elements_with_src"], 1)
        self.assertEqual(report["form_controls"], {"input": 1})
        for private in ("Secret text", "secret.png", "private.js", "privatevalue"):
            self.assertNotIn(private, result)

    def test_rejects_oversized_input(self):
        with self.assertRaises(ValueError):
            inspect_html("x" * (MAX_HTML_BYTES + 1))

    def test_rejects_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_site(Path(tmp) / "site", "Name", "Text", "invalid", "blue")


if __name__ == "__main__":
    unittest.main()
