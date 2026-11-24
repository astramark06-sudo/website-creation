"""Exercise the actual Studio audit endpoint and report invalidation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from playwright.sync_api import expect, sync_playwright

from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from test_studio import serve


class StudioRelationalCheckTests(unittest.TestCase):
    def test_report_and_invalidation(self):
        # The actual verifier has a separate full three-engine regression test.
        # This test isolates the Studio wiring and checks the submitted schema.
        result = {"status": "passed", "files": {"config.json": "a" * 64},
                  "project_sha256": "a" * 64, "checks": {"synthetic": True}}
        with patch("scripts.creator_studio.check_relational", return_value=result) as check:
            with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw, serve(lambda port: make_handler(port, "check-test", browser_checks=True)) as url:
                browser = launch_browser(pw)
                try:
                    page = browser.new_page(accept_downloads=True)
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    page.locator("#relational-panel > summary").click()
                    page.get_by_role("button", name="Load example schema", exact=True).click()
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="Verify relational application", exact=True).click()
                    expect(page.locator("#relational-check-status")).to_contain_text("Passed")
                    self.assertEqual(check.call_count, 1)
                    self.assertEqual(check.call_args.args[2]["tables"][0]["id"], "categories")
                    self.assertEqual(check.call_args.args[3], "chromium")
                    with page.expect_download() as report:
                        page.get_by_role("button", name="Download application report", exact=True).click()
                    target = Path(tmp) / "report.json"
                    report.value.save_as(target)
                    self.assertEqual(json.loads(target.read_text()), result)
                    page.locator(".relational-table").first.get_by_label("Table label", exact=True).fill("Changed")
                    expect(page.get_by_role("button", name="Download application report", exact=True)).to_be_disabled()
                    expect(page.locator("#relational-check-status")).to_contain_text("Application changed")
                finally:
                    browser.close()

    def test_disabled_by_default(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "disabled-check")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.locator("#relational-panel > summary").click()
                expect(page.locator("#relational-check-panel")).to_be_hidden()
                response = page.request.post(url + "/api/relational-check", headers={"Origin": url, "X-Creator-Token": "disabled-check"},
                                             data={"confirmed": True})
                self.assertEqual(response.status, 403)
            finally:
                browser.close()
