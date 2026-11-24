"""Real browser screenshot analysis of a synthetic, original local image."""
import json
import struct
import unittest
import zlib
from playwright.sync_api import sync_playwright, expect
from scripts.creator_studio import make_handler
from test_studio import serve


def synthetic_png():
    def chunk(name, payload):
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload))
    width, height = 120, 60
    scanlines = (b"\x00" + bytes((220, 100, 60)) * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class VisualBrowserTests(unittest.TestCase):
    def test_screenshot_stays_local(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "visual-test")) as url:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.locator("#visual-reference-panel summary").click()
                page.locator("#visual-file").set_input_files({"name": "synthetic.png", "mimeType": "image/png", "buffer": synthetic_png()})
                page.locator("#visual-authorized").check()
                page.on("dialog", lambda dialog: dialog.accept())
                with page.expect_request(lambda req: req.url.endswith("/api/visual-reference")) as sent:
                    page.locator("#visual-analyze").click()
                payload = json.loads(sent.value.post_data)
                self.assertEqual(set(payload), {"observations", "title", "objective", "authorized"})
                self.assertEqual(payload["observations"]["shape"], "landscape")
                self.assertEqual(payload["observations"]["palette_family"], "warm")
                expect(page.locator("#status")).to_contain_text("Screenshot-informed draft created")
                expect(page.locator("#theme")).to_have_value("plum")
                expect(page.locator("#layout")).to_have_value("editorial")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
