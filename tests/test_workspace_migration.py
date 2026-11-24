"""Regression coverage for non-destructive, additive SQLite migrations."""
import io
import json
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.creator_fullstack import export_fullstack, TEMPLATE


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = runpy.run_path(str(TEMPLATE / "server.py"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.sqlite3"
        self.dest = self.root / "new.sqlite3"

    def test_general_records_to_custom(self):
        change, listing = self.app["change_item"], self.app["list_items"]
        change(self.source, {"action": "add", "title": "Original", "notes": "Notes"})
        change(self.source, {"action": "toggle", "id": listing(self.source)[0]["id"]})
        original = listing(self.source)
        data = self.source.read_bytes()
        fields = [{"id": "qty", "label": "Quantity", "type": "integer"},
                  {"id": "stage", "label": "Stage", "type": "stage", "choices": ["Draft", "Review"]},
                  {"id": "related", "label": "Related", "type": "link"}]
        defaults = {"qty": 0, "stage": "Draft", "related": None}
        report = self.app["migrate_database"](self.source, self.dest, [], fields, defaults)
        self.assertEqual(report, {"records": 1, "added_fields": 3})
        self.assertEqual(self.source.read_bytes(), data)
        self.assertEqual(listing(self.source), original)
        record = listing(self.dest, fields=fields)[0]
        self.assertEqual(record["id"], original[0]["id"])
        self.assertEqual(record["done"], 1)
        self.assertEqual(record["details"], defaults)
        self.assertEqual(record["links"], {"related": None})
        snapshot = self.dest.read_bytes()
        with self.assertRaises(FileExistsError):
            self.app["migrate_database"](self.source, self.dest, [], fields, defaults)
        self.assertEqual(self.dest.read_bytes(), snapshot)

    def test_existing_links_and_stage_survive(self):
        old = [{"id": "related", "label": "Related", "type": "link"},
               {"id": "stage", "label": "Stage", "type": "stage", "choices": ["Draft", "Review"]}]
        new = old + [{"id": "label", "label": "Label", "type": "text"}]
        change, listing = self.app["change_item"], self.app["list_items"]
        change(self.source, {"action": "add", "title": "Parent", "notes": "", "details": {"related": None, "stage": "Draft"}}, old)
        parent = listing(self.source, fields=old)[0]["id"]
        change(self.source, {"action": "add", "title": "Child", "notes": "", "details": {"related": parent, "stage": "Draft"}}, old)
        child = listing(self.source, fields=old)[0]["id"]
        change(self.source, {"action": "move_stage", "id": child, "expected": "Draft", "target": "Review"}, old)
        before = listing(self.source, fields=old)
        self.app["migrate_database"](self.source, self.dest, old, new, {"label": "New"})
        after = listing(self.dest, fields=new)
        for previous, migrated in zip(before, after):
            self.assertEqual(migrated["id"], previous["id"])
            self.assertEqual(migrated["links"], previous["links"])
            self.assertEqual(migrated["details"], {**previous["details"], "label": "New"})
        change(self.dest, {"action": "delete", "id": parent}, new)
        self.assertIsNone(listing(self.dest, fields=new)[0]["details"]["related"])
        self.assertEqual(listing(self.source, fields=old), before)

    def test_invalid_plan_and_source_never_overwrite(self):
        integer = {"id": "qty", "label": "Quantity", "type": "integer"}
        link = {"id": "link", "label": "Related", "type": "link"}
        stage = {"id": "stage", "label": "Stage", "type": "stage", "choices": ["Draft", "Review"]}
        self.app["change_item"](self.source, {"action": "add", "title": "Original", "notes": ""})
        before = self.source.read_bytes()
        for old, new, defaults in [
            ([], [integer], {}),
            ([], [integer], {"qty": True}),
            ([], [link], {"link": 1}),
            ([], [stage], {"stage": "Review"}),
            ([integer], [link], {}),
            ([integer], [integer, link], {"link": None}),
        ]:
            with self.subTest(old=old, new=new, defaults=defaults), self.assertRaises(ValueError):
                self.app["migrate_database"](self.source, self.dest, old, new, defaults)
            self.assertFalse(self.dest.exists())
            self.assertEqual(self.source.read_bytes(), before)

    def test_empty_database_migration(self):
        self.app["list_items"](self.source)
        fields = [{"id": "tag", "label": "Tag", "type": "text"}]
        self.assertEqual(self.app["migrate_database"](self.source, self.dest, [], fields, {"tag": ""})["records"], 0)
        self.assertEqual(self.app["list_items"](self.dest, fields=fields), [])

    def test_cli_migrates_into_separate_export(self):
        old, new = self.root / "old", self.root / "new"
        fields = [{"id": "tag", "label": "Tag", "type": "text"}]
        for folder, bundle in [(old, export_fullstack("Original", "Records")),
                               (new, export_fullstack("Original", "Records", "custom", fields))]:
            folder.mkdir()
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                for name in archive.namelist():
                    (folder / name).write_bytes(archive.read(name))
        self.app["change_item"](old / "workspace.sqlite3", {"action": "add", "title": "Original", "notes": ""})
        defaults = self.root / "defaults.json"
        defaults.write_text(json.dumps({"tag": "Migrated"}), encoding="utf-8")
        command = [sys.executable, str(old / "server.py"), "--migrate-to", str(new), "--defaults", str(defaults)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.app["list_items"](new / "workspace.sqlite3", fields=fields)[0]["details"], {"tag": "Migrated"})
        self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=20).returncode, 0)


if __name__ == "__main__":
    unittest.main()
