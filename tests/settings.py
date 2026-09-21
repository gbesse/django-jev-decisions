"""Purpose: Configure an isolated SQLite Django host for integration tests and the offline example."""
from pathlib import Path
import json
BASE = Path(__file__).resolve().parent.parent
SECRET_KEY = "synthetic-test-secret-not-for-deployment"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.admin", "jev_decisions", "tests.demoapp"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIDDLEWARE = ["django.contrib.sessions.middleware.SessionMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware"]
ROOT_URLCONF = "tests.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
ADMINS = [("Fixture admin", "admin@example.invalid")]
JEV_ENVIRONMENT = "staging"
JEV_RULES = {"support": {"pack": json.loads((BASE / "packs/support-triage.json").read_text()), "model": "demoapp.Ticket", "state": "tests.demoapp.models.ticket_state"}}
USE_TZ = True
