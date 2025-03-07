from __future__ import annotations

from django.db import models
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SafeMigrationManager(models.Manager):
    def get_detected_map(
        self, app_model_pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], timezone.datetime]:
        detection_qs = (
            self.get_queryset()
            .annotate(
                identifer=Concat(models.F("app"), models.Value("."), models.F("name"))
            )
            .filter(identifer__in=[".".join(pair) for pair in app_model_pairs])
        )
        detected_map = {
            (obj.app, obj.name): obj.detected for obj in detection_qs.iterator()
        }
        return detected_map


class SafeMigration(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["app", "name"], name="safemigration_unique"
            ),
        ]

    created = models.DateTimeField(auto_now_add=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    detected = models.DateTimeField(
        help_text=_(
            "The time the migration was detected."
            " This is used to determine when a migration with"
            " Safe.after_deploy() should be migrated."
        ),
        default=timezone.now,
    )
    objects = SafeMigrationManager()
