"""Create a private local staging database backup with no active sessions."""
import json
from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from staging_auth.backup import backup_staging, check_backup, recovery_copy


class Command(BaseCommand):
    help = "Create a private backup or check an existing offline snapshot without restoring it"

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--output", type=Path)
        mode.add_argument("--verify", type=Path)
        mode.add_argument("--recovery-copy", type=Path, help="Trusted stopped backup to copy")
        parser.add_argument("--destination", type=Path, help="New private recovery database; requires --recovery-copy")

    def handle(self, *args, **options):
        source, destination = options["recovery_copy"], options["destination"]
        if (source is None) != (destination is None):
            raise CommandError("Recovery copy requires both --recovery-copy and --destination")
        if source is not None:
            active = Path(settings.DATABASES["default"]["NAME"]).resolve()
            if source.resolve() == active or destination.resolve() == active:
                raise CommandError("Recovery must not use the configured active database")
            try:
                report = recovery_copy(source, destination)
            except (ValueError, OSError, sqlite3.Error) as exc:
                raise CommandError("Recovery copy failed; review the trusted snapshot and new private destination") from exc
            self.stdout.write(json.dumps(report, sort_keys=True))
            self.stdout.write("Private recovery copy prepared. No database activated; review historical permissions before use.")
            return
        if options["verify"] is not None:
            try:
                report = check_backup(options["verify"])
            except (ValueError, OSError, sqlite3.Error) as exc:
                raise CommandError("Snapshot verification failed; review the offline backup") from exc
            self.stdout.write(json.dumps(report, sort_keys=True))
            self.stdout.write("Offline snapshot checks passed. No database restored or changed.")
            return
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Only the local SQLite staging database is supported")
        try:
            report = backup_staging(db["NAME"], options["output"])
        except (ValueError, OSError, sqlite3.Error) as exc:
            raise CommandError("Backup failed; check the database and new private destination") from exc
        self.stdout.write(json.dumps(report, sort_keys=True))
        self.stdout.write("Private snapshot created. It contains account hashes and workspace data; keep it private.")
