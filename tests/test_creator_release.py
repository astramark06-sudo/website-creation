"""Release reports describe observed evidence and never approve publication."""
from pathlib import Path
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from scripts.creator_project import build, read_spec, filename, verify
from scripts.creator_release import release_report, main

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

    def test_existing_output_matches_and_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            build(self.spec, output)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(release_report(self.spec, output=output), release_report(self.spec))
            self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)
            (output / "index.html").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                release_report(self.spec, output=output)
            self.assertEqual((output / "index.html").read_text(), "changed")

    def test_reviewed_gate_rejects_unapproved_input_and_missing_engines(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / "spec.json"
            spec_file.write_text(json.dumps(self.spec), encoding="utf-8")
            for approved in (False, True):
                if approved:
                    self.spec["review"] = {key: True for key in self.spec["review"]}
                    spec_file.write_text(json.dumps(self.spec), encoding="utf-8")
                with patch("sys.argv", ["release", "--spec", str(spec_file), "--require-reviewed"]), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        main()
                    self.assertEqual(exc.exception.code, 2)

    def test_reviewed_gate_records_warnings_and_exits_nonzero(self):
        self.spec["review"] = {key: True for key in self.spec["review"]}
        self.spec["title"] = "My website"
        report = release_report(self.spec)
        report["browser_reports"] = [{"status": "passed"}]
        with tempfile.TemporaryDirectory() as tmp:
            spec_file, evidence = Path(tmp) / "spec.json", Path(tmp) / "report.json"
            spec_file.write_text(json.dumps(self.spec), encoding="utf-8")
            args = ["release", "--spec", str(spec_file), "--require-reviewed", "--engine", "chromium", "--report", str(evidence)]
            with patch("sys.argv", args), patch("scripts.creator_release.release_report", return_value=report), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    main()
                self.assertEqual(exc.exception.code, 1)
            self.assertEqual(json.loads(evidence.read_text()), report)
            self.assertFalse(report["publication_ready"])

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
