"""Verify original full-stack export and SQLite behavior."""
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

from scripts.creator_fullstack import export_fullstack, TEMPLATE


class FullstackTests(unittest.TestCase):
    def test_export(self):
        with zipfile.ZipFile(io.BytesIO(export_fullstack("Original", "A local application"))) as z:
            self.assertEqual(json.loads(z.read("config.json"))["title"], "Original")
            self.assertIn("server.py", z.namelist())
            self.assertIn("app.js", z.namelist())
            self.assertNotIn("workspace.sqlite3", z.namelist())

    def test_database_lifecycle(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite3"
            change, listing = app["change_item"], app["list_items"]
            change(path, {"action":"add", "title":"Example", "notes":"Original note"})
            item = listing(path)[0]
            change(path, {"action":"edit", "id":item["id"], "title":"Updated", "notes":"New note"})
            self.assertEqual(listing(path, "updated")[0]["title"], "Updated")
            change(path, {"action":"toggle", "id":item["id"]})
            self.assertEqual(len(listing(path, state="done")), 1)
            self.assertEqual(listing(path, state="open"), [])
            change(path, {"action":"delete", "id":item["id"]})
            self.assertEqual(listing(path), [])

    def test_invalid_record_rejected(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                app["change_item"](Path(tmp) / "db", {"action":"add", "title":"", "notes":""})


if __name__ == "__main__":
    unittest.main()
