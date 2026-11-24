"""Test portable draft preflight with deterministic synthetic browser evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.creator_preflight import prepare_draft
from scripts.creator_project import read_spec, filename
from scripts.creator_release import release_report
from scripts.creator_bundle import read_verified_bundle

ROOT = Path(__file__).resolve().parents[1]


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")
        self.baseline = release_report(self.spec)

    def browser(self, spec, *, output, engine):
        return {
            "project_sha256": self.baseline["project_sha256"], "files": self.baseline["files"],
            "browser": engine, "status": "passed", "findings": [],
            "results": [{"page": filename(page), "width": width, "checks": {"response": True}}
                        for page in spec["pages"] for width in (360, 768, 1440)],
        }

    def test_verified_bundle_and_report_match(self):
        self.spec["review"] = {key: True for key in self.spec["review"]}
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.creator_release.check_browser", side_effect=self.browser):
            output = Path(tmp) / "draft"
            report = prepare_draft(self.spec, output, engines=["chromium", "firefox", "webkit"])
            self.assertEqual(report["status"], "passed")
            self.assertTrue(report["bundle_available"])
            self.assertFalse(report["publication_ready"])
            self.assertEqual(json.loads((output / "preflight-report.json").read_text()), report)
            draft, bundle = read_verified_bundle((output / "creator-project.zip").read_bytes())
            self.assertFalse(any(draft["review"].values()))
            self.assertTrue(all(self.spec["review"].values()))
            self.assertEqual(bundle, report["bundle"])
            self.assertEqual(bundle["files"], report["release"]["files"])
            self.assertEqual(bundle["project_sha256"], report["release"]["project_sha256"])
            self.assertEqual([item["browser"] for item in report["release"]["browser_reports"]],
                             ["chromium", "firefox", "webkit"])
            before = (output / "preflight-report.json").read_bytes()
            with self.assertRaises(ValueError):
                prepare_draft(self.spec, output, engines=["chromium"])
            self.assertEqual((output / "preflight-report.json").read_bytes(), before)

    def test_failure_retains_report_but_not_bundle(self):
        def failed(spec, *, output, engine):
            return {**self.browser(spec, output=output, engine=engine), "status": "failed",
                    "findings": ["Synthetic browser failure"]}
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.creator_release.check_browser", side_effect=failed):
            output = Path(tmp) / "draft"
            report = prepare_draft(self.spec, output, engines=["chromium"])
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["bundle_available"])
            self.assertTrue((output / "preflight-report.json").is_file())
            self.assertFalse((output / "creator-project.zip").exists())

    def test_rejects_missing_engines_and_mismatched_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "draft"
            for engines in ([], ["unknown"], ["chromium", "chromium"]):
                with self.assertRaises(ValueError):
                    prepare_draft(self.spec, output, engines=engines)
            report = {**self.baseline, "project_sha256": "wrong"}
            with patch("scripts.creator_preflight.release_report", return_value=report):
                with self.assertRaises(ValueError):
                    prepare_draft(self.spec, output, engines=["chromium"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
