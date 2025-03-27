"""Add a safemigrate command."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SafeMigrateConfig(AppConfig):
    """Safe migrate Django app config."""

    name = "django_safemigrate"
    verbose_name = _("Safe Migrate")
    default_auto_field = "django.db.models.BigAutoField"
