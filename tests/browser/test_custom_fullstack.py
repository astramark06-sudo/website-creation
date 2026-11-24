"""Exercise a user-defined local model with a real relational link field."""
from pathlib import Path
import io
import runpy
import tempfile
import unittest
import zipfile

from playwright.sync_api import expect, sync_playwright

from scripts.creator_fullstack import export_fullstack
from test_studio import serve


class CustomModelBrowserTests(unittest.TestCase):
    def test_custom_linked_records(self):
        fields = [
            {"id": "field1", "label": "Category", "type": "choice", "choices": ["A", "B"]},
            {"id": "field2", "label": "Related record", "type": "link"},
        ]
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(export_fullstack("Linked records", "Local custom model", "custom", fields))) as archive:
                for name in archive.namelist():
                    (root / name).write_bytes(archive.read(name))
            app = runpy.run_path(str(root / "server.py"))
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                with serve(lambda port: app["handler"](port, "custom-model-test", root / "workspace.sqlite3")) as url:
                    page.goto(url)
                    page.get_by_label("Title", exact=True).fill("Parent")
                    page.get_by_label("Category").select_option("A")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    page.get_by_label("Title", exact=True).fill("Child")
                    page.get_by_label("Category").select_option("B")
                    page.get_by_label("Related record").select_option(label="Parent")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#items")).to_contain_text("Parent")
                    page.get_by_label("Search", exact=True).fill("parent")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("2 matching records.")
                    page.get_by_label("Search", exact=True).fill("child")
                    page.get_by_role("button", name="Apply filters").click()
                    page.get_by_role("button", name="Edit", exact=True).click()
                    options = page.get_by_label("Related record").locator("option")
                    self.assertEqual(options.filter(has_text="Child").count(), 0)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
