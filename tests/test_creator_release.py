"""Release reports describe observed evidence and never approve publication."""
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.creator_project import read_spec, filename, verify
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

    def test_combined_report_matches_verified_output_and_never_approves(self):
        baseline = release_report(self.spec)

        def browser(spec, *, output, engine):
            self.assertEqual(verify(spec, output)["status"], "passed")
            return {"project_sha256": baseline["project_sha256"], "files": baseline["files"],
                    "browser": engine, "status": "passed", "findings": [],
                    "results": [{"page": filename(page), "width": width, "checks": {"response": True}}
                                for page in spec["pages"] for width in (360, 768, 1440)]}

        with patch("scripts.creator_release.check_browser", side_effect=browser) as check:
            report = release_report(self.spec, engines=["chromium", "webkit"])
            self.assertEqual(check.call_count, 2)
        self.assertEqual([item["browser"] for item in report["browser_reports"]], ["chromium", "webkit"])
        gates = {g["name"]: g["status"] for g in report["gates"]}
        self.assertEqual(gates["Project-specific browser and responsive testing"], "passed")
        self.assertEqual(gates["Accessibility review"], "not-tested")
        self.assertFalse(report["publication_ready"])

        good = report["browser_reports"][0]
        for invalid in ({**good, "project_sha256": "wrong"}, {**good, "files": {}},
                        {**good, "results": []}, {**good, "findings": ["failure"]}):
            with patch("scripts.creator_release.check_browser", return_value=invalid):
                with self.assertRaises(ValueError):
                    release_report(self.spec, engines=["chromium"])
        with patch("scripts.creator_release.check_browser", return_value={**good, "status": "failed"}):
            failed = release_report(self.spec, engines=["chromium"])
        self.assertIn("failed", [gate["status"] for gate in failed["gates"]])
        self.assertFalse(failed["publication_ready"])

    def test_invalid_engines_rejected(self):
        for engines in (["unknown"], ["chromium", "chromium"], "chromium"):
            with self.assertRaises(ValueError):
                release_report(self.spec, engines=engines)

    def test_invalid_spec_rejected(self):
        self.spec["pages"][0]["slug"] = "../private"
        with self.assertRaises(ValueError):
            release_report(self.spec)


if __name__ == "__main__":
    unittest.main()
