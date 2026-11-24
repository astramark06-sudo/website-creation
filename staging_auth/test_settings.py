"""Ephemeral test configuration; never use for actual applications."""
import os
import secrets

os.environ.setdefault("CREATOR_STAGING_SECRET", secrets.token_urlsafe(48))
from .settings import *  # noqa: F403
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
                         "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5}}}
