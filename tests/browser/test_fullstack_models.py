"""Export and exercise a typed inventory app in a real browser."""
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile
import io

from playwright.sync_api import expect, sync_playwright
from scripts.creator_fullstack import export_fullstack
from test_studio import serve


class ModelBrowserTests(unittest.TestCase):
    def test_inventory_fields(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(export_fullstack("Supplies", "Local inventory", "inventory"))) as archive:
                for name in archive.namelist():
                    (root / name).write_bytes(archive.read(name))
            app = runpy.run_path(str(root / "server.py"))
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                with serve(lambda port: app["handler"](port, "model-test", root / "workspace.sqlite3")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    page.get_by_label("Title", exact=True).fill("Pens")
                    page.get_by_label("Quantity").fill("15")
                    page.get_by_label("Storage location").fill("Shelf A")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#items")).to_contain_text("Shelf A")
                    page.get_by_role("button", name="Edit", exact=True).click()
                    expect(page.get_by_label("Quantity")).to_have_value("15")
                    page.get_by_label("Quantity").fill("9")
                    page.get_by_role("button", name="Save record").click()
                    expect(page.locator("#items dd").first).to_have_text("9")
                    page.reload()
                    expect(page.locator("#items dd").first).to_have_text("9")
                    page.get_by_label("Search", exact=True).fill("shelf a")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
            finally:
                browser.close()
