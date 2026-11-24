"""Verify workflow controls in an exported application."""
import io
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile
from playwright.sync_api import expect, sync_playwright
from scripts.creator_fullstack import export_fullstack
from test_studio import serve


class WorkflowBrowserTests(unittest.TestCase):
    def test_stage_transition_filter_and_persistence(self):
        fields = [{"id": "stage", "label": "Workflow", "type": "stage",
                   "choices": ["Draft", "Review", "Approved"]}]
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(export_fullstack("Documents", "Local workflow", "custom", fields))) as archive:
                for name in archive.namelist():
                    (root / name).write_bytes(archive.read(name))
            app = runpy.run_path(str(root / "server.py"))
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                with serve(lambda port: app["handler"](port, "workflow-test", root / "workspace.sqlite3")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    expect(page.get_by_label("Workflow", exact=True)).to_be_disabled()
                    expect(page.get_by_label("Workflow", exact=True)).to_have_value("Draft")
                    page.get_by_label("Title", exact=True).fill("Original document")
                    page.get_by_role("button", name="Add record", exact=True).click()
                    expect(page.locator("#items dd")).to_have_text("Draft")
                    page.get_by_role("button", name="Next stage: Review", exact=True).click()
                    expect(page.locator("#items dd")).to_have_text("Review")
                    page.get_by_role("button", name="Next stage: Approved", exact=True).click()
                    expect(page.locator("#items dd")).to_have_text("Approved")
                    page.reload()
                    expect(page.locator("#items dd")).to_have_text("Approved")
                    expect(page.get_by_role("button", name="Next stage:", exact=False)).to_have_count(0)
                    page.get_by_label("Workflow stage").select_option("Draft")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
                    page.get_by_label("Workflow stage").select_option("Approved")
                    page.get_by_role("button", name="Apply filters").click()
                    expect(page.locator("#status")).to_have_text("1 matching records.")
                    page.get_by_role("button", name="Previous stage: Review").click()
                    expect(page.locator("#status")).to_have_text("0 matching records.")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
