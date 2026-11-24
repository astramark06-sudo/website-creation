"""Check downloaded evidence against a verified draft without opening a browser."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.creator_preflight import prepare_draft
from scripts.creator_preflight_verify import check_preflight, BASE_CHECKS, INTERACTION_CHECKS, MAX_REPORT
from scripts.creator_project import read_spec, filename
from scripts.creator_release import release_report
from scripts.creator_browser import VIEWPORTS

ROOT = Path(__file__).resolve().parents[1]


class PreflightVerifierTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")
        self.baseline = release_report(self.spec)

    def browser(self, spec, *, output, engine):
        return {
            "version": 1, "project_sha256": self.baseline["project_sha256"], "files": self.baseline["files"],
            "browser": engine, "browser_version": "synthetic", "status": "passed",
            "findings": [], "viewports": list(VIEWPORTS), "limitations": ["Synthetic fixture"],
            "results": [{"page": filename(page), "width": width, "diagnostics": [],
                         "checks": {key: True for key in sorted(BASE_CHECKS | INTERACTION_CHECKS[page["interaction"]])}}
                        for page in spec["pages"] for width in VIEWPORTS],
        }

    def prepare(self, output):
        with patch("scripts.creator_release.check_browser", side_effect=self.browser):
            return prepare_draft(self.spec, output, engines=["chromium", "firefox", "webkit"])

    def test_pass_and_read_only_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "draft"
            self.prepare(output)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with patch("scripts.creator_release.check_browser") as browser:
                result = check_preflight(output, required_engines=["chromium", "firefox", "webkit"])
                browser.assert_not_called()
            self.assertEqual(result["status"], "passed")
            self.assertFalse(result["browser_tests_rerun"])
            self.assertFalse(result["report_authenticity_verified"])
            self.assertFalse(result["publication_ready"])
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            with self.assertRaises(ValueError):
                check_preflight(output, required_engines=["chromium"])

    def test_rejects_tampered_or_incomplete_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "draft"
            original = self.prepare(output)
            evidence = output / "preflight-report.json"

            def mutations(report):
                yield lambda: report["bundle"].update(archive_sha256="incorrect")
                yield lambda: report["release"].update(publication_ready=True)
                yield lambda: report["release"].update(warnings=["invented"])
                yield lambda: report["release"]["browser_reports"].pop()
                yield lambda: report["release"]["browser_reports"][0]["results"].pop()
                yield lambda: report["release"]["browser_reports"][0]["results"][0]["checks"].pop("navigation")
                yield lambda: report["release"]["browser_reports"][0]["results"][0]["checks"].update(response=1)
                yield lambda: report["release"]["browser_reports"][0]["results"][0]["diagnostics"].append("failure")
                yield lambda: report["release"]["browser_reports"][0]["results"][0].update(width=360.0)
                yield lambda: report["release"]["browser_reports"][1].update(browser="chromium")

            for index in range(len(list(mutations(copy.deepcopy(original))))):
                altered = copy.deepcopy(original)
                list(mutations(altered))[index]()
                evidence.write_text(json.dumps(altered), encoding="utf-8")
                with self.subTest(index=index), self.assertRaises(ValueError):
                    check_preflight(output)

            for raw in (b'{"version":1,"version":1}', b"[" * 3000 + b"]" * 3000,
                        b"x" * (MAX_REPORT + 1)):
                evidence.write_bytes(raw)
                with self.assertRaises(ValueError):
                    check_preflight(output)
            evidence.write_text(json.dumps(original), encoding="utf-8")
            (output / "creator-project.zip").write_bytes(b"not the verified ZIP")
            with self.assertRaises(ValueError):
                check_preflight(output)


if __name__ == "__main__":
    unittest.main()
