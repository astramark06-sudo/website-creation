"""Internal audit worker copied beside a trusted, newly generated application."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
import creator_relational as rel
import server

ROOT = Path(__file__).resolve().parent
WIDTHS = (360, 768, 1440)


@contextmanager
def local_server():
    with ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as http:
        http.RequestHandlerClass = server.make_handler(http.server_port, secrets.token_urlsafe(32), ROOT)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            yield "http://127.0.0.1:" + str(http.server_port)
        finally:
            http.shutdown()
            thread.join(timeout=5)


def sample_values(table, edited=False, ids=None):
    values = {}
    for field in table["fields"]:
        kind = field["type"]
        if kind == "text":
            value = "Audit edited <sample>" if edited else "Audit original <sample>"
        elif kind == "integer":
            value = 9 if edited else 3
        elif kind == "choice":
            value = field["choices"][-1 if edited else 0]
        else:
            value = ids[field["target"]] if edited else None
        values[field["id"]] = value
    return values


def check(engine):
    config = server.config_for(ROOT)
    schema, db_path = config["schema"], ROOT / "workspace.sqlite3"
    tables = schema["tables"]
    ids, expected, results = {}, {}, []
    page_errors, unexpected = [], []

    def assert_database():
        for table in tables:
            name = table["id"]
            if rel.list_records(db_path, schema, name) != expected.get(name, []):
                raise AssertionError("Database contents differ for " + name)

    with sync_playwright() as pw:
        browser = getattr(pw, engine).launch()
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900},
                                          service_workers="block", accept_downloads=False)
            allowed_origin = [None]

            def route_request(route):
                url = urlsplit(route.request.url)
                origin = url.scheme + "://" + url.netloc
                if origin == allowed_origin[0] and url.path == "/favicon.ico" and route.request.method == "GET":
                    route.fulfill(status=204, body="")
                elif (origin == allowed_origin[0] and
                      ((route.request.method == "GET" and url.path in ("/", "/style.css", "/app.js", "/api/session", "/api/records"))
                       or (route.request.method == "POST" and url.path == "/api/records"))):
                    route.continue_()
                else:
                    unexpected.append(url.scheme + "://" + url.netloc + url.path[:100])
                    route.abort()

            context.route("**/*", route_request)
            page = context.new_page()
            page.set_default_timeout(5000)
            page.set_default_navigation_timeout(8000)
            page.on("pageerror", lambda error: page_errors.append(str(error)[:300]))
            page.on("dialog", lambda dialog: dialog.accept())

            def select(table, count):
                if page.locator("#table").input_value() != table["id"]:
                    page.locator("#table").select_option(table["id"])
                expect(page.locator("#status")).to_have_text(str(count) + " records in " + table["label"] + ".")
                expect(page.locator("#submit")).to_be_enabled()
                expect(page.locator("#fields input, #fields select")).to_have_count(len(table["fields"]))

            def fill(table, values):
                for field in table["fields"]:
                    control = page.locator("#field-" + field["id"])
                    expect(control).to_be_enabled()
                    expect(control).to_have_accessible_name(field["label"])
                    value = values[field["id"]]
                    if field["type"] in ("choice", "relation"):
                        control.select_option(value="" if value is None else str(value))
                    else:
                        control.fill(str(value))

            with local_server() as url:
                allowed_origin[0] = url
                page.goto(url)
                expect(page.locator("#title")).to_have_text(config["title"])
                expect(page.locator("#table option")).to_have_count(len(tables))
                # All targets exist before links are added, including cyclic schemas.
                for table in tables:
                    name = table["id"]
                    select(table, 0)
                    values = sample_values(table)
                    fill(table, values)
                    page.locator("#submit").click()
                    select(table, 1)
                    records = rel.list_records(db_path, schema, name)
                    if len(records) != 1 or records[0]["values"] != values:
                        raise AssertionError("Create failed for " + name)
                    ids[name] = records[0]["id"]
                    expected[name] = [{"id": ids[name], "values": values}]
                assert_database()

                for table in tables:
                    name = table["id"]
                    select(table, 1)
                    page.get_by_role("button", name="Edit", exact=True).click()
                    expect(page.locator("#submit")).to_have_text("Save record")
                    values = sample_values(table, edited=True, ids=ids)
                    fill(table, values)
                    page.locator("#submit").click()
                    expect(page.locator("#submit")).to_have_text("Add record")
                    select(table, 1)
                    expected[name][0]["values"] = values
                    assert_database()
                    for width in WIDTHS:
                        page.set_viewport_size({"width": width, "height": 900})
                        if not page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"):
                            raise AssertionError("Horizontal overflow in " + name + " at " + str(width))
                    results.append({"table": name, "fields": len(table["fields"]),
                                    "create_edit": True, "viewports": list(WIDTHS)})
                if page.request.get(url + "/api/records?table=" + tables[0]["id"]).status != 403:
                    raise AssertionError("Unauthenticated read accepted")
                if page.request.post(url + "/api/records", data={"action": "delete", "table": tables[0]["id"], "id": ids[tables[0]["id"]]}).status != 403:
                    raise AssertionError("Unauthenticated write accepted")
                assert_database()

            # Restart the actual server with a new session and check persisted values.
            with local_server() as url:
                allowed_origin[0] = url
                page.goto(url)
                for table in tables:
                    name = table["id"]
                    select(table, 1)
                    page.get_by_role("button", name="Edit", exact=True).click()
                    for field in table["fields"]:
                        value = expected[name][0]["values"][field["id"]]
                        expect(page.locator("#field-" + field["id"])).to_have_value("" if value is None else str(value))
                    page.locator("#clear").click()
                assert_database()
                for table in tables:
                    name = table["id"]
                    select(table, 1)
                    page.get_by_role("button", name="Delete", exact=True).click()
                    select(table, 0)
                    expected[name] = []
                    for other in tables:
                        for field in other["fields"]:
                            if field["type"] == "relation" and field["target"] == name:
                                for item in expected[other["id"]]:
                                    item["values"][field["id"]] = None
                    assert_database()
            if page_errors or unexpected:
                raise AssertionError("Unexpected browser errors or requests: " + repr((page_errors[:5], unexpected[:5])))
            return {"status": "passed", "browser_version": browser.version, "tables": results,
                    "checks": {"create_edit_all_tables": True, "all_fields": True,
                               "restart_persistence": True, "delete_and_clear_references": True,
                               "session_boundaries": True, "no_page_errors": True,
                               "no_unexpected_browser_requests": True}}
        finally:
            browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("chromium", "firefox", "webkit"):
        raise SystemExit("Invalid audit engine")
    print(json.dumps(check(sys.argv[1]), ensure_ascii=True))
