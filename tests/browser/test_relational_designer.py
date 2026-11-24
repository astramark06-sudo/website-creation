"""Exercise the visual schema editor and its actual exported database schema."""
import json
import tempfile
from pathlib import Path
import unittest
import zipfile
from playwright.sync_api import expect, sync_playwright

from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from test_studio import serve


class RelationalDesignerTests(unittest.TestCase):
    def test_visual_schema_export_and_json_roundtrip(self):
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp, serve(lambda port: make_handler(port, "designer-test")) as url:
            browser = launch_browser(pw)
            context = browser.new_context(accept_downloads=True)
            try:
                page = context.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.locator("#relational-panel > summary").click()
                page.get_by_role("button", name="Load example schema", exact=True).click()
                tables = page.locator(".relational-table")
                expect(tables).to_have_count(2)
                page.get_by_role("button", name="Add table", exact=True).click()
                expect(tables).to_have_count(3)
                third = tables.nth(2)
                third.get_by_label("Table label", exact=True).fill("Suppliers")
                third.get_by_role("button", name="Add field", exact=True).click()
                new_field = third.locator(".relational-field").nth(1)
                new_field.get_by_label("Field label", exact=True).fill("Category")
                new_field.get_by_label("Field type", exact=True).select_option("relation")
                new_field.get_by_label("Related table", exact=True).select_option("categories")
                tables.first.get_by_role("button", name="Remove table", exact=True).click()
                expect(page.locator("#relational-design-status")).to_contain_text("before removing")
                expect(tables).to_have_count(3)
                page.locator("#relational-json-panel summary").click()
                raw = page.locator("#relational-schema")
                schema = json.loads(raw.input_value())
                self.assertEqual(schema["tables"][2]["label"], "Suppliers")
                self.assertEqual(schema["tables"][2]["fields"][1]["target"], "categories")
                schema["tables"][2]["label"] = "Vendors"
                raw.fill(json.dumps(schema))
                expect(page.locator("#relational-visual")).to_be_hidden()
                page.get_by_role("button", name="Validate and apply JSON").click()
                expect(tables.nth(2).get_by_label("Table label", exact=True)).to_have_value("Vendors")
                raw.fill('{"version":1,"tables":[]}')
                page.get_by_role("button", name="Validate and apply JSON").click()
                expect(raw).to_have_attribute("aria-invalid", "true")
                expect(page.locator("#relational-visual")).to_be_hidden()
                raw.fill(json.dumps(schema))
                page.get_by_role("button", name="Validate and apply JSON").click()
                expect(tables).to_have_count(3)
                expect(page.locator("#relational-visual")).to_be_visible()
                with page.expect_download() as schema_download:
                    page.get_by_role("button", name="Download schema JSON").click()
                schema_download.value.save_as(Path(tmp)/"schema.json")
                self.assertEqual(json.loads((Path(tmp)/"schema.json").read_text()), schema)
                with page.expect_download() as bundle:
                    page.get_by_role("button", name="Export relational database app").click()
                bundle.value.save_as(Path(tmp)/"app.zip")
                with zipfile.ZipFile(Path(tmp)/"app.zip") as archive:
                    self.assertEqual(json.loads(archive.read("config.json"))["schema"], schema)
                page.set_viewport_size({"width":360,"height":900})
                self.assertTrue(page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    unittest.main()
