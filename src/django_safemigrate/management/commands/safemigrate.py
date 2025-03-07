"""Hook into the migrate command to add safety.

Migration safety is enforced by a pre_migrate signal receiver.
"""

from __future__ import annotations

from functools import cached_property
from enum import Enum

from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands import migrate
from django.db.migrations import Migration
from django.db.models.signals import pre_migrate
from django.utils import timezone
from django.utils.timesince import timeuntil

from django_safemigrate import Safe, When
from django_safemigrate.models import SafeMigration


class Mode(Enum):
    """The mode of operation for safemigrate.

    STRICT, the default mode, will throw an error if migrations
    marked Safe.before_deploy() are blocked by unrun migrations that
    are marked Safe.after_deploy() with an unfulfilled delay.

    NONSTRICT will run the same migrations as strict mode, but will
    not throw an error if migrations are blocked.

    DISABLED will completely bypass safemigrate protections and run
    exactly the same as the standard migrate command.
    """

    STRICT = "strict"
    NONSTRICT = "nonstrict"
    DISABLED = "disabled"


def safety(migration: Migration):
    """Determine the safety status of a migration."""
    safe = getattr(migration, "safe", Safe.always())
    callables = [Safe.before_deploy, Safe.after_deploy, Safe.always]
    return safe() if safe in callables else safe


def filter_migrations(
    migrations: list[Migration],
) -> tuple[list[Migration], list[Migration]]:
    """
    Filter migrations into ready and protected migrations.

    A protected migration is one that's marked Safe.after_deploy()
    and has not yet passed its delay value.
    """
    now = timezone.now()

    detected_map = SafeMigration.objects.get_detected_map(
        [(m.app_label, m.name) for m in migrations]
    )

    def is_protected(migration):
        migration_safe = safety(migration)
        detected = detected_map.get((migration.app_label, migration.name))
        # A migration is protected if detected is None or delay is not specified.
        return migration_safe.when == When.AFTER_DEPLOY and (
            detected is None
            or migration_safe.delay is None
            or now < (detected + migration_safe.delay)
        )

    ready = []
    protected = []

    for migration in migrations:
        if is_protected(migration):
            protected.append(migration)
        else:
            ready.append(migration)
    return ready, protected


class Command(migrate.Command):
    """Run database migrations that are safe to run before deployment."""

    help = "Run database migrations that are safe to run before deployment."
    receiver_has_run = False
    fake = False

    def handle(self, *args, **options):
        self.fake = options.get("fake", False)
        # Only connect the handler when this command is run to
        # avoid running for tests.
        pre_migrate.connect(
            self.pre_migrate_receiver, dispatch_uid="django_safemigrate"
        )
        super().handle(*args, **options)

    def pre_migrate_receiver(self, *, plan: list[tuple[Migration, bool]], **_):
        """Modify the migration plan to apply deployment safety."""
        if self.receiver_has_run:
            return  # Only run once
        self.receiver_has_run = True

        if self.mode == Mode.DISABLED:
            # When disabled, run migrate
            return

        if any(backward for mig, backward in plan):
            raise CommandError("Backward migrations are not supported.")

        # Pull the migrations into a new list
        migrations = [migration for migration, backward in plan]

        # Check for invalid safe properties
        invalid = [
            migration
            for migration in migrations
            if not isinstance(safety(migration), Safe)
            or safety(migration).when not in When
        ]
        if invalid:
            self.stdout.write(self.style.MIGRATE_HEADING("Invalid migrations:"))
            for migration in invalid:
                self.stdout.write(f"  {migration.app_label}.{migration.name}")
            raise CommandError(
                "Aborting due to migrations with invalid safe properties."
            )

        ready, protected = filter_migrations(migrations)

        if not protected:
            self.detect(migrations)
            return  # Run all the migrations

        # Display the migrations that are protected
        self.stdout.write(self.style.MIGRATE_HEADING("Protected migrations:"))
        for migration in protected:
            self.stdout.write(f"  {migration.app_label}.{migration.name}")

        delayed = []
        blocked = []

        while True:
            blockers = protected + delayed + blocked
            blockers_deps = [(m.app_label, m.name) for m in blockers]
            to_block_deps = [dep for mig in blockers for dep in mig.run_before]
            block = [
                migration
                for migration in ready
                if any(dep in blockers_deps for dep in migration.dependencies)
                or (migration.app_label, migration.name) in to_block_deps
            ]
            if not block:
                break

            for migration in block:
                ready.remove(migration)
                if safety(migration).when == When.BEFORE_DEPLOY:
                    blocked.append(migration)
                else:
                    delayed.append(migration)

        # Order the migrations in the order of the original plan.
        delayed = [m for m in migrations if m in delayed]
        blocked = [m for m in migrations if m in blocked]

        self.delayed(delayed)
        self.blocked(blocked)

        if blocked and self.mode == Mode.STRICT:
            raise CommandError("Aborting due to blocked migrations.")

        # Only mark migrations as detected if not faking
        if not self.fake:
            self.detect(migrations)

        # Swap out the items in the plan with the safe migrations.
        # None are backward, so we can always set backward to False.
        plan[:] = [(migration, False) for migration in ready]

    @cached_property
    def mode(self):
        """Determine the configured mode of operation for safemigrate."""
        try:
            return Mode(getattr(settings, "SAFEMIGRATE", "strict").lower())
        except ValueError:
            raise ValueError(
                "The SAFEMIGRATE setting is invalid."
                " It must be one of 'strict', 'nonstrict', or 'disabled'."
            )

    def detect(self, migrations):
        """Detect and record migrations to the database."""
        # The detection datetime is what's used to determine if an
        # after_deploy() with a delay can be migrated or not.
        for migration in migrations:
            SafeMigration.objects.get_or_create(
                app=migration.app_label, name=migration.name
            )

    def delayed(self, migrations):
        """Handle delayed migrations."""
        # Display delayed migrations if they exist:
        if migrations:
            detected_map = SafeMigration.objects.get_detected_map(
                [(m.app_label, m.name) for m in migrations]
            )
            self.stdout.write(self.style.MIGRATE_HEADING("Delayed migrations:"))
            for migration in migrations:
                migration_safe = safety(migration)
                if (
                    migration_safe.when == When.AFTER_DEPLOY
                    and migration_safe.delay is not None
                ):
                    now = timezone.localtime()
                    detected = detected_map.get(
                        (migration.app_label, migration.name), timezone.localtime()
                    )
                    migrate_date = detected + migration_safe.delay
                    humanized_date = timeuntil(migrate_date, now=now, depth=2)
                    self.stdout.write(
                        f"  {migration.app_label}.{migration.name} "
                        f"(can automatically migrate in {humanized_date} "
                        f"- {migrate_date.isoformat()})"
                    )
                else:
                    self.stdout.write(f"  {migration.app_label}.{migration.name}")

    def blocked(self, migrations):
        """Handle blocked migrations."""
        # Display blocked migrations if they exist.
        if migrations:
            self.stdout.write(self.style.MIGRATE_HEADING("Blocked migrations:"))
            for migration in migrations:
                self.stdout.write(f"  {migration.app_label}.{migration.name}")
