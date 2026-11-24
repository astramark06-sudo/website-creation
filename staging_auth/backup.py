"""Private, checked SQLite snapshot for stopped local staging workspaces."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3

REQUIRED_TABLES = {
    "django_migrations", "django_session", "auth_user", "staging_auth_workspace",
    "staging_auth_membership", "staging_auth_record", "staging_auth_membershipevent",
    "staging_auth_loginbudget",
}


def verify_snapshot(db):
    if [row[0] for row in db.execute("PRAGMA integrity_check")] != ["ok"]:
        raise ValueError("Database integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Database foreign-key check failed")
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED_TABLES <= tables:
        raise ValueError("Not an initialized current staging database")


def backup_staging(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file() or destination.suffix != ".sqlite3":
        raise ValueError("Choose an existing source and new .sqlite3 destination")
    # Create exclusively before connecting. Never overwrite existing files.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as original:
            with closing(sqlite3.connect(destination, timeout=5)) as copy:
                original.backup(copy)
                verify_snapshot(copy)
                with copy:
                    # Restored backups must never resurrect old authenticated sessions.
                    copy.execute("DELETE FROM django_session")
                verify_snapshot(copy)
                if copy.execute("SELECT count(*) FROM django_session").fetchone()[0] != 0:
                    raise ValueError("Snapshot retained sessions")
                report = {
                    "workspaces": copy.execute("SELECT count(*) FROM staging_auth_workspace").fetchone()[0],
                    "records": copy.execute("SELECT count(*) FROM staging_auth_record").fetchone()[0],
                    "sessions_retained": 0,
                }
    except BaseException:
        destination.unlink()
        raise
    return report
