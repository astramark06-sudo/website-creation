"""Test selecting and composing original components in the graphical studio."""
import unittest

from browser_engine import launch_browser

from playwright.sync_api import expect, sync_playwright
from scripts.creator_studio import make_handler
from test_studio import serve


class ComponentBrowserTests(unittest.TestCase):
    def test_component_selection_and_keyboard_ordering(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "component-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                sections = page.locator(".page-card").first.locator(".section-card")
                first = sections.nth(0)
                first.get_by_label("Component type").select_option("faq")
                first.get_by_label("Section heading").fill("Original question")
                first.get_by_label("Section body").fill("Original answer")
                first.get_by_role("button", name="Move section down").click()
                expect(sections.nth(1).get_by_label("Section heading")).to_have_value("Original question")
                page.get_by_role("button", name="Refresh preview").click()
                expect(page.locator("#status")).to_contain_text("Preview generated")
                details = page.frame_locator("#frame").locator("details.component-faq")
                expect(details.locator("summary")).to_have_text("Original question")
                details.locator("summary").click()
                expect(details.locator("p")).to_be_visible()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
