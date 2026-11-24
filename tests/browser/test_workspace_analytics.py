"""Verify live filtered analytics in an actual exported local application."""
from pathlib import Path
import io
import runpy
import tempfile
import unittest
import zipfile

from playwright.sync_api import expect, sync_playwright

from scripts.creator_fullstack import export_fullstack
from test_studio import serve


class WorkspaceAnalyticsTests(unittest.TestCase):
    def test_inventory_summary_after_mutations_and_filtering(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(export_fullstack("Supplies", "Local inventory", "inventory"))) as archive:
                for name in archive.namelist():
                    (root / name).write_bytes(archive.read(name))
            app = runpy.run_path(str(root / "server.py"))
            db = root / "workspace.sqlite3"
            fields = [{"id": "quantity", "label": "Quantity", "type": "integer"},
                      {"id": "location", "label": "Storage location", "type": "text"}]
            for title, quantity in (("Pens", 5), ("Paper", 12)):
                app["change_item"](db, {"action": "add", "title": title, "notes": "",
                                       "details": {"quantity": quantity, "location": "Shelf"}}, fields)
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                with serve(lambda port: app["handler"](port, "analytics-test", db)) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("2 matching records.")
                    expect(page.locator("#analytics-counts dd").first).to_have_text("2")
                    expect(page.locator("#analytics-fields dd").first).to_have_text("17")
                    expect(page.locator("#analytics-fields dd").nth(1)).to_have_text("8.5")
                    record = page.locator("#items li").filter(has=page.get_by_role("heading", name="Pens", exact=True))
                    record.get_by_role("button", name="Complete", exact=True).click()
                    expect(page.locator("#completion-caption")).to_have_text("50% completed.")
                    page.locator("#filter").select_option("done")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    expect(page.locator("#analytics-fields dd").first).to_have_text("5")
                    expect(page.locator("#completion-caption")).to_have_text("100% completed.")
                    page.get_by_label("Search", exact=True).fill("not present")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    expect(page.locator("#completion-caption")).to_have_text("No matching records to summarize.")
                    expect(page.locator("#analytics-fields dd").nth(1)).to_have_text("Not applicable")
                    expect(page.locator("#completion-meter")).to_be_hidden()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
