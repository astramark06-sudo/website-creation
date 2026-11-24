"""Create a private local staging database backup with no active sessions."""
import json
from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from staging_auth.backup import backup_staging


class Command(BaseCommand):
    help = "Back up a stopped local staging database to a new private SQLite file"

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, required=True)

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Only the local SQLite staging database is supported")
        try:
            report = backup_staging(db["NAME"], options["output"])
        except (ValueError, OSError, sqlite3.Error) as exc:
            raise CommandError("Backup failed; check the database and new private destination") from exc
        self.stdout.write(json.dumps(report, sort_keys=True))
        self.stdout.write("Private snapshot created. It contains account hashes and workspace data; keep it private.")
