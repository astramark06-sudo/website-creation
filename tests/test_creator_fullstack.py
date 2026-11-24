"""Verify original full-stack export and SQLite behavior."""
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

from scripts.creator_fullstack import export_fullstack, TEMPLATE, MODELS, validate_fields


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

    def test_model_fields_persist_search_and_validate(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = MODELS["inventory"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.sqlite3"
            change, listing = app["change_item"], app["list_items"]
            payload = {"action": "add", "title": "Notebook", "notes": "", "details": {"quantity": 12, "location": "Shelf A"}}
            change(path, payload, fields)
            item = listing(path, "shelf a", fields=fields)[0]
            self.assertEqual(item["details"]["quantity"], 12)
            change(path, {"action": "edit", "id": item["id"], "title": "Notebook", "notes": "", "details": {"quantity": 7, "location": "Shelf B"}}, fields)
            self.assertEqual(listing(path, fields=fields)[0]["details"]["quantity"], 7)
            with self.assertRaises(ValueError):
                change(path, {**payload, "details": {"quantity": True, "location": "Shelf A"}}, fields)
            with self.assertRaises(ValueError):
                listing(path, fields=MODELS["issues"])
            change(path, {"action": "delete", "id": item["id"]}, fields)
            self.assertEqual(listing(path, fields=fields), [])

    def test_model_export_and_rejection(self):
        with zipfile.ZipFile(io.BytesIO(export_fullstack("Original", "Inventory", "inventory"))) as z:
            config = json.loads(z.read("config.json"))
            self.assertEqual(config["fields"], MODELS["inventory"])
        with self.assertRaises(ValueError):
            export_fullstack("Original", "Workspace", "unknown")

    def test_choice_validation(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = MODELS["issues"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                app["change_item"](Path(tmp) / "db", {"action": "add", "title": "Original", "notes": "", "details": {"priority": "Invalid", "category": ""}}, fields)

    def test_custom_schema_and_link_lifecycle(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = validate_fields([
            {"id": "tag", "label": "Tag", "type": "text"},
            {"id": "related", "label": "Related record", "type": "link"},
        ], require_nonempty=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "linked.sqlite3"
            change, listing = app["change_item"], app["list_items"]
            change(path, {"action": "add", "title": "Parent", "notes": "", "details": {"tag": "root", "related": None}}, fields)
            parent = listing(path, fields=fields)[0]
            change(path, {"action": "add", "title": "Child", "notes": "", "details": {"tag": "leaf", "related": parent["id"]}}, fields)
            child = listing(path, "parent", fields=fields)[0]
            self.assertEqual(child["links"]["related"]["title"], "Parent")
            with self.assertRaises(ValueError):
                change(path, {"action": "edit", "id": child["id"], "title": "Child", "notes": "", "details": {"tag": "leaf", "related": child["id"]}}, fields)
            change(path, {"action": "delete", "id": parent["id"]}, fields)
            child = listing(path, fields=fields)[0]
            self.assertIsNone(child["details"]["related"])
            self.assertIsNone(child["links"]["related"])

    def test_custom_export_validation(self):
        fields = [{"id": "field1", "label": "Related", "type": "link"}]
        with zipfile.ZipFile(io.BytesIO(export_fullstack("Original", "Custom", "custom", fields))) as z:
            self.assertEqual(json.loads(z.read("config.json"))["fields"], fields)
        with self.assertRaises(ValueError):
            export_fullstack("Original", "Custom", "custom", [])
        with self.assertRaises(ValueError):
            export_fullstack("Original", "Inventory", "inventory", fields)
        with self.assertRaises(ValueError):
            validate_fields([{"id": "bad-id", "label": "Bad", "type": "text"}], True)

    def test_checked_backup_preserves_links_and_never_overwrites(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = [{"id": "related", "label": "Related", "type": "link"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, backup = root / "live.sqlite3", root / "backup.sqlite3"
            change, listing = app["change_item"], app["list_items"]
            change(source, {"action": "add", "title": "Parent", "notes": "", "details": {"related": None}}, fields)
            parent = listing(source, fields=fields)[0]
            change(source, {"action": "add", "title": "Child", "notes": "Snapshot", "details": {"related": parent["id"]}}, fields)
            expected = listing(source, fields=fields)
            self.assertEqual(app["backup_database"](source, backup, fields), backup)
            original_bytes = backup.read_bytes()
            with self.assertRaises(FileExistsError):
                app["backup_database"](source, backup, fields)
            self.assertEqual(backup.read_bytes(), original_bytes)
            change(source, {"action": "delete", "id": parent["id"]}, fields)
            self.assertEqual(listing(backup, fields=fields), expected)
            self.assertIsNone(listing(source, fields=fields)[0]["details"]["related"])
            with self.assertRaises(ValueError):
                app["backup_database"](source, root / "wrong.sqlite3", MODELS["inventory"])
            self.assertFalse((root / "wrong.sqlite3").exists())

    def test_missing_database_backup_does_not_create_files(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "missing.sqlite3", Path(tmp) / "backup.sqlite3"
            with self.assertRaises(ValueError):
                app["backup_database"](source, output)
            self.assertFalse(source.exists())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
