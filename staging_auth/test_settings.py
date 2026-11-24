"""Ephemeral file-backed test configuration; never use for actual applications."""
import os
import secrets
import tempfile
from pathlib import Path

os.environ.setdefault("CREATOR_STAGING_SECRET", secrets.token_urlsafe(48))
from .settings import *  # noqa: F403
# A real temporary SQLite file permits independent connections in concurrency tests.
_TEST_DIR = tempfile.TemporaryDirectory(prefix="creator-staging-test-")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": str(Path(_TEST_DIR.name) / "unused.sqlite3"),
                         "TEST": {"NAME": str(Path(_TEST_DIR.name) / "test.sqlite3")},
                         "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5}}}
