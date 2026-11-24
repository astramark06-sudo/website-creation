"""Exercise the real Studio custom schema form and exported workspace."""
import json
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

from playwright.sync_api import expect, sync_playwright
from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from test_studio import serve


class StudioCustomExportTests(unittest.TestCase):
    def test_custom_workflow_export_and_responsive_layout(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            browser = launch_browser(pw)
            context = browser.new_context(accept_downloads=True)
            try:
                page = context.new_page()
                with serve(lambda port: make_handler(port, "custom-export-test")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    expect(page.locator("#custom-model-fields")).to_be_hidden()
                    page.get_by_label("Database application model").select_option("custom")
                    expect(page.locator("#custom-model-fields")).to_be_visible()
                    page.get_by_label("Custom fields", exact=True).fill("Amount | integer\nCategory | choice | A, B\nRelated | link\nStage | stage | Draft, Review, Done")
                    with page.expect_download() as saved:
                        page.get_by_role("button", name="Export local database app").click()
                    saved.value.save_as(root / "workspace.zip")
                expected = {"server.py", "index.html", "style.css", "app.js", "config.json", "README.md", ".gitignore"}
                with zipfile.ZipFile(root / "workspace.zip") as archive:
                    self.assertEqual(set(archive.namelist()), expected)
                    config = json.loads(archive.read("config.json"))
                    self.assertEqual(config["model"], "custom")
                    self.assertEqual([field["type"] for field in config["fields"]], ["integer", "choice", "link", "stage"])
                    for name in expected:
                        (root / name).write_bytes(archive.read(name))
                app = runpy.run_path(str(root / "server.py"))
                with serve(lambda port: app["handler"](port, "custom-export-app", root / "workspace.sqlite3")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    page.get_by_label("Title", exact=True).fill("Original record")
                    page.get_by_label("Amount", exact=True).fill("8")
                    page.get_by_label("Category", exact=True).select_option("B")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    expect(page.locator("#items")).to_contain_text("Draft")
                    page.get_by_role("button", name="Next stage: Review").click()
                    expect(page.locator("#items dd").last).to_have_text("Review")
                    for width in (360, 768, 1440):
                        page.set_viewport_size({"width": width, "height": 900})
                        self.assertTrue(page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"), f"Layout overflow at {width}px")
                    page.reload()
                    expect(page.locator("#items dd").last).to_have_text("Review")
            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    unittest.main()
