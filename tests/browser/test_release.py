"""Project-specific release report and stale report invalidation."""
import unittest
from playwright.sync_api import expect, sync_playwright
from scripts.creator_studio import make_handler
from test_studio import serve


class ReleaseBrowserTests(unittest.TestCase):
    def test_report_is_invalidated_by_edit(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "release-test")) as url:
            browser = pw.chromium.launch()
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
