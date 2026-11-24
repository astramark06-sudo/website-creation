"""Exercise the real exported relational app on the selected browser engine."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright
from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from test_studio import serve


def module_from(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelationalBrowserTests(unittest.TestCase):
    def test_studio_export_and_relational_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            browser = launch_browser(pw)
            context = browser.new_context(accept_downloads=True)
            try:
                page = context.new_page()
                with serve(lambda port: make_handler(port, "studio-relational-test")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    page.locator("#relational-panel summary").click()
                    page.get_by_role("button", name="Load example schema").click()
                    schema = json.loads(page.locator("#relational-schema").input_value())
                    self.assertEqual(len(schema["tables"]), 2)
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Export relational database app").click()
                    download.value.save_as(root / "app.zip")
                names = {"server.py", "creator_relational.py", "app.js", "style.css", "index.html", "config.json", "README.md", ".gitignore"}
                with zipfile.ZipFile(root / "app.zip") as archive:
                    self.assertEqual(set(archive.namelist()), names)
                    for name in names:
                        (root / name).write_bytes(archive.read(name))
                engine = module_from("creator_relational", root / "creator_relational.py")
                with patch.dict(sys.modules, {"creator_relational": engine}):
                    server = module_from("exported_relational_server", root / "server.py")
                with serve(lambda port: server.make_handler(port, "test-token", root)) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("0 records in Categories.")
                    page.get_by_label("Name", exact=True).fill("Office")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#status")).to_have_text("1 records in Categories.")
                    page.get_by_label("Table", exact=True).select_option("items")
                    expect(page.locator("#status")).to_have_text("0 records in Items.")
                    page.get_by_label("Name", exact=True).fill("Pens")
                    page.get_by_label("Quantity", exact=True).fill("7")
                    page.get_by_label("Category", exact=True).select_option(label="Office (#1)")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#records")).to_contain_text("Office (#1)")
                    page.get_by_role("button", name="Edit", exact=True).click()
                    page.get_by_label("Quantity", exact=True).fill("9")
                    page.get_by_role("button", name="Save record").click()
                    expect(page.locator("#records dd").nth(1)).to_have_text("9")
                    self.assertEqual(page.request.get(url + "/api/records?table=items").status, 403)
                    self.assertEqual(page.request.post(url + "/api/records", data={"action": "delete", "table": "items", "id": 1}).status, 403)
                    page.get_by_label("Table", exact=True).select_option("categories")
                    expect(page.locator("#status")).to_have_text("1 records in Categories.")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="Delete", exact=True).click()
                    expect(page.locator("#status")).to_have_text("0 records in Categories.")
                with serve(lambda port: server.make_handler(port, "new-token", root)) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("0 records in Categories.")
                    page.get_by_label("Table", exact=True).select_option("items")
                    expect(page.locator("#status")).to_have_text("1 records in Items.")
                    expect(page.locator("#records dd").nth(1)).to_have_text("9")
                    expect(page.locator("#records dd").last).to_have_text("None")
                    for width in (360, 768, 1440):
                        page.set_viewport_size({"width": width, "height": 900})
                        self.assertTrue(page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
            finally:
                context.close()
                browser.close()
