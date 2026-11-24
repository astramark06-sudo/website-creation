"""Verify audit boundaries without requiring an installed browser."""
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

from scripts.creator_relational import read_schema
from scripts.creator_relational_check import check_relational

ROOT = Path(__file__).resolve().parents[1]


class RelationalCheckTests(unittest.TestCase):
    def test_invalid_input_rejected(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        with self.assertRaises(ValueError):
            check_relational("Audit", "Local", schema, "unknown")
        with self.assertRaises(ValueError):
            check_relational("Audit", "Local", {"version": 1, "tables": []})

    def test_failed_worker_report(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        with patch("scripts.creator_relational_check.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "Synthetic failure")):
            report = check_relational("Audit", "Local", schema)
        self.assertEqual(report["status"], "failed")
        self.assertIn("Synthetic failure", report["diagnostic"])
        self.assertEqual(len(report["files"]), 8)
