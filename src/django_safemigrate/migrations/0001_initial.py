import django.utils.timezone
from django.db import migrations, models

from django_safemigrate import Safe


class Migration(migrations.Migration):
    safe = Safe.before_deploy()

    dependencies = [
        ("contenttypes", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="SafeMigration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("app", models.CharField(max_length=255)),
                ("name", models.CharField(max_length=255)),
                (
                    "detected",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="The time the migration was detected."
                        " This is used to determine when a migration with"
                        " Safe.after_deploy() should be migrated.",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="safemigration",
            constraint=models.UniqueConstraint(
                fields=("app", "name"), name="safemigration_unique"
            ),
        ),
    ]
