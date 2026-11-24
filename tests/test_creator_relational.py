"""Test real multi-table SQLite schema generation and transactional CRUD."""
import copy
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing

from scripts import creator_relational as rel

ROOT = Path(__file__).resolve().parents[1]


class RelationalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data.sqlite3"
        self.schema = rel.read_schema(ROOT / "projects" / "relational-example.json")
        rel.create_database(self.path, self.schema)

    def test_physical_tables_and_relationship_lifecycle(self):
        with closing(sqlite3.connect(self.path)) as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"t_categories", "t_items", "schema_info"} <= names)
            foreign = db.execute("PRAGMA foreign_key_list(t_items)").fetchone()
            self.assertEqual(foreign[2], "t_categories")
            self.assertEqual(foreign[6], "SET NULL")
        category = rel.add_record(self.path, self.schema, "categories", {"name": "Office"})
        data = {"name": "Pencils", "quantity": 5, "state": "Available", "category": category}
        item = rel.add_record(self.path, self.schema, "items", data)
        self.assertEqual(rel.list_records(self.path, self.schema, "items"), [{"id": item, "values": data}])
        rel.edit_record(self.path, self.schema, "items", item, {**data, "quantity": 7})
        rel.delete_record(self.path, self.schema, "categories", category)
        self.assertEqual(rel.list_records(self.path, self.schema, "items")[0]["values"], {**data, "quantity": 7, "category": None})
        new = rel.add_record(self.path, self.schema, "categories", {"name": "New"})
        self.assertGreater(new, category)
        self.assertIsNone(rel.list_records(self.path, self.schema, "items")[0]["values"]["category"])

    def test_failed_writes_preserve_records(self):
        values = {"name": "Paper", "quantity": 2, "state": "Available", "category": None}
        item = rel.add_record(self.path, self.schema, "items", values)
        for invalid in ({**values, "quantity": True}, {**values, "quantity": -1},
                        {**values, "category": 999}, {**values, "state": "Unknown"},
                        {**values, "name": "\ud800"}, {**values, "extra": 1}):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                rel.edit_record(self.path, self.schema, "items", item, invalid)
        self.assertEqual(rel.list_records(self.path, self.schema, "items"), [{"id": item, "values": values}])
        with self.assertRaises(ValueError):
            rel.delete_record(self.path, self.schema, "items", True)
        with self.assertRaises(ValueError):
            rel.add_record(self.path, self.schema, "unknown", {})

    def test_schema_and_destination_mismatch(self):
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            rel.create_database(self.path, self.schema)
        modified = copy.deepcopy(self.schema)
        modified["tables"][0]["label"] = "Changed"
        with self.assertRaises(ValueError):
            rel.list_records(self.path, modified, "items")
        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_schema(self):
        for table, field, replacement in [
            (1, 3, {"target": "missing"}),
            (1, 3, {"target": "items"}),
            (1, 0, {"id": "id"}),
            (1, 0, {"id": "quantity"}),
            (1, 2, {"choices": ["Same", "Same"]}),
            (1, 0, {"id": "invalid-name"}),
        ]:
            schema = copy.deepcopy(self.schema)
            schema["tables"][table]["fields"][field].update(replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                rel.validate_schema(schema)

    def test_cli(self):
        target = self.path.with_name("cli.sqlite3")
        command = [sys.executable, str(ROOT / "scripts" / "creator_relational.py"), "--schema",
                   str(ROOT / "projects" / "relational-example.json"), "--output", str(target)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(rel.list_records(target, self.schema, "categories"), [])
        self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=20).returncode, 0)


if __name__ == "__main__":
    unittest.main()
