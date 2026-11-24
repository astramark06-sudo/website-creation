"""Studio export is available without installing Django in the Studio environment."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from playwright.sync_api import expect, sync_playwright

from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from test_studio import serve


class AuthenticatedStudioExportTests(unittest.TestCase):
    def test_explicit_local_export(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw, serve(lambda port: make_handler(port, "auth-export-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page(accept_downloads=True)
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.locator("#relational-panel > summary").click()
                page.get_by_role("button", name="Load example schema", exact=True).click()
                button = page.get_by_role("button", name="Export authenticated staging app", exact=True)
                page.once("dialog", lambda dialog: dialog.dismiss())
                button.click()
                page.once("dialog", lambda dialog: dialog.accept())
                with page.expect_download() as saved:
                    button.click()
                path = Path(tmp) / "app.zip"
                saved.value.save_as(path)
                with zipfile.ZipFile(path) as archive:
                    config = json.loads(archive.read("workspace-config.json"))
                    self.assertEqual(config["profile"], "authenticated-local-staging")
                    self.assertEqual(config["schema"], json.loads(page.locator("#relational-schema").input_value()))
                    self.assertFalse(json.loads(archive.read("bundle-manifest.json"))["public_deployment"])
                    self.assertNotIn("staging_auth/test_settings.py", archive.namelist())
            finally:
                browser.close()
