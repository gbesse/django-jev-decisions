"""Purpose: Register the reusable Django application."""
from django.apps import AppConfig
class JevDecisionsConfig(AppConfig):
    name = "jev_decisions"
    verbose_name = "Jev decisions"
    default_auto_field = "django.db.models.BigAutoField"
