"""Verify concurrent revocation and protected writes using independent DB connections."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections, transaction
from django.test import TransactionTestCase

from scripts.creator_access import Action
from scripts.creator_relational import read_schema
from .models import Membership, Record, Workspace
from .services import NotMember, authorized_workspace, change_record, set_member

ROOT = Path(__file__).resolve().parents[1]


class RevocationConcurrencyTests(TransactionTestCase):
    def test_revocation_commits_before_waiting_write(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        workspace = Workspace.objects.create(slug="test_workspace", title="Local test", schema=schema)
        owner = get_user_model().objects.create_user(username="test_owner")
        editor = get_user_model().objects.create_user(username="test_editor")
        Membership.objects.create(workspace=workspace, user=owner, role="owner")
        Membership.objects.create(workspace=workspace, user=editor, role="editor")
        revoked_in_transaction, writer_started, allow_commit = Event(), Event(), Event()

        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    actor = get_user_model().objects.get(pk=owner.pk)
                    checked = authorized_workspace(actor, workspace.slug, Action.MANAGE_MEMBERS)
                    set_member(checked, actor, {"user_id": editor.pk, "role": "editor", "active": False})
                    revoked_in_transaction.set()
                    if not allow_commit.wait(5):
                        raise AssertionError("Test synchronization timed out")
            finally:
                connections.close_all()

        def write():
            close_old_connections()
            try:
                writer_started.set()
                try:
                    with transaction.atomic():
                        user = get_user_model().objects.get(pk=editor.pk)
                        checked = authorized_workspace(user, workspace.slug, Action.CREATE_RECORD)
                        change_record(checked, "categories", {"action": "add", "values": {"name": "Not allowed"}})
                    return "written"
                except NotMember:
                    return "revoked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            revocation = executor.submit(revoke)
            try:
                self.assertTrue(revoked_in_transaction.wait(5))
                writer = executor.submit(write)
                self.assertTrue(writer_started.wait(5))
            finally:
                allow_commit.set()
            revocation.result(timeout=8)
            self.assertEqual(writer.result(timeout=8), "revoked")
        self.assertFalse(Record.objects.filter(workspace=workspace).exists())
