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


    def test_page_links_editor_preview_and_validation(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "page-links-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                first = page.locator(".page-card").first.locator(".section-card").first
                first.get_by_label("Component type").select_option("links")
                first.get_by_label("Section heading").fill("Continue exploring")
                body = first.get_by_label("Section body")
                body.fill("Open workspace | workspace")
                page.get_by_role("button", name="Refresh preview").click()
                expect(page.locator("#status")).to_contain_text("Preview generated")
                anchor = page.frame_locator("#frame").locator(".component-links a")
                expect(anchor).to_have_text("Open workspace")
                expect(anchor).to_have_attribute("data-preview-href", "workspace.html")
                self.assertIsNone(anchor.get_attribute("href"))
                body.fill("Missing | missing")
                page.get_by_role("button", name="Refresh preview").click()
                expect(page.locator("#status")).to_contain_text("Invalid project")
            finally:
                browser.close()


    def test_page_address_rename_preserves_links_and_blocks_referenced_deletion(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "rename-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                expect(page.locator("#preview")).to_be_enabled()
                cards = page.locator(".page-card")
                first = cards.first.locator(".section-card").first
                first.get_by_label("Component type").select_option("links")
                body = first.get_by_label("Section body")
                body.fill("Open workspace | workspace\nBack home | home")
                address = cards.nth(1).get_by_label("Page address")
                for invalid in ("home", "index", "com1", "Bad address", ""):
                    address.fill(invalid)
                    address.press("Tab")
                    expect(address).to_have_value("workspace")
                    expect(body).to_have_value("Open workspace | workspace\nBack home | home")
                address.fill("guide")
                address.press("Tab")
                expect(address).to_have_value("guide")
                expect(body).to_have_value("Open workspace | guide\nBack home | home")
                expect(page.locator("#status")).to_contain_text("1 page links updated")
                page.get_by_role("button", name="Refresh preview").click()
                expect(page.locator("#status")).to_contain_text("Preview generated")
                expect(page.frame_locator("#frame").locator(".component-links a").first).to_have_attribute("data-preview-href", "guide.html")
                cards.nth(1).get_by_role("button", name="Remove page").click()
                expect(page.locator("#status")).to_contain_text("Cannot remove a referenced page")
                expect(cards).to_have_count(2)
                body.fill("Back home | home")
                cards.nth(1).get_by_role("button", name="Remove page").click()
                expect(cards).to_have_count(1)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
