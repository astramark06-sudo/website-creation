"""Project-specific release report and stale report invalidation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from browser_engine import launch_browser, browser_engine
from playwright.sync_api import expect, sync_playwright
from scripts.creator_studio import make_handler
from scripts.creator_project import build, read_spec, verify
from scripts.creator_release import release_report
from test_studio import serve


class ReleaseBrowserTests(unittest.TestCase):
    def test_combined_report_with_installed_engine(self):
        root = Path(__file__).resolve().parents[2]
        spec = read_spec(root / "projects" / "example.json")
        spec["review"] = {key: True for key in spec["review"]}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            build(spec, output, publish=True)
            report = release_report(spec, engines=[browser_engine()], output=output)
            self.assertEqual(verify(spec, output, publish=True)["status"], "passed")
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["browser_reports"][0]["status"], "passed")
        self.assertEqual(report["browser_reports"][0]["files"], report["files"])
        self.assertFalse(report["publication_ready"])

    def test_combined_report_studio_consent_and_invalidation(self):
        root = Path(__file__).resolve().parents[2]
        spec = read_spec(root / "projects" / "example.json")
        report = release_report(spec)
        report["browser_reports"] = [{"browser": "firefox", "status": "passed"}]
        with patch("scripts.creator_studio.release_report", return_value=report) as check:
            with sync_playwright() as pw, serve(lambda port: make_handler(port, "combined-test", browser_checks=True)) as url:
                browser = launch_browser(pw)
                try:
                    page = browser.new_page(accept_downloads=True)
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    engine = page.get_by_label("Static site browser engine")
                    engine.select_option("firefox")
                    button = page.get_by_role("button", name="Run combined release check")
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    button.click()
                    self.assertEqual(check.call_count, 0)
                    page.once("dialog", lambda dialog: dialog.accept())
                    button.click()
                    expect(page.locator("#release-status")).to_contain_text("Combined report generated")
                    self.assertEqual(check.call_args.kwargs["engines"], ["firefox"])
                    save = page.get_by_role("button", name="Download review report")
                    with page.expect_download() as download:
                        save.click()
                    self.assertEqual(json.loads(download.value.path().read_text()), report)
                    engine.select_option("webkit")
                    expect(save).to_be_disabled()
                    expect(page.locator("#release-status")).to_contain_text("Browser changed")
                    headers = {"Origin": url, "X-Creator-Token": "combined-test"}
                    response = page.request.post(url + "/api/release-report", headers=headers,
                                                 data={"confirmed": False, "engines": ["firefox"], "spec": spec})
                    self.assertEqual(response.status, 400)
                    self.assertEqual(check.call_count, 1)
                finally:
                    browser.close()

    def test_browser_engine_selection_and_report_invalidation(self):
        report = {"status": "passed", "browser": "firefox", "results": [{"page": "index.html"}],
                  "viewports": [360, 768, 1440], "findings": [], "limitations": []}
        with patch("scripts.creator_studio.check_browser", return_value=report) as check:
            with sync_playwright() as pw, serve(lambda port: make_handler(port, "browser-test", browser_checks=True)) as url:
                browser = launch_browser(pw)
                try:
                    page = browser.new_page(accept_downloads=True)
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    engine = page.get_by_label("Static site browser engine")
                    engine.select_option("firefox")
                    button = page.get_by_role("button", name="Run browser checks", exact=True)
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    button.click()
                    self.assertEqual(check.call_count, 0)
                    page.once("dialog", lambda dialog: dialog.accept())
                    button.click()
                    expect(page.locator("#browser-check-status")).to_contain_text("passed")
                    self.assertEqual(check.call_args.kwargs["engine"], "firefox")
                    save = page.get_by_role("button", name="Download browser report")
                    with page.expect_download() as download:
                        save.click()
                    self.assertEqual(download.value.suggested_filename, "creator-browser-firefox-report.json")
                    self.assertEqual(json.loads(download.value.path().read_text()), report)
                    engine.select_option("webkit")
                    expect(save).to_be_disabled()
                    expect(page.locator("#browser-check-status")).to_contain_text("Browser changed")
                    headers = {"Origin": url, "X-Creator-Token": "browser-test"}
                    response = page.request.post(url + "/api/browser-check", headers=headers,
                                                 data={"confirmed": False, "engine": "firefox", "spec": {}})
                    self.assertEqual(response.status, 400)
                    self.assertEqual(check.call_count, 1)
                finally:
                    browser.close()

    def test_report_is_invalidated_by_edit(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "release-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.get_by_role("button", name="Check release readiness").click()
                expect(page.locator("#release-status")).to_contain_text("Report generated")
                expect(page.locator("#release-results")).to_contain_text("Build integrity")
                expect(page.locator("#release-results")).to_contain_text("Public deployment verification")
                expect(page.locator("#release-save")).to_be_enabled()
                page.get_by_label("Website name").fill("Updated draft")
                expect(page.locator("#release-save")).to_be_disabled()
                expect(page.locator("#release-status")).to_contain_text("Draft changed")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
