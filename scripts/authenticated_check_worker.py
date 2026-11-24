"""Internal worker for trusted fresh authenticated exports; all data is synthetic."""
from contextlib import contextmanager, redirect_stdout
import io
import json
import secrets
import sys
import threading
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server, WSGIRequestHandler

import django
django.setup()

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import connections
from playwright.sync_api import expect, sync_playwright

from staging_auth.models import Membership, Record, Workspace

WIDTHS = (360, 768, 1440)
stage = "database initialization"


class AuditFailure(Exception):
    """Only fixed, non-sensitive messages are emitted from explicit checks."""


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def local_server():
    with make_server("127.0.0.1", 0, get_wsgi_application(), handler_class=QuietHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield "http://127.0.0.1:" + str(server.server_port)
        finally:
            server.shutdown()
            thread.join(timeout=5)


def sample(table, ids=None):
    values = {}
    for field in table["fields"]:
        kind = field["type"]
        if kind == "text":
            value = "Audit edited <sample>" if ids is not None else "Audit original <sample>"
        elif kind == "integer":
            value = 9 if ids is not None else 3
        elif kind == "choice":
            value = field["choices"][-1 if ids is not None else 0]
        else:
            value = ids[field["target"]] if ids is not None else None
        values[field["id"]] = value
    return values


def check(engine):
    global stage
    with redirect_stdout(io.StringIO()):
        call_command("migrate", interactive=False, verbosity=0)
        users = {}
        passwords = {}
        for role in ("owner", "editor", "viewer", "outsider"):
            passwords[role] = secrets.token_urlsafe(24)
            users[role] = get_user_model().objects.create_user(username="audit_" + role, password=passwords[role])
        call_command("provision_export", owner=users["owner"].username)
    workspace = Workspace.objects.get(slug="workspace")
    schema = workspace.schema
    tables = schema["tables"]
    for role in ("editor", "viewer"):
        Membership.objects.create(workspace=workspace, user=users[role], role=role)
    other = Workspace.objects.create(slug="separate", title="Separate audit workspace", schema=schema)
    Membership.objects.create(workspace=other, user=users["outsider"], role="owner")
    other_record = Record.objects.create(workspace=other, table_id=tables[0]["id"], data=sample(tables[0]))
    ids, expected, results = {}, {}, []
    unexpected, page_errors = [], []

    def verify_database():
        for table in tables:
            rows = list(Record.objects.filter(workspace=workspace, table_id=table["id"]).order_by("id").values("id", "data"))
            if rows != expected.get(table["id"], []):
                raise AuditFailure("Stored record mismatch")
        other_record.refresh_from_db()
        if other_record.data != sample(tables[0]):
            raise AuditFailure("Separate workspace changed")

    with sync_playwright() as pw, local_server() as url:
        browser = getattr(pw, engine).launch()
        try:
            def context():
                ctx = browser.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
                def route_request(route):
                    parsed = urlsplit(route.request.url)
                    origin = parsed.scheme + "://" + parsed.netloc
                    if origin == url and parsed.path == "/favicon.ico":
                        route.fulfill(status=204, body="")
                    elif origin == url and (parsed.path in ("/", "/login/", "/logout/", "/assets/staging.css")
                                            or parsed.path.startswith("/workspaces/")):
                        route.continue_()
                    else:
                        unexpected.append("unexpected request")
                        route.abort()
                ctx.route("**/*", route_request)
                return ctx

            def sign_in(role):
                global stage
                stage = "sign-in: " + role
                ctx = context()
                page = ctx.new_page()
                page.set_default_timeout(5000)
                page.set_default_navigation_timeout(8000)
                page.on("pageerror", lambda error: page_errors.append("browser error"))
                page.goto(url + "/login/")
                page.locator("#id_username").fill(users[role].username)
                page.locator("#id_password").fill(passwords[role])
                with page.expect_response(lambda response: response.request.method == "POST" and urlsplit(response.url).path == "/login/") as submitted:
                    page.get_by_role("button", name="Sign in", exact=True).click()
                if submitted.value.status != 302:
                    response = submitted.value
                    # Report only HTTP status and known fixed categories, never page
                    # HTML, form values, cookie values or credential-bearing logs.
                    body = response.text()
                    reason = ("csrf" if "CSRF verification failed" in body else
                              "invalid credentials" if "Please enter a correct" in body else
                              "invalid form" if "errorlist" in body else "other response")
                    names = {cookie["name"] for cookie in ctx.cookies()}
                    has_csrf = "creator_staging_csrf" in names
                    raise AuditFailure("Sign-in HTTP " + str(response.status) + "; " + reason +
                                       "; CSRF cookie present: " + str(has_csrf))
                expect(page.get_by_role("heading", name="Your workspaces")).to_be_visible()
                cookies = [cookie for cookie in ctx.cookies() if cookie["name"] == "creator_staging_session"]
                if len(cookies) != 1 or not cookies[0]["httpOnly"] or cookies[0]["sameSite"] != "Strict":
                    raise AuditFailure("Session cookie boundary")
                return ctx, page

            def collection(table):
                return url + "/workspaces/workspace/tables/" + table["id"] + "/"

            def api(table):
                return url + "/api/workspaces/workspace/tables/" + table["id"] + "/"

            def fill(page, table, values):
                for field in table["fields"]:
                    control = page.locator("#id_f_" + field["id"])
                    expect(control).to_be_visible()
                    if not control.evaluate("(el) => el.labels && el.labels.length > 0"):
                        raise AuditFailure("Unlabelled editor control")
                    value = values[field["id"]]
                    if field["type"] in ("choice", "relation"):
                        control.select_option(value="" if value is None else str(value))
                    else:
                        control.fill(str(value))

            stage = "anonymous access"
            anonymous = context()
            page = anonymous.new_page()
            page.goto(collection(tables[0]))
            expect(page.get_by_role("heading", name="Local staging sign-in")).to_be_visible()
            if page.request.get(api(tables[0])).status != 401:
                raise AuditFailure("Anonymous API access")
            anonymous.close()

            stage = "editor login and create"
            editor_context, editor = sign_in("editor")
            for table in tables:
                stage = "editor create"
                name = table["id"]
                editor.goto(collection(table))
                values = sample(table)
                fill(editor, table, values)
                with editor.expect_response(lambda response: response.request.method == "POST" and response.url == collection(table)) as submitted:
                    editor.get_by_role("button", name="Add record", exact=True).click()
                if submitted.value.status != 302:
                    raise AuditFailure("Create form did not redirect")
                expect(editor.locator(".record-grid article")).to_have_count(1)
                row = Record.objects.get(workspace=workspace, table_id=name)
                ids[name] = row.pk
                expected[name] = [{"id": row.pk, "data": values}]
            stage = "verify created records"
            verify_database()

            stage = "editor edit and relation options"
            for table in tables:
                name = table["id"]
                editor.goto(collection(table))
                editor.get_by_role("link", name="Edit record #" + str(ids[name]), exact=True).click()
                values = sample(table, ids)
                fill(editor, table, values)
                with editor.expect_response(lambda response: response.request.method == "POST") as submitted:
                    editor.get_by_role("button", name="Save record", exact=True).click()
                if submitted.value.status != 302:
                    raise AuditFailure("Edit form did not redirect")
                expect(editor.locator(".record-grid article")).to_have_count(1)
                expected[name][0]["data"] = values
                verify_database()
                expect(editor.get_by_role("link", name="Delete record #" + str(ids[name]), exact=True)).to_have_count(0)
                for width in WIDTHS:
                    editor.set_viewport_size({"width": width, "height": 900})
                    if not editor.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"):
                        raise AuditFailure("Horizontal overflow")
                results.append({"table": name, "fields": len(table["fields"]), "viewports": list(WIDTHS)})

            stage = "viewer and workspace isolation"
            viewer_context, viewer = sign_in("viewer")
            viewer.goto(collection(tables[0]))
            expect(viewer.locator(".record-grid article")).to_have_count(1)
            expect(viewer.get_by_role("button", name="Add record", exact=True)).to_have_count(0)
            expect(viewer.get_by_role("link", name="Edit record #" + str(ids[tables[0]["id"]]), exact=True)).to_have_count(0)
            if viewer.request.get(url + "/api/workspaces/separate/schema/").status != 404:
                raise AuditFailure("Cross-workspace access")
            csrf = viewer.locator('input[name="csrfmiddlewaretoken"]').first.input_value()
            denied = viewer.request.post(api(tables[0]), headers={"X-CSRFToken": csrf},
                                         data={"action": "add", "values": sample(tables[0])})
            if denied.status != 403 or denied.json().get("error") != "Operation not permitted":
                raise AuditFailure("Viewer mutation not denied")
            outsider_context, outsider = sign_in("outsider")
            if outsider.request.get(api(tables[0])).status != 404:
                raise AuditFailure("Nonmember workspace access")
            outsider_context.close()

            stage = "owner administration and CSRF"
            owner_context, owner = sign_in("owner")
            owner.goto(collection(tables[0]))
            if owner.request.post(api(tables[0]), data={"action": "delete", "id": ids[tables[0]["id"]]}).status != 403:
                raise AuditFailure("Missing CSRF token accepted")
            exported = owner.request.get(url + "/api/workspaces/workspace/export/")
            if exported.status != 200 or set(exported.json()["tables"]) != set(ids):
                raise AuditFailure("Owner export failed")
            owner.goto(url + "/workspaces/workspace/members/")
            owner.locator("#id_user_id").fill(str(users["editor"].pk))
            owner.locator("#id_role").select_option("editor")
            owner.locator("#id_active").uncheck()
            owner.get_by_role("button", name="Save membership", exact=True).click()
            expect(owner.get_by_text("Your role: owner", exact=True)).to_be_visible()
            if editor.request.get(api(tables[0])).status != 404:
                raise AuditFailure("Revoked membership still permitted")
            editor_context.close()
            viewer_context.close()

            stage = "owner deletion and relationship cleanup"
            for table in tables:
                name = table["id"]
                owner.goto(collection(table))
                owner.get_by_role("link", name="Delete record #" + str(ids[name]), exact=True).click()
                owner.get_by_role("button", name="Confirm deletion", exact=True).click()
                expect(owner.locator(".record-grid article")).to_have_count(0)
                expected[name] = []
                for other_table in tables:
                    for field in other_table["fields"]:
                        if field["type"] == "relation" and field["target"] == name:
                            for row in expected[other_table["id"]]:
                                row["data"][field["id"]] = None
                verify_database()

            stage = "logout and browser errors"
            owner.get_by_role("button", name="Sign out", exact=True).click()
            expect(owner.get_by_role("heading", name="Local staging sign-in")).to_be_visible()
            if owner.request.get(api(tables[0])).status != 401:
                raise AuditFailure("Logout did not revoke session")
            if unexpected or page_errors:
                raise AuditFailure("Unexpected browser activity")
            owner_context.close()
            return {"status": "passed", "browser_version": browser.version, "tables": results,
                    "checks": {"anonymous_denial": True, "session_cookie": True, "editor_create_edit": True,
                               "viewer_read_only": True, "workspace_isolation": True, "csrf": True,
                               "membership_revocation": True, "owner_export_delete": True,
                               "relation_cleanup": True, "logout": True, "no_unexpected_requests": True}}
        finally:
            browser.close()
            connections.close_all()


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("chromium", "firefox", "webkit"):
            raise ValueError("Invalid browser engine")
        print(json.dumps(check(sys.argv[1]), ensure_ascii=True))
    except Exception as exc:
        # A bounded stage name and exception class are sufficient to locate the
        # failing check without exposing a synthetic password or request body.
        print(json.dumps({"status": "failed", "diagnostic": stage + ": " + (str(exc) if type(exc) is AuditFailure else type(exc).__name__)}))
        raise SystemExit(1)
