"""Search interaction generation and preview boundaries."""
from pathlib import Path
import tempfile
import unittest

from scripts.creator_project import assemble, build, read_spec, verify
from scripts.creator_studio import preview_document

ROOT = Path(__file__).resolve().parents[1]


class SearchTests(unittest.TestCase):
    def test_search_only_on_selected_pages(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        self.assertNotIn("search.js", assemble(spec))
        spec["pages"][0]["interaction"] = "search"
        files = assemble(spec)
        self.assertIn('src="search.js"', files["index.html"])
        self.assertNotIn('src="search.js"', files["workspace.html"])
        self.assertIn("search.js", files)
        self.assertIn("app.js", files)
        self.assertNotIn('src="search.js"', preview_document(spec, "home"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(spec, out)
            self.assertEqual(verify(spec, out)["status"], "passed")
