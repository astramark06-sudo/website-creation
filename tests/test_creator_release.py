"""Release reports describe observed evidence and never approve publication."""
from pathlib import Path
import unittest

from scripts.creator_project import read_spec
from scripts.creator_release import release_report

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")

    def test_integrity_and_unverified_gates(self):
        report = release_report(self.spec)
        self.assertFalse(report["publication_ready"])
        self.assertEqual(report["pages"], len(self.spec["pages"]))
        gates = {g["name"]: g["status"] for g in report["gates"]}
        self.assertEqual(gates["Build integrity"], "passed")
        self.assertEqual(gates["Originality"], "review")
        self.assertEqual(gates["Public deployment verification"], "not-tested")

    def test_human_flags_never_certify_release(self):
        self.spec["review"] = {key: True for key in self.spec["review"]}
        report = release_report(self.spec)
        self.assertFalse(report["publication_ready"])
        self.assertIn("declared", [g["status"] for g in report["gates"]])

    def test_changed_content_changes_digest(self):
        previous = release_report(self.spec)["project_sha256"]
        self.spec["title"] = "My website"
        after = release_report(self.spec)
        self.assertNotEqual(previous, after["project_sha256"])
        self.assertTrue(after["warnings"])

    def test_invalid_spec_rejected(self):
        self.spec["pages"][0]["slug"] = "../private"
        with self.assertRaises(ValueError):
            release_report(self.spec)


if __name__ == "__main__":
    unittest.main()
