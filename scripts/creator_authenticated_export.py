"""Package an explicitly local authenticated application from a validated schema.

The bundle contains only reviewed source files and configuration, never accounts,
session data, database contents, or an automatically generated deployment.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

try:
    from .creator_relational import validate_schema, read_schema, require_text
except ImportError:
    from creator_relational import validate_schema, read_schema, require_text

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "scripts/creator_access.py",
    "scripts/creator_relational.py",
    "staging_auth/__init__.py",
    "staging_auth/requirements.txt",
    "staging_auth/settings.py",
    "staging_auth/middleware.py",
    "staging_auth/models.py",
    "staging_auth/services.py",
    "staging_auth/views.py",
    "staging_auth/html_views.py",
    "staging_auth/forms.py",
    "staging_auth/urls.py",
    "staging_auth/login_guard.py",
    "staging_auth/backup.py",
    "staging_auth/staging.css",
    "staging_auth/migrations/__init__.py",
    "staging_auth/migrations/0001_initial.py",
    "staging_auth/migrations/0002_workspace_description.py",
    "staging_auth/migrations/0003_loginbudget.py",
    "staging_auth/management/__init__.py",
    "staging_auth/management/commands/__init__.py",
    "staging_auth/management/commands/provision_workspace.py",
    "staging_auth/management/commands/provision_export.py",
    "staging_auth/management/commands/backup_staging.py",
    "staging_auth/templates/staging_auth/base.html",
    "staging_auth/templates/staging_auth/home.html",
    "staging_auth/templates/staging_auth/login.html",
    "staging_auth/templates/staging_auth/workspace.html",
    "staging_auth/templates/staging_auth/collection.html",
    "staging_auth/templates/staging_auth/edit.html",
    "staging_auth/templates/staging_auth/delete.html",
    "staging_auth/templates/staging_auth/members.html",
)
README = """# Local authenticated staging application

This is a separate local development bundle, not production hosting. Use synthetic data and dedicated local test accounts. Do not expose it to the internet.

Use Python 3.10 or newer in a private virtual environment. Install the optional framework using:

    python -m pip install -r staging_auth/requirements.txt

Create a private .local-staging directory. Set CREATOR_STAGING_SECRET to a locally generated random value of at least 50 characters in your environment. Keep it private and outside version control. Set CREATOR_STAGING_DB only if you need a different private SQLite file.

Initialize the database, create a local test account interactively, provision the exported workspace, and start the loopback development server:

    python -m django migrate --settings=staging_auth.settings
    python -m django createsuperuser --settings=staging_auth.settings
    python -m django provision_export --owner TEST_USERNAME --settings=staging_auth.settings
    python -m django runserver 127.0.0.1:8769 --noreload --settings=staging_auth.settings

Replace TEST_USERNAME with your existing local test account username. No credentials are included in this bundle. The framework superuser has no workspace access until provisioned. A small installation-wide login attempt budget protects local staging only. No production account recovery, TLS, distributed rate limiting, MFA, hosting or public registration is configured.

The exported workspace uses schema-aware scoped JSON records in SQLite, not the physical-table engine of the simpler relational export. The schema is fixed after provisioning. The manifest identifies the generated source and configuration; it is not a signed security certification. Keep the database and secret out of shared files. Stop the server before running python -m django backup_staging --output PRIVATE_NEW.sqlite3 --settings=staging_auth.settings. The checked snapshot contains private workspace data and account hashes but no active sessions.
"""


def export_authenticated(title, description, schema):
    config = {
        "version": 1, "profile": "authenticated-local-staging",
        "title": require_text(title, "Workspace title", 120),
        "description": require_text(description, "Description", 1000),
        "schema": validate_schema(schema),
    }
    files = {name: (ROOT / name).read_bytes() for name in SOURCE_FILES}
    files["scripts/__init__.py"] = b""
    files["workspace-config.json"] = (json.dumps(config, ensure_ascii=False, sort_keys=True,
                                                 separators=(",", ":")) + "\n").encode("utf-8")
    files[".gitignore"] = b".local-staging/\n.env\n.env.*\n*.sqlite3\n*.sqlite3-*\n__pycache__/\n.venv/\n"
    files["README.md"] = README.encode("utf-8")
    manifest = {
        "version": 1,
        "profile": "authenticated-local-staging",
        "public_deployment": False,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["bundle-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            # Fixed metadata permits reproducible exports of the same inputs.
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = export_authenticated(args.title, args.description, read_schema(args.schema))
        with args.output.open("xb") as stream:
            stream.write(data)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
