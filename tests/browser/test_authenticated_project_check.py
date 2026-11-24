"""Verify the generated authenticated profile on the installed browser engine."""
import importlib.util
from pathlib import Path
import unittest

from browser_engine import browser_engine
from scripts.creator_authenticated_check import check_authenticated
from scripts.creator_relational import read_schema

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(importlib.util.find_spec("django"), "Optional Django staging dependency not installed")
class AuthenticatedProjectCheckTests(unittest.TestCase):
    def test_cyclic_schema_and_roles(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        schema["tables"][0]["fields"].append({"id": "featured", "label": "Featured", "type": "relation", "target": "items"})
        report = check_authenticated("Audit example", "Synthetic role verification", schema, browser_engine())
        self.assertEqual(report["status"], "passed", report.get("diagnostic"))
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(len(report["tables"]), 2)
        self.assertFalse(report["public_deployment"])
