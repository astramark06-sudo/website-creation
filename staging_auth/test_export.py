"""Exercise actual standalone generated source and migrations in an isolated subprocess."""
import io
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import zipfile

from django.test import SimpleTestCase

from scripts.creator_authenticated_export import export_authenticated
from scripts.creator_relational import read_schema

ROOT = Path(__file__).resolve().parents[1]
CHECK = r"""
import django
django.setup()
import secrets
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from staging_auth.models import Workspace, Record
password = secrets.token_urlsafe(24)
user = get_user_model().objects.create_user(username="synthetic_owner", password=password)
call_command("provision_export", owner=user.username)
workspace = Workspace.objects.get(slug="workspace")
assert workspace.title == "Exported example"
assert workspace.description == "Synthetic standalone test"
assert len(workspace.schema["tables"]) == 2
client = Client(HTTP_HOST="127.0.0.1", enforce_csrf_checks=True)
assert client.get("/api/workspaces/workspace/schema/").status_code == 401
assert client.get("/login/").status_code == 200
csrf = client.cookies["creator_staging_csrf"].value
assert client.post("/login/", {"username": user.username, "password": password,
                              "csrfmiddlewaretoken": csrf}).status_code == 302
assert b"Synthetic standalone test" in client.get("/workspaces/workspace/").content
csrf = client.cookies["creator_staging_csrf"].value
assert client.post("/workspaces/workspace/tables/categories/", {"f_name": "Synthetic category",
                                                               "csrfmiddlewaretoken": csrf}).status_code == 302
assert Record.objects.get(workspace=workspace).data == {"name": "Synthetic category"}
try:
    call_command("provision_export", owner=user.username)
except CommandError:
    pass
else:
    raise AssertionError("Provisioning overwrote workspace")
assert Workspace.objects.count() == 1
"""


class ExportIntegrationTests(SimpleTestCase):
    def test_standalone_bundle(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        bundle = export_authenticated("Exported example", "Synthetic standalone test", schema)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                for name in archive.namelist():
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.update(CREATOR_STAGING_SECRET=secrets.token_urlsafe(48),
                       CREATOR_STAGING_DB=str(root / "test.sqlite3"), DJANGO_SETTINGS_MODULE="staging_auth.settings")
            for command in ([sys.executable, "-E", "-m", "django", "migrate", "--noinput"],
                            [sys.executable, "-E", "-c", CHECK]):
                proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
