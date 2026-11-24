"""Verify relational application bundles and HTTP mutation boundaries."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.creator_relational import read_schema
from scripts.creator_relational_export import export_relational

ROOT = Path(__file__).resolve().parents[1]


class ExportTests(unittest.TestCase):
    def test_bundle_is_standalone(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        with zipfile.ZipFile(io.BytesIO(export_relational("Local", "Original example", schema))) as archive:
            self.assertEqual(set(archive.namelist()), {"server.py", "creator_relational.py", "app.js", "style.css", "index.html", "config.json", "README.md", ".gitignore"})
            self.assertEqual(json.loads(archive.read("config.json"))["schema"], schema)
            self.assertNotIn(b"from creator_project import", archive.read("creator_relational.py"))
            for name in ("server.py", "creator_relational.py"):
                compile(archive.read(name), name, "exec")
    def test_invalid_schema_rejected(self):
        with self.assertRaises(ValueError):
            export_relational("Local", "Original", {"version": 1, "tables": []})
