"""Real browser tests for studio and generated sites."""
import contextlib
import http.server
import json
from pathlib import Path
import tempfile
import threading
import unittest

from browser_engine import launch_browser
import zipfile

from playwright.sync_api import expect, sync_playwright
from scripts.creator_project import read_spec
from scripts.creator_studio import make_handler

ROOT = Path(__file__).resolve().parents[2]


@contextlib.contextmanager
def serve(factory):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    server.RequestHandlerClass = factory(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class QuietFiles(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class StudioBrowserTests(unittest.TestCase):
    def test_edit_preview_export_and_task_persistence(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            browser = launch_browser(pw)
            context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
            try:
                page = context.new_page()
                with serve(lambda port: make_handler(port, "browser-test-token")) as url:
                    page.goto(url)
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    page.get_by_label("Website name").fill("Original browser test")
                    page.get_by_label("Color theme").select_option("blue")
                    page.get_by_role("button", name="Add page", exact=True).click()
                    expect(page.locator(".page-card")).to_have_count(3)
                    page.locator(".page-card").nth(2).get_by_label("Page title").fill("New guide")
                    page.locator("#preview-page").select_option("page-2")
                    page.locator("#viewport").select_option("390px")
                    page.get_by_role("button", name="Refresh preview").click()
                    expect(page.locator("#status")).to_contain_text("Preview generated")
                    frame = page.frame_locator("#frame")
                    expect(frame.get_by_role("heading", name="New guide", exact=True)).to_be_visible()
                    expect(page.locator("#frame")).to_have_css("width", "390px")
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Build and export ZIP").click()
                    path = Path(tmp) / "project.zip"
                    download.value.save_as(path)
                    with zipfile.ZipFile(path) as archive:
                        spec = json.loads(archive.read("project.json"))
                        self.assertEqual(spec["title"], "Original browser test")
                        self.assertEqual(len(spec["pages"]), 3)
                        self.assertFalse(any(spec["review"].values()))
                        for name in ("index.html", "workspace.html", "page-2.html", "style.css", "app.js", "favicon.svg"):
                            target = Path(tmp) / "site" / name
                            target.parent.mkdir(exist_ok=True)
                            target.write_bytes(archive.read("site/" + name))
                with serve(lambda port: lambda *args, **kw: QuietFiles(*args, directory=str(Path(tmp) / "site"), **kw)) as url:
                    page.goto(url)
                    page.get_by_role("link", name="Workspace", exact=True).click()
                    expect(page.get_by_role("heading", name="Task workspace")).to_be_visible()
                    page.get_by_label("New task").fill("Browser-tested task")
                    page.get_by_role("button", name="Add task").click()
                    expect(page.locator("#status")).to_have_text("1 tasks, 0 completed.")
                    page.get_by_role("button", name="Complete: Browser-tested task").click()
                    expect(page.locator("#status")).to_have_text("1 tasks, 1 completed.")
                    page.reload()
                    expect(page.locator("#status")).to_have_text("1 tasks, 1 completed.")
                    page.get_by_role("button", name="Remove: Browser-tested task").click()
                    expect(page.locator("#status")).to_have_text("0 tasks, 0 completed.")
            finally:
                context.close()
                browser.close()

    def test_tool_center(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "test-token")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                page.locator("#tool-center summary").click()
                expect(page.locator("#tool-status")).to_have_text("Read-only catalogue ready.")
                page.locator("#tool-profile").select_option("marketing")
                page.get_by_role("button", name="Propose development plan").click()
                expect(page.locator("#tool-results")).to_contain_text("proposal-only")
                page.get_by_label("Search component sources").fill("templates")
                page.get_by_label("Import policy").select_option("reference-only")
                page.get_by_role("button", name="Search sources").click()
                expect(page.locator("#tool-results")).to_contain_text("reference-only")
                expect(page.locator("#tool-status")).to_contain_text("matching sources")
            finally:
                browser.close()

    def test_multipage_reference_requires_consent_and_preserves_originality(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "reference-test")) as url:
            browser = launch_browser(pw)
            try:
                page = browser.new_page(accept_downloads=True)
                page.goto(url)
                expect(page.locator("#status")).to_contain_text("Preview generated")
                files = [{"name": "private-one.html", "mimeType": "text/html", "buffer": b"<nav>Private reference title</nav>"},
                         {"name": "private-two.html", "mimeType": "text/html", "buffer": b"<article><img src='private.png'></article>"},
                         {"name": "private-three.html", "mimeType": "text/html", "buffer": b"<table><tr><td>Private cell</td></tr></table>"}]
                picker = page.locator("#reference")
                button = page.get_by_role("button", name="Analyze reference and propose draft")
                picker.set_input_files(files)
                button.click()
                expect(page.locator("#status")).to_contain_text("confirm permission")
                page.locator("#reference-authorized").check()
                page.once("dialog", lambda dialog: dialog.dismiss())
                button.click()
                expect(page.locator("#status")).to_contain_text("Existing draft unchanged")
                expect(page.locator(".page-card")).to_have_count(2)
                picker.set_input_files(files)
                page.locator("#reference-authorized").check()
                page.once("dialog", lambda dialog: dialog.accept())
                button.click()
                expect(page.locator(".page-card")).to_have_count(3)
                expect(page.locator("#status")).to_contain_text("Original reference-informed draft created")
                report = json.loads(page.locator("#reference-report").text_content())
                self.assertEqual(report["observations"]["reference_count"], 3)
                with page.expect_download() as download:
                    page.get_by_role("button", name="Build and export ZIP").click()
                with zipfile.ZipFile(download.value.path()) as archive:
                    spec = json.loads(archive.read("project.json"))
                    self.assertEqual([p["slug"] for p in spec["pages"]], ["home", "topic-2", "topic-3"])
                    self.assertFalse(any(spec["review"].values()))
                    for secret in ("private-one", "Private reference title", "private.png", "Private cell"):
                        self.assertNotIn(secret, json.dumps(spec) + json.dumps(report))
                headers = {"Origin": url, "X-Creator-Token": "reference-test"}
                response = page.request.post(url + "/api/reference", headers=headers,
                                             data={"sources": ["one", "two"], "title": "Name", "objective": "Goal", "authorized": False})
                self.assertEqual(response.status, 400)
            finally:
                browser.close()

    def test_request_boundaries(self):
        with sync_playwright() as pw, serve(lambda port: make_handler(port, "test-token")) as url:
            request = pw.request.new_context()
            try:
                spec = read_spec(ROOT / "projects" / "example.json")
                payload = {"spec": spec, "slug": "home"}
                self.assertEqual(request.post(url + "/api/preview", data=payload).status, 403)
                headers = {"Origin": url, "X-Creator-Token": "test-token"}
                self.assertEqual(request.post(url + "/api/preview", data=payload, headers=headers).status, 200)
                self.assertEqual(request.post(url + "/api/preview", data={"spec": spec, "slug": "../other"}, headers=headers).status, 400)
                self.assertEqual(request.get(url + "/AGENTS.md").status, 404)
            finally:
                request.dispose()


if __name__ == "__main__":
    unittest.main()
