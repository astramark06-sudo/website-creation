"""Isolated local staging configuration, not a public production configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY = os.environ.get("CREATOR_STAGING_SECRET", "")
if len(SECRET_KEY) < 50:
    raise RuntimeError("Set a locally generated CREATOR_STAGING_SECRET of at least 50 characters")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
ROOT_URLCONF = "staging_auth.urls"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "staging_auth",
]
MIDDLEWARE = [
    "staging_auth.middleware.LocalHeaders",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": os.environ.get("CREATOR_STAGING_DB", str(BASE_DIR / ".local-staging" / "workspace.sqlite3")),
    "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"},
}}
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request",
                                       "django.contrib.auth.context_processors.auth"]},
}]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_NAME = "creator_staging_session"
CSRF_COOKIE_NAME = "creator_staging_csrf"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
# Loopback HTTP only. Public TLS/cookie configuration is deliberately not provided.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Keep same-origin form provenance for Django CSRF checks; never send cross-origin referrers.
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 16384
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20
USE_TZ = True
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
