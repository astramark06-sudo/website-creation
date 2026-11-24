"""Local Django integration tests with synthetic accounts and records."""
import json
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.core.management import call_command
from django.core.management.base import CommandError

from scripts.creator_relational import read_schema
from .models import Workspace, Membership, MembershipEvent, Record

ROOT = Path(__file__).resolve().parents[1]


class AuthenticatedStagingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schema = read_schema(ROOT / "projects" / "relational-example.json")
        cls.a = Workspace.objects.create(slug="alpha", title="Alpha", schema=cls.schema)
        cls.b = Workspace.objects.create(slug="beta", title="Beta", schema=cls.schema)
        users = get_user_model().objects
        cls.owner = users.create_user(username="owner")
        cls.editor = users.create_user(username="editor")
        cls.viewer = users.create_user(username="viewer")
        cls.other = users.create_user(username="other")
        for user, role in [(cls.owner, "owner"), (cls.editor, "editor"), (cls.viewer, "viewer")]:
            Membership.objects.create(workspace=cls.a, user=user, role=role)
        Membership.objects.create(workspace=cls.b, user=cls.other, role="owner")
        cls.cat_a = Record.objects.create(workspace=cls.a, table_id="categories", data={"name": "Alpha category"})
        cls.cat_b = Record.objects.create(workspace=cls.b, table_id="categories", data={"name": "Beta category"})
        cls.item = Record.objects.create(workspace=cls.a, table_id="items",
                                         data={"name": "Item", "quantity": 1, "state": "Available", "category": cls.cat_a.pk})

    def api(self, slug="alpha", table="categories"):
        return f"/api/workspaces/{slug}/tables/{table}/"

    def post(self, path, data):
        return self.client.post(path, data, content_type="application/json")

    def test_anonymous_and_cross_workspace(self):
        self.assertEqual(self.client.get(self.api()).status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.api()).status_code, 404)
        self.assertEqual(self.client.get(self.api("missing")).status_code, 404)
        self.assertNotContains(self.client.get("/"), "Alpha")
        self.assertContains(self.client.get("/"), "Beta")
        self.assertEqual(self.client.get("/api/workspaces/alpha/export/").status_code, 404)

    def test_viewer_read_only(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.api()).json()["records"], [{"id": self.cat_a.pk, "values": {"name": "Alpha category"}}])
        for data in [{"action": "add", "values": {"name": "No"}},
                     {"action": "edit", "id": self.cat_a.pk, "values": {"name": "No"}},
                     {"action": "delete", "id": self.cat_a.pk}]:
            self.assertEqual(self.post(self.api(), data).status_code, 403)
        self.assertEqual(self.client.get("/api/workspaces/alpha/members/").status_code, 403)
        self.assertEqual(self.client.get("/api/workspaces/alpha/export/").status_code, 403)

    def test_editor_record_scope_and_relations(self):
        self.client.force_login(self.editor)
        values = {"name": "Pens", "quantity": 7, "state": "Available", "category": self.cat_a.pk}
        response = self.post(self.api(table="items"), {"action": "add", "values": values})
        self.assertEqual(response.status_code, 200)
        item = response.json()["id"]
        self.assertEqual(self.post(self.api(table="items"), {"action": "edit", "id": item, "values": {**values, "category": self.cat_b.pk}}).status_code, 400)
        self.assertEqual(self.post(self.api(), {"action": "edit", "id": self.cat_b.pk, "values": {"name": "No"}}).status_code, 404)
        self.assertEqual(self.post(self.api(table="items"), {"action": "delete", "id": item}).status_code, 403)
        self.assertEqual(Record.objects.get(pk=item).data, values)
        self.cat_b.refresh_from_db()
        self.assertEqual(self.cat_b.data, {"name": "Beta category"})

    def test_owner_deletion_clears_only_local_links_and_export(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.post(self.api(), {"action": "delete", "id": self.cat_a.pk}).status_code, 200)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.data["category"])
        self.assertTrue(Record.objects.filter(pk=self.cat_b.pk).exists())
        response = self.client.get("/api/workspaces/alpha/export/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Beta category", response.content.decode())
        self.assertEqual(response.json()["tables"]["items"][0]["values"]["category"], None)

    def test_membership_changes_and_last_owner(self):
        self.client.force_login(self.owner)
        path = "/api/workspaces/alpha/members/"
        self.assertEqual(self.post(path, {"user_id": self.owner.pk, "role": "viewer", "active": True}).status_code, 400)
        self.assertEqual(MembershipEvent.objects.count(), 0)
        editor_client = Client()
        editor_client.force_login(self.editor)
        self.assertEqual(editor_client.get(self.api()).status_code, 200)
        self.assertEqual(self.post(path, {"user_id": self.editor.pk, "role": "editor", "active": False}).status_code, 200)
        self.assertEqual(editor_client.get(self.api()).status_code, 404)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.assertEqual(self.post(path, {"user_id": self.viewer.pk, "role": "owner", "active": True}).status_code, 200)
        self.assertEqual(self.post(path, {"user_id": self.owner.pk, "role": "viewer", "active": True}).status_code, 200)
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_session_login_csrf_logout(self):
        password = secrets.token_urlsafe(24)
        self.owner.set_password(password)
        self.owner.save(update_fields=["password"])
        client = Client(enforce_csrf_checks=True)
        login = client.get("/login/")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.headers["Cache-Control"], "no-store")
        csrf = client.cookies["creator_staging_csrf"].value
        self.assertEqual(client.post("/login/", {"username": self.owner.username, "password": password}).status_code, 403)
        response = client.post("/login/", {"username": self.owner.username, "password": password, "csrfmiddlewaretoken": csrf})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies["creator_staging_session"]["httponly"])
        self.assertEqual(client.get(self.api()).status_code, 200)
        self.assertEqual(client.post(self.api(), {"action": "add", "values": {"name": "No"}}, content_type="application/json").status_code, 403)
        csrf = client.cookies["creator_staging_csrf"].value
        self.assertEqual(client.post(self.api(), {"action": "add", "values": {"name": "Yes"}}, content_type="application/json", HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(client.get("/logout/").status_code, 405)
        self.assertEqual(client.post("/logout/", {"csrfmiddlewaretoken": csrf}).status_code, 302)
        self.assertEqual(client.get(self.api()).status_code, 401)

    def test_malformed_requests_and_inactive_user(self):
        self.client.force_login(self.owner)
        for payload in [{"action": "add", "values": {"name": "No"}, "role": "owner"},
                        {"action": [], "values": {}}, {"action": "delete", "id": True}]:
            self.assertEqual(self.post(self.api(), payload).status_code, 400)
        self.assertEqual(self.client.post(self.api(), '{"action":"add","action":"delete"}', content_type="application/json").status_code, 400)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.api()).status_code, 401)

    def test_provision_command_no_overwrite(self):
        args = {"slug": "new_workspace", "title": "New", "schema": str(ROOT / "projects" / "relational-example.json"), "owner": self.owner.username}
        call_command("provision_workspace", **args)
        workspace = Workspace.objects.get(slug="new_workspace")
        self.assertTrue(Membership.objects.filter(workspace=workspace, user=self.owner, role="owner").exists())
        with self.assertRaises(CommandError):
            call_command("provision_workspace", **args)
        self.assertEqual(Workspace.objects.filter(slug="new_workspace").count(), 1)
