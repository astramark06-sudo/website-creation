"""Tests for preview and verified draft export."""
import io
import json
from pathlib import Path
import unittest
import zipfile

from scripts.creator_project import read_spec
from scripts.creator_studio import export_zip, preview_document

ROOT = Path(__file__).resolve().parents[1]


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")

    def test_preview_is_inert(self):
        page = preview_document(self.spec, "workspace")
        self.assertIn("<style>", page)
        self.assertIn("Task workspace", page)
        self.assertNotIn('<script src="app.js"', page)
        self.assertNotIn(' href="workspace.html"', page)

    def test_unknown_page_rejected(self):
        with self.assertRaises(ValueError):
            preview_document(self.spec, "missing")

    def test_export_clears_review_approvals(self):
        self.spec["review"] = {key: True for key in self.spec["review"]}
        with zipfile.ZipFile(io.BytesIO(export_zip(self.spec))) as archive:
            self.assertIn("site/index.html", archive.namelist())
            self.assertIn("site/workspace.html", archive.namelist())
            self.assertIn("site/app.js", archive.namelist())
            draft = json.loads(archive.read("project.json"))
            manifest = json.loads(archive.read("site/creator-manifest.json"))
            self.assertFalse(any(draft["review"].values()))
            self.assertFalse(manifest["publish_approved"])
            self.assertTrue(all(self.spec["review"].values()))


if __name__ == "__main__":
    unittest.main()
