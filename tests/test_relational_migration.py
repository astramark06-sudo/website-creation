"""Additive migration of physical tables, relationships and ID sequences."""
import copy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing

from scripts import creator_relational as rel
from scripts.creator_relational_export import export_relational

ROOT = Path(__file__).resolve().parents[1]


class RelationalMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = rel.read_schema(ROOT / "projects" / "relational-example.json")
        self.source, self.target = self.root / "source.sqlite3", self.root / "target.sqlite3"
        rel.create_database(self.source, self.old)
        self.new = copy.deepcopy(self.old)
        self.new["tables"][1]["fields"].append({"id": "supplier", "label": "Supplier", "type": "relation", "target": "suppliers"})
        self.new["tables"][1]["fields"].append({"id": "cost", "label": "Cost", "type": "integer"})
        self.new["tables"].append({"id": "suppliers", "label": "Suppliers", "fields": [{"id": "name", "label": "Name", "type": "text"}]})
        self.defaults = {"items": {"supplier": None, "cost": 0}}

    def test_records_references_and_deleted_id_high_water_mark(self):
        category = rel.add_record(self.source, self.old, "categories", {"name": "Office"})
        deleted = rel.add_record(self.source, self.old, "categories", {"name": "Deleted"})
        rel.delete_record(self.source, self.old, "categories", deleted)
        values = {"name": "Pens", "quantity": 7, "state": "Available", "category": category}
        item = rel.add_record(self.source, self.old, "items", values)
        before = self.source.read_bytes()
        report = rel.migrate_database(self.source, self.target, self.old, self.new, self.defaults)
        self.assertEqual(report, {"records": 2, "tables_added": 1, "fields_added": 2})
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(rel.list_records(self.target, self.new, "items"), [{"id": item, "values": {**values, "supplier": None, "cost": 0}}])
        self.assertEqual(rel.list_records(self.target, self.new, "suppliers"), [])
        self.assertGreater(rel.add_record(self.target, self.new, "categories", {"name": "New"}), deleted)
        rel.delete_record(self.target, self.new, "categories", category)
        self.assertIsNone(rel.list_records(self.target, self.new, "items")[0]["values"]["category"])
        self.assertEqual(rel.list_records(self.source, self.old, "items")[0]["values"]["category"], category)

    def test_invalid_defaults_and_overwrite(self):
        before = self.source.read_bytes()
        for defaults in ({}, {"items": {"supplier": 1, "cost": 0}}, {"items": {"supplier": None, "cost": True}}, {"items": {"supplier": None, "cost": -1}}):
            with self.subTest(defaults=defaults), self.assertRaises(ValueError):
                rel.migrate_database(self.source, self.target, self.old, self.new, defaults)
            self.assertFalse(self.target.exists())
        self.target.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            rel.migrate_database(self.source, self.target, self.old, self.new, self.defaults)
        self.assertEqual(self.target.read_bytes(), b"existing")
        self.assertEqual(self.source.read_bytes(), before)

    def test_cyclic_relations(self):
        old = copy.deepcopy(self.old)
        old["tables"][0]["fields"].append({"id": "item", "label": "Item", "type": "relation", "target": "items"})
        path = self.root / "cycle.sqlite3"
        rel.create_database(path, old)
        category = rel.add_record(path, old, "categories", {"name": "A", "item": None})
        item = rel.add_record(path, old, "items", {"name": "B", "quantity": 1, "state": "Available", "category": category})
        rel.edit_record(path, old, "categories", category, {"name": "A", "item": item})
        new = copy.deepcopy(old)
        new["tables"][0]["fields"].append({"id": "label", "label": "Label", "type": "text"})
        rel.migrate_database(path, self.target, old, new, {"categories": {"label": "Migrated"}})
        self.assertEqual(rel.list_records(self.target, new, "categories")[0]["values"]["item"], item)
        self.assertEqual(rel.list_records(self.target, new, "items")[0]["values"]["category"], category)

    def test_reject_changed_schema_and_invalid_source(self):
        modified = copy.deepcopy(self.new)
        modified["tables"][0]["label"] = "Changed"
        with self.assertRaises(ValueError):
            rel.migrate_database(self.source, self.target, self.old, modified, self.defaults)
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("INSERT INTO t_items(f_name,f_quantity,f_state,f_category) VALUES (?,?,?,?)", ("Bad relation", 1, "Available", 999))
        with self.assertRaises(ValueError):
            rel.migrate_database(self.source, self.target, self.old, self.new, self.defaults)
        self.assertFalse(self.target.exists())

    def test_cli_exported_app_migration(self):
        old_folder, new_folder = self.root / "old", self.root / "new"
        for folder, schema in [(old_folder, self.old), (new_folder, self.new)]:
            folder.mkdir()
            with zipfile.ZipFile(io.BytesIO(export_relational("Local", "Migration test", schema))) as archive:
                for name in archive.namelist():
                    (folder / name).write_bytes(archive.read(name))
        source = old_folder / "workspace.sqlite3"
        rel.create_database(source, self.old)
        rel.add_record(source, self.old, "categories", {"name": "Original"})
        defaults = self.root / "defaults.json"
        defaults.write_text(json.dumps(self.defaults), encoding="utf-8")
        command = [sys.executable, str(old_folder / "server.py"), "--migrate-to", str(new_folder), "--defaults", str(defaults)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rel.list_records(new_folder / "workspace.sqlite3", self.new, "categories")[0]["values"], {"name": "Original"})
        self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=20).returncode, 0)


if __name__ == "__main__":
    unittest.main()
