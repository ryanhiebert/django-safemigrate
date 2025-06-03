"""Hook into the migrate command to add safety.

Migration safety is enforced by a pre_migrate signal receiver.
"""

from __future__ import annotations

from collections.abc import Collection
from functools import cached_property
from enum import Enum
import warnings

from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands import migrate
from django.db.migrations import Migration
from django.db.models.signals import pre_migrate
from django.db.utils import OperationalError
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


class Command(migrate.Command):
    """Run database migrations that are safe to run before deployment."""

    help = "Run database migrations that are safe to run before deployment."
    receiver_has_run = False

    def handle(self, *args, **options):
        if options.get("fake") or options.get("fake_initial"):
            raise CommandError("Safemigrate does not support faking migrations.")
        if options.get("plan"):
            raise CommandError("Safemigrate does not support the plan option.")
        if options.get("check_unapplied"):
            raise CommandError("Safemigrate does not support the check_unapplied option.")
        if options.get("prune"):
            raise CommandError("Safemigrate does not support the prune option.")
        if options.get("run_syncdb"):
            raise CommandError("Safemigrate does not support the run_syncdb option.")

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
            return  # Run migrate normally

        if any(backward for _, backward in plan):
            raise CommandError("Backward migrations are not supported.")

        # Resolve the declared safety configuration of each migration
        declared = {migration: self.safe(migration) for migration, _ in plan}

        # Get the dates of when migrations were detected
        detected = self.detected(declared)

        # Resolve the current status for each migration respecting delays
        resolved = self.resolve(declared, detected)

        # Categorize the migrations for display and action
        ready, delayed, blocked = self.categorize(resolved)

        if delayed:
            self.write_delayed(delayed, declared, resolved, detected)

        if blocked:
            self.write_blocked(blocked)

        if blocked and self.mode == Mode.STRICT:
            raise CommandError("Aborting due to blocked migrations.")

        # Mark the delayed migrations as detected
        self.detect(
            [
                migration
                for migration in delayed
                if declared[migration].when == When.AFTER_DEPLOY
                and declared[migration].delay is not None
            ]
        )

        # Swap out the items in the plan with the safe migrations.
        # None are backward, so we can always set backward to False.
        plan[:] = [(migration, False) for migration in ready]

    @cached_property
    def mode(self):
        """Determine the configured mode of operation for safemigrate."""
        mode = getattr(settings, "SAFEMIGRATE", "strict")
        if mode is None:
            warnings.warn(
                "Setting the SAFEMIGRATE setting to None is deprecated."
                " Use 'strict' instead, or remove the setting to use the default.",
                DeprecationWarning,
            )
            mode = "strict"
        if not isinstance(mode, str):
            raise ValueError(
                "The SAFEMIGRATE setting must be a string."
                " It must be one of 'strict', 'nonstrict', or 'disabled'."
            )
        try:
            return Mode(mode.lower())
        except ValueError:
            raise ValueError(
                "The SAFEMIGRATE setting is invalid."
                " It must be one of 'strict', 'nonstrict', or 'disabled'."
            )

    @staticmethod
    def safe(migration: Migration) -> Safe:
        """Determine the safety setting of a migration."""
        callables = [Safe.before_deploy, Safe.after_deploy, Safe.always]
        safe = getattr(migration, "safe", Safe.always)
        safety = safe() if safe in callables else safe
        if not isinstance(safety, Safe):
            raise CommandError(
                f"Migration {migration.app_label}.{migration.name}"
                " has an invalid safe property."
            )
        return safety

    def detected(
        self, declared: dict[Migration, Safe]
    ) -> dict[Migration, timezone.datetime]:
        """Get the detected dates for each migration."""
        to_detect = [
            (migration.app_label, migration.name)
            for migration, safe in declared.items()
            if safe.when == When.AFTER_DEPLOY and safe.delay is not None
        ]
        try:
            detected_map = SafeMigration.objects.get_detected_map(to_detect)
        except OperationalError:  # pragma: no cover
            return {}  # The table doesn't exist yet
        return {
            migration: detected_map[(migration.app_label, migration.name)]
            for migration in declared
            if (migration.app_label, migration.name) in detected_map
        }

    def resolve(
        self,
        declared: dict[Migration, Safe],
        detected: dict[Migration, timezone.datetime],
    ) -> dict[Migration, When]:
        """Resolve the current status of each migration.

        ``When.AFTER_DEPLOY`` migrations are resolved to ``When.ALWAYS``
        if they have previously been detected and their delay has passed.
        """
        now = timezone.now()
        return {
            migration: (
                When.ALWAYS
                if safe.when == When.AFTER_DEPLOY
                and safe.delay is not None
                and migration in detected
                and detected[migration] + safe.delay <= now
                else safe.when
            )
            for migration, safe in declared.items()
        }

    @staticmethod
    def to_block(
        target: Collection[Migration],
        blockers: Collection[Migration],
    ):
        """Find a round of migrations that depend on these blockers.

        Search the target collection for migrations that depend on the
        given set of blocker migrations.
        """
        blocker_deps = [(m.app_label, m.name) for m in blockers]
        to_block_deps = [dep for m in blockers for dep in m.run_before]
        return [
            migration
            for migration in target
            if any(dep in blocker_deps for dep in migration.dependencies)
            or (migration.app_label, migration.name) in to_block_deps
        ]

    def categorize(
        self,
        resolved: dict[Migration, When],
    ) -> tuple[list[Migration], list[Migration], list[Migration]]:
        """Categorize the migrations as ready, delayed, or blocked.

        Ready migrations are ready to be run immediately.

        Delayed migrations cannot be run immediately, but are safe to run
        after deployment.

        Blocked migrations are dependent on a delayed migration, but
        either need to run before deployment or depend on a migration
        that needs to run before deployment.
        """
        ready = [mig for mig, when in resolved.items() if when != When.AFTER_DEPLOY]
        delayed = [mig for mig, when in resolved.items() if when == When.AFTER_DEPLOY]
        blocked = []

        if not delayed and not blocked:
            return ready, delayed, blocked

        # Delay or block migrations that are behind protected migrations.
        while True:
            block = self.to_block(ready, delayed + blocked)
            if not block:
                break

            for migration in block:
                ready.remove(migration)
                if resolved[migration] == When.BEFORE_DEPLOY:
                    blocked.append(migration)
                else:
                    delayed.append(migration)

        # Block delayed migrations that are behind other blocked migrations.
        while True:
            block = self.to_block(delayed, blocked)
            if not block:
                break

            for migration in block:
                delayed.remove(migration)
                blocked.append(migration)

        # Order the migrations in the order of the original plan.
        ready = [m for m in resolved if m in ready]
        delayed = [m for m in resolved if m in delayed]
        blocked = [m for m in resolved if m in blocked]

        return ready, delayed, blocked

    def detect(self, migrations: list[Migration]):
        """Mark the given migrations as detected."""
        # The detection datetime is what's used to determine if an
        # after_deploy() with a delay can be migrated or not.
        try:
            for migration in migrations:
                SafeMigration.objects.get_or_create(
                    app=migration.app_label, name=migration.name
                )
        except OperationalError:  # pragma: no cover
            pass  # The table doesn't exist yet

    def write_delayed(
        self,
        migrations: list[Migration],
        declared: dict[Migration, Safe],
        resolved: dict[Migration, When],
        detected: dict[Migration, timezone.datetime],
    ):
        """Display delayed migrations."""
        self.stdout.write(self.style.MIGRATE_HEADING("Delayed migrations:"))
        for migration in migrations:
            if (
                resolved[migration] == When.AFTER_DEPLOY
                and declared[migration].delay is not None
            ):
                now = timezone.localtime()
                migrate_date = detected.get(migration, now) + declared[migration].delay
                humanized_date = timeuntil(migrate_date, now=now, depth=2)
                self.stdout.write(
                    f"  {migration.app_label}.{migration.name} "
                    f"(can automatically migrate in {humanized_date} "
                    f"- {migrate_date.isoformat()})"
                )
            else:
                self.stdout.write(f"  {migration.app_label}.{migration.name}")

    def write_blocked(self, migrations: list[Migration]):
        """Display blocked migrations."""
        self.stdout.write(self.style.MIGRATE_HEADING("Blocked migrations:"))
        for migration in migrations:
            self.stdout.write(f"  {migration.app_label}.{migration.name}")
