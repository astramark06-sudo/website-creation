"""Run the project-specific verifier on a cyclic, mixed-type schema."""
from pathlib import Path
import unittest

from browser_engine import browser_engine
from scripts.creator_relational import read_schema
from scripts.creator_relational_check import check_relational

ROOT = Path(__file__).resolve().parents[2]


class RelationalProjectCheckTests(unittest.TestCase):
    def test_actual_schema_verification(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        schema["tables"][0]["fields"].append({"id": "featured", "label": "Featured item", "type": "relation", "target": "items"})
        schema["tables"].append({"id": "references", "label": "References", "fields": [
            {"id": "target", "label": "Related category", "type": "relation", "target": "categories"}
        ]})
        report = check_relational("Audit original", "Synthetic application check", schema, browser_engine())
        self.assertEqual(report["status"], "passed", report.get("diagnostic"))
        self.assertEqual(len(report["tables"]), 3)
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(len(report["files"]), 8)
        self.assertTrue(all(len(digest) == 64 for digest in report["files"].values()))
        self.assertEqual(report["project_sha256"], report["files"]["config.json"])
