"""Verify that optional vision mode sends only reduced, consented image data."""
import base64
import json
import unittest
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright
from browser_engine import launch_browser
from scripts.creator_studio import make_handler
from scripts.creator_vision import jpeg_dimensions
from test_studio import serve
from test_visual_reference import synthetic_png


class VisionBrowserTests(unittest.TestCase):
    def test_opt_in_reduced_image_request(self):
        captured = []
        def fake_plan(image, title, objective, authorized, model):
            captured.append((jpeg_dimensions(base64.b64decode(image)), authorized, model))
            return {"selection": {"structure": "overview"}, "limitations": ["Simulated model response"]}
        with patch("scripts.creator_studio.vision_plan", side_effect=fake_plan):
            with sync_playwright() as pw, serve(lambda port: make_handler(port, "vision-test", vision_model="vision:local")) as url:
                browser = launch_browser(pw)
                try:
                    page = browser.new_page()
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    page.locator("#visual-reference-panel > summary").click()
                    page.locator("#visual-file").set_input_files({"name": "sample.png", "mimeType": "image/png", "buffer": synthetic_png()})
                    page.locator("#visual-authorized").check()
                    page.locator("#vision-analyze").click()
                    expect(page.locator("#status")).to_contain_text("confirm local model consent")
                    self.assertEqual(captured, [])
                    page.locator("#vision-consent").check()
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    with page.expect_request(lambda req: req.url.endswith("/api/vision-reference")) as sent:
                        page.locator("#vision-analyze").click()
                    payload = json.loads(sent.value.post_data)
                    self.assertEqual(set(payload), {"image", "title", "objective", "authorized"})
                    self.assertLessEqual(len(base64.b64decode(payload["image"])), 65536)
                    expect(page.locator("#status")).to_contain_text("Existing draft unchanged")
                    self.assertEqual(captured, [((120, 60), True, "vision:local")])
                finally:
                    browser.close()
