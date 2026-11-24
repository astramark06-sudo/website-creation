"""Exercise local attempt limiting and private backup with synthetic data."""
from contextlib import closing
import io
from pathlib import Path
import secrets
import sqlite3
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase

from scripts.creator_relational import read_schema
from .backup import backup_staging, check_backup
from .login_guard import MAX_ATTEMPTS, reserve_attempt
from .models import LoginBudget, Membership, Record, Workspace

ROOT = Path(__file__).resolve().parents[1]


class LoginGuardTests(TestCase):
    def test_fixed_window_and_clock_rollback(self):
        for _ in range(MAX_ATTEMPTS):
            self.assertEqual(reserve_attempt(1000), 0)
        self.assertEqual(reserve_attempt(1001), 59)
        self.assertEqual(reserve_attempt(999), 60)
        self.assertEqual(LoginBudget.objects.count(), 1)
        self.assertEqual(LoginBudget.objects.get(pk=1).attempts, MAX_ATTEMPTS)
        self.assertEqual(reserve_attempt(1060), 0)
        self.assertEqual(LoginBudget.objects.get(pk=1).attempts, 1)

    def test_http_attempt_limit_with_csrf(self):
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user(username="synthetic", password=password)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/login/").status_code, 200)
        token = client.cookies["creator_staging_csrf"].value
        with patch("staging_auth.login_guard.time.time", return_value=1000):
            self.assertEqual(client.post("/login/", {"username": user.username, "password": password}).status_code, 403)
            self.assertFalse(LoginBudget.objects.exists())
            for _ in range(MAX_ATTEMPTS):
                response = client.post("/login/", {"username": "unknown", "password": "invalid",
                                                   "csrfmiddlewaretoken": token})
                self.assertEqual(response.status_code, 200)
            response = client.post("/login/", {"username": user.username, "password": password,
                                               "csrfmiddlewaretoken": token})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "60")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        with patch("staging_auth.login_guard.time.time", return_value=1060):
            self.assertEqual(client.post("/login/", {"username": user.username, "password": password,
                                                    "csrfmiddlewaretoken": token}).status_code, 302)

    def test_database_failure_fails_closed(self):
        from django.db import OperationalError
        with patch("staging_auth.login_guard.reserve_attempt", side_effect=OperationalError("synthetic")):
            self.assertEqual(self.client.post("/login/", {"username": "synthetic", "password": "invalid"}).status_code, 503)


class BackupTests(TransactionTestCase):
    def test_real_snapshot_retains_data_but_not_sessions(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        user = get_user_model().objects.create_user(username="synthetic_owner")
        workspace = Workspace.objects.create(slug="synthetic", title="Synthetic", schema=schema)
        Membership.objects.create(workspace=workspace, user=user, role="owner")
        Record.objects.create(workspace=workspace, table_id="categories", data={"name": "Synthetic record"})
        client = Client()
        client.force_login(user)
        self.assertEqual(Session.objects.count(), 1)
        session_key = Session.objects.get().session_key
        source = Path(connection.settings_dict["NAME"])
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "backup.sqlite3"
            out = io.StringIO()
            call_command("backup_staging", output=target, stdout=out)
            with closing(sqlite3.connect(target)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM django_session").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM staging_auth_record").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM staging_auth_membership").fetchone()[0], 1)
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(Session.objects.count(), 1)
            self.assertEqual(Record.objects.count(), 1)
            before = target.read_bytes()
            self.assertNotIn(session_key.encode("ascii"), before)
            expected = {"workspaces": 1, "records": 1, "sessions_retained": 0}
            self.assertEqual(check_backup(target), expected)
            verification = io.StringIO()
            call_command("backup_staging", verify=target, stdout=verification)
            self.assertIn("Offline snapshot checks passed", verification.getvalue())
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ["backup.sqlite3"])
            with self.assertRaises(ValueError):
                check_backup(source)
            self.assertTrue(Session.objects.filter(session_key=session_key).exists())
            with self.assertRaises(CommandError):
                call_command("backup_staging", output=target, stdout=out)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(backup_staging(source, Path(temp) / "second.sqlite3"),
                             {"workspaces": 1, "records": 1, "sessions_retained": 0})

    def test_invalid_source_cleanup_and_existing_file_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "invalid.sqlite3"
            target = Path(temp) / "backup.sqlite3"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE unrelated (id INTEGER)")
            with self.assertRaises(ValueError):
                backup_staging(source, target)
            self.assertFalse(target.exists())
            target.write_bytes(b"untouched")
            with self.assertRaises(FileExistsError):
                backup_staging(source, target)
            self.assertEqual(target.read_bytes(), b"untouched")
            with self.assertRaises(sqlite3.Error):
                check_backup(target)
            with self.assertRaises(ValueError):
                check_backup(Path(temp) / "missing.sqlite3")
            sidecar = Path(str(source) + "-wal")
            sidecar.write_bytes(b"synthetic")
            with self.assertRaisesRegex(ValueError, "sidecar"):
                check_backup(source)
            self.assertEqual(sidecar.read_bytes(), b"synthetic")
