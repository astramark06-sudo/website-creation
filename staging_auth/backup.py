"""Private, checked SQLite snapshot for stopped local staging workspaces."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import shutil

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


def snapshot_report(db):
    verify_snapshot(db)
    if db.execute("SELECT count(*) FROM django_session").fetchone()[0] != 0:
        raise ValueError("Snapshot retained sessions")
    return {
        "workspaces": db.execute("SELECT count(*) FROM staging_auth_workspace").fetchone()[0],
        "records": db.execute("SELECT count(*) FROM staging_auth_record").fetchone()[0],
        "sessions_retained": 0,
    }


def check_backup(source):
    """Check an offline, private snapshot without opening it for writes."""
    source = Path(source).resolve()
    if not source.is_file() or source.suffix != ".sqlite3":
        raise ValueError("Choose an existing offline .sqlite3 snapshot")
    if any(os.path.lexists(str(source) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Snapshot has SQLite sidecar files; stop and review it")
    # Immutable mode is appropriate only for a stopped, standalone snapshot.
    # It prevents writes, locking, and creation of SQLite sidecar files.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only = ON")
        return snapshot_report(db)


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
                # Scrub session data from the snapshot's database pages as well as
                # its logical rows. Rebuild to discard previously freed pages.
                copy.execute("PRAGMA secure_delete = ON")
                with copy:
                    copy.execute("DELETE FROM django_session")
                copy.execute("VACUUM")
                report = snapshot_report(copy)
    except BaseException:
        destination.unlink()
        raise
    return report


def recovery_copy(source, destination):
    """Prepare a new private database for a separate, stopped recovery installation.

    The source must be a trusted standalone snapshot. This does not activate
    the database, alter settings, migrate its schema, or reconcile old roles.
    """
    source = Path(source).resolve()
    destination = Path(destination)
    if destination.suffix != ".sqlite3":
        raise ValueError("Choose a new .sqlite3 recovery destination")
    if not destination.parent.is_dir():
        raise ValueError("Choose an existing private recovery directory")
    if any(os.path.lexists(str(destination) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Recovery destination has existing SQLite sidecars")
    expected = check_backup(source)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        actual = check_backup(destination)
        if actual != expected:
            raise ValueError("Recovery copy differs from checked snapshot")
        # Compare bytes in bounded chunks, not merely row counts.
        with source.open("rb") as original, destination.open("rb") as copied:
            while True:
                block = original.read(1024 * 1024)
                if block != copied.read(1024 * 1024):
                    raise ValueError("Recovery copy differs from checked snapshot")
                if not block:
                    break
        return actual
    except BaseException:
        destination.unlink()
        raise
