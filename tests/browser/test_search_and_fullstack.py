"""Exercise original search and a real exported database workspace."""
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

from playwright.sync_api import expect, sync_playwright

from scripts.creator_browser import check_browser
from scripts.creator_project import read_spec
from scripts.creator_studio import make_handler
from test_studio import serve

ROOT = Path(__file__).resolve().parents[2]


class ApplicationBrowserTests(unittest.TestCase):
    def test_project_search_audit(self):
        spec = read_spec(ROOT / "projects" / "example.json")
        spec["pages"][0]["interaction"] = "search"
        report = check_browser(spec)
        self.assertEqual(report["status"], "passed", report["results"])
        self.assertEqual(sum(r["checks"].get("search_reset", False)
                             for r in report["results"]), 3)

    def test_exported_database_workspace(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(accept_downloads=True)
            try:
                page = context.new_page()
                root = Path(tmp)
                with serve(lambda port: make_handler(port, "studio-test")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    page.get_by_label("Website name").fill("Original records")
                    with page.expect_download() as dl:
                        page.get_by_role("button", name="Export local database app").click()
                    dl.value.save_as(root / "app.zip")
                app = root / "app"
                app.mkdir()
                with zipfile.ZipFile(root / "app.zip") as archive:
                    expected = {"server.py", "index.html", "style.css", "app.js", "config.json",
                                "README.md", ".gitignore"}
                    self.assertEqual(set(archive.namelist()), expected)
                    for name in expected:
                        (app / name).write_bytes(archive.read(name))
                namespace = runpy.run_path(str(app / "server.py"))
                handler = namespace["handler"]
                db = app / "workspace.sqlite3"
                with serve(lambda port: handler(port, "first-test-token", db)) as url:
                    page.goto(url)
                    expect(page.locator("#title")).to_have_text("Original records")
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    page.locator("#name").fill("First original record")
                    page.locator("#notes").fill("Example notes")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    page.get_by_role("button", name="Edit", exact=True).click()
                    page.locator("#name").fill("Updated original record")
                    page.get_by_role("button", name="Save record").click()
                    expect(page.locator("#items h3")).to_have_text("Updated original record")
                    page.get_by_role("button", name="Complete", exact=True).click()
                    expect(page.locator("#items h3")).to_have_class("completed")
                    page.locator("#filter").select_option("open")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    self.assertEqual(page.request.get(url + "/api/items").status, 403)
                    self.assertEqual(page.request.post(url + "/api/items", data={"action": "delete", "id": 1}).status, 403)
                # Start a new HTTP server with a new token and the same on-disk database.
                with serve(lambda port: handler(port, "second-test-token", db)) as url:
                    page.goto(url)
                    expect(page.locator("#items h3")).to_have_text("Updated original record")
                    expect(page.locator("#items h3")).to_have_class("completed")
                    page.locator("#search").fill("nonexistent")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    page.locator("#search").fill("updated")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="Delete", exact=True).click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
            finally:
                context.close()
                browser.close()
