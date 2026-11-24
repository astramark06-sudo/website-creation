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

    def test_filtered_summary_all_field_types(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = [
            {"id": "qty", "label": "Quantity", "type": "integer"},
            {"id": "category", "label": "Category", "type": "choice", "choices": ["A", "B", "C"]},
            {"id": "related", "label": "Related", "type": "link"},
            {"id": "note", "label": "Note", "type": "text"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.sqlite3"
            change, listing, summarize = app["change_item"], app["list_items"], app["summarize_items"]
            change(path, {"action": "add", "title": "First", "notes": "",
                          "details": {"qty": 4, "category": "A", "related": None, "note": "private sample"}}, fields)
            first = listing(path, fields=fields)[0]["id"]
            change(path, {"action": "add", "title": "Second", "notes": "",
                          "details": {"qty": 9, "category": "B", "related": first, "note": ""}}, fields)
            change(path, {"action": "toggle", "id": first}, fields)
            summary = summarize(listing(path, fields=fields), fields)
            self.assertEqual((summary["total"], summary["completed"], summary["open"]), (2, 1, 1))
            self.assertEqual(summary["completion_percent"], 50)
            metrics = {field["id"]: field for field in summary["fields"]}
            self.assertEqual(metrics["qty"]["total"], 13)
            self.assertEqual(metrics["qty"]["average"], 6.5)
            self.assertEqual([c["count"] for c in metrics["category"]["choices"]], [1, 1, 0])
            self.assertEqual(metrics["related"]["linked"], 1)
            self.assertNotIn("note", metrics)
            filtered = summarize(listing(path, state="done", fields=fields), fields)
            self.assertEqual(filtered["completion_percent"], 100)
            self.assertEqual(filtered["fields"][0]["total"], 4)
            empty = summarize(listing(path, "missing", fields=fields), fields)
            self.assertIsNone(empty["completion_percent"])
            self.assertIsNone(empty["fields"][0]["average"])
            self.assertEqual(empty["fields"][0]["total"], 0)

    def test_general_record_summary(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        self.assertEqual(app["summarize_items"]([]), {"total": 0, "completed": 0, "open": 0,
                                                    "completion_percent": None, "fields": []})

    def test_ordered_workflow_transition_and_filter(self):
        app = runpy.run_path(str(TEMPLATE / "server.py"))
        fields = [{"id": "stage", "label": "Workflow", "type": "stage",
                   "choices": ["Draft", "Review", "Approved"]}]
        with zipfile.ZipFile(io.BytesIO(export_fullstack("Original", "Workflow", "custom", fields))) as archive:
            self.assertEqual(json.loads(archive.read("config.json"))["fields"], fields)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow.sqlite3"
            change, listing = app["change_item"], app["list_items"]
            add = {"action": "add", "title": "Document", "notes": "", "details": {"stage": "Draft"}}
            with self.assertRaises(ValueError):
                change(path, {**add, "details": {"stage": "Approved"}}, fields)
            change(path, add, fields)
            item = listing(path, fields=fields)[0]
            move = {"action": "move_stage", "id": item["id"], "expected": "Draft", "target": "Review"}
            with self.assertRaises(ValueError):
                change(path, {**move, "target": "Approved"}, fields)
            with self.assertRaises(ValueError):
                change(path, {**add, "action": "edit", "id": item["id"], "details": {"stage": "Review"}}, fields)
            change(path, move, fields)
            with self.assertRaises(ValueError):
                change(path, move, fields)
            self.assertEqual(listing(path, fields=fields, stage="Draft"), [])
            reviewed = listing(path, fields=fields, stage="Review")
            self.assertEqual(len(reviewed), 1)
            self.assertEqual(reviewed[0]["done"], 0)
            summary = app["summarize_items"](reviewed, fields)
            self.assertEqual([v["count"] for v in summary["fields"][0]["choices"]], [0, 1, 0])
            change(path, {**move, "expected": "Review", "target": "Draft"}, fields)
            self.assertEqual(listing(path, fields=fields)[0]["details"]["stage"], "Draft")

    def test_workflow_schema_limits(self):
        field = {"id": "stage", "label": "Stage", "type": "stage", "choices": ["One", "Two"]}
        with self.assertRaises(ValueError):
            validate_fields([{**field, "choices": ["One"]}], True)
        with self.assertRaises(ValueError):
            validate_fields([field, {**field, "id": "second"}], True)
        with self.assertRaises(ValueError):
            validate_fields([{**field, "choices": ["One", "One"]}], True)


if __name__ == "__main__":
    unittest.main()
