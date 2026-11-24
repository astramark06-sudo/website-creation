"""Test verification boundaries without loading optional runtime packages."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts.creator_authenticated_check import check_authenticated
from scripts.creator_relational import read_schema

ROOT = Path(__file__).resolve().parents[1]


class AuthenticatedCheckTests(unittest.TestCase):
    def test_worker_failure_does_not_include_process_logs(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        with patch("scripts.creator_authenticated_check.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 1, '{"status":"failed","diagnostic":"Synthetic failure"}', "Private process output")):
            report = check_authenticated("Audit", "Synthetic", schema)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["diagnostic"], "Synthetic failure")
        self.assertNotIn("Private process output", str(report))
        self.assertFalse(report["public_deployment"])

    def test_invalid_engine_and_schema(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        with self.assertRaises(ValueError):
            check_authenticated("Audit", "Synthetic", schema, "unknown")
        with self.assertRaises(ValueError):
            check_authenticated("Audit", "Synthetic", {"version": 1, "tables": []})
