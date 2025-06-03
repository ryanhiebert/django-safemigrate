"""Unit tests for the safemigrate command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management.base import CommandError
from django.utils import timezone

from django_safemigrate import Safe
from django_safemigrate.check import validate_migrations
from django_safemigrate.management.commands.safemigrate import Command
from django_safemigrate.models import SafeMigration


class Migration:
    """A mock migration."""

    def __init__(
        self, app_label=None, name=None, dependencies=None, run_before=None, safe=None
    ):
        self.app_label = app_label or "app_label"
        self.name = name or "0001_fake_migration"
        self.dependencies = dependencies or []
        self.run_before = run_before or []
        if safe is not None:
            self.safe = safe

    def __repr__(self):
        return f"<Migration {self.app_label}.{self.name}>"


class TestSafeMigrate:
    """Unit tests for the safemigrate command."""

    # Identify all tests in this class as pytest.mark.django_db
    pytestmark = pytest.mark.django_db

    @pytest.fixture
    def receiver(self):
        """A bound receiver to test against."""
        return Command().pre_migrate_receiver

    def test_receiver_addition(self, mocker):
        connect = mocker.patch(
            "django_safemigrate.management.commands.safemigrate.pre_migrate.connect"
        )
        super_handle = mocker.patch(
            "django_safemigrate.management.commands.safemigrate.migrate.Command.handle"
        )
        command = Command()
        receiver = mocker.patch.object(command, "pre_migrate_receiver")
        command.handle()
        super_handle.assert_called_once_with()
        connect.assert_called_once_with(receiver, dispatch_uid="django_safemigrate")

    def test_rerun(self, receiver):
        """Avoid running the pre_migrate_receiver twice."""
        # Make sure we're looking for the right attribute
        assert receiver.__self__.receiver_has_run is False
        receiver.__self__.receiver_has_run = True
        plan = [(Migration(), False)]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_callable_compat(self, receiver):
        """Understand and do not throw an error when using compatibility syntax."""
        # The plan items aren't dependencies of each other.
        plan = [
            (Migration(safe=Safe.before_deploy), False),
            (Migration(safe=Safe.always), False),
            (Migration(safe=Safe.after_deploy), False),
        ]
        receiver(plan=plan)
        assert len(plan) == 2

    def test_backward(self, receiver):
        """It should fail to run backward."""
        plan = [(Migration(), True)]
        with pytest.raises(CommandError):
            receiver(plan=plan)

    def test_default_always_wont_block(self, receiver):
        """Migrations are safe always by default."""
        plan = [(Migration(safe=Safe.after_deploy()), False), (Migration(), False)]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_default_always_wont_delay(self, receiver):
        """Migrations are safe always by default."""
        plan = [(Migration(safe=Safe.before_deploy()), False), (Migration(), False)]
        receiver(plan=plan)
        assert len(plan) == 2

    def test_all_before(self, receiver):
        """Before migrations will remain in the plan."""
        plan = [(Migration(safe=Safe.before_deploy()), False)]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_final_after(self, receiver):
        """Run everything except the final migration."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_multiple_after(self, receiver):
        """Run up to the first after migration."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (Migration("eggs", "0001_followup", safe=Safe.after_deploy()), False),
        ]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_after_with_passed_delay(self, receiver):
        """Run through the delayed after_deploy migration."""
        SafeMigration.objects.create(
            app="spam", name="0001_initial", detected=timezone.now() - timedelta(days=1)
        )
        SafeMigration.objects.create(
            app="spam",
            name="0002_followup",
            detected=timezone.now() - timedelta(days=1),
        )
        plan = [
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.after_deploy(delay=timedelta(hours=12)),
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(days=2)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1
        assert plan[0][0].name == "0001_initial"

    def test_after_blocks_passed_delay(self, receiver):
        """
        An after_deploy migration without a delay blocks a after_deploy
        migration with a passed delay.
        """
        SafeMigration.objects.create(
            app="spam", name="0001_initial", detected=timezone.now() - timedelta(days=1)
        )
        SafeMigration.objects.create(
            app="spam",
            name="0002_followup",
            detected=timezone.now() - timedelta(days=1),
        )
        plan = [
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.after_deploy(delay=timedelta(days=2)),
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(hours=12)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_after_with_no_detected_blocks_passed_delay(self, receiver):
        """
        An after_deploy migration without a detected blocks a after_deploy
        migration with a passed delay.
        """
        SafeMigration.objects.create(
            app="spam",
            name="0002_followup",
            detected=timezone.now() - timedelta(days=1),
        )
        plan = [
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.after_deploy(delay=timedelta(days=2)),
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(hours=12)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_after_with_no_delay_blocks_passed_delay(self, receiver):
        """
        An after_deploy migration without a delay blocks a after_deploy
        migration with a passed delay.
        """
        SafeMigration.objects.create(
            app="spam", name="0001_initial", detected=timezone.now() - timedelta(days=1)
        )
        SafeMigration.objects.create(
            app="spam",
            name="0002_followup",
            detected=timezone.now() - timedelta(days=1),
        )
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.after_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(hours=12)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_after_doesnt_apply_on_first_run(self, receiver):
        """An after_deploy migration with a passed delay only can't run
        on the same command it was detected."""
        plan = [
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.after_deploy(delay=timedelta(hours=-1)),
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_after_message(self):
        """
        Confirm the delayed messaging of a migration with
        an after_deploy safety.
        """
        plan = [
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.after_deploy(delay=(timedelta(days=8))),
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        out = StringIO()
        receiver = Command(stdout=out).pre_migrate_receiver
        receiver(plan=plan)
        result = out.getvalue().strip()
        header, migration1, migration2 = result.split("\n", maxsplit=2)
        assert header == "Delayed migrations:"
        assert migration1.startswith(
            "  spam.0001_initial (can automatically migrate in 1\xa0week, 1\xa0day - "
        )
        assert migration2 == "  spam.0002_followup"

    def test_blocked_by_after(self, receiver):
        """Blocked before migrations indicate a failure state.

        This might happen when an after migration is shipped, but
        is not run manually after the deployment happened. Safe
        migrations should be run automatically, so this needs to
        block to avoid release failures.
        """
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.before_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
        ]
        with pytest.raises(CommandError):
            receiver(plan=plan)

    def test_blocked_by_after_run_before(self, receiver):
        """Consider run_before when tracking dependencies.

        run_before allows for dependency inversion when a migration
        needs to be run before a migration that may not be under
        your control to add a dependency to directly.
        """
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                    run_before=[("eggs", "0001_safety")],
                ),
                False,
            ),
            (Migration("eggs", "0001_safety", safe=Safe.before_deploy()), False),
        ]
        with pytest.raises(CommandError):
            receiver(plan=plan)

    def test_consecutive_after(self, receiver):
        """Consecutive after migrations are ok."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_always_before_after(self, receiver):
        """Always migrations will run before after migrations."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.always()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_always_after_after(self, receiver):
        """Always migrations will not block after deployments."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.after_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.always(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_blocked_by_after_nonstrict(self, settings, receiver):
        """Nonstrict mode allows before blocked migrations.

        This allows the command to succeed where it would normally
        error. This allows for development environments, where
        errors are acceptable during transitions, to avoid having
        to migrate everything incrementally the way production
        environments are expected to.
        """
        settings.SAFEMIGRATE = "nonstrict"
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.before_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1

    def test_with_non_safe_migration_nonstrict(self, settings, receiver):
        """Run ready migrations even if there are blocked migrations."""
        settings.SAFEMIGRATE = "nonstrict"
        plan = [
            (
                Migration(
                    "auth",
                    "0001_initial",
                    safe=Safe.after_deploy(),
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.before_deploy(),
                    dependencies=[("auth", "0001_initial")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 0

    def test_with_non_safe_migration_disabled(self, settings, receiver):
        """Disabled mode allows all migrations"""
        settings.SAFEMIGRATE = "disabled"
        plan = [
            (
                Migration(
                    "auth",
                    "0001_initial",
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0001_initial",
                    safe=Safe.before_deploy(),
                    dependencies=[("auth", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.before_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 4

    def test_safemigrate_invalid_value(self, settings, receiver):
        """Invalid settings of the SAFEMIGRATE setting will raise an error."""
        settings.SAFEMIGRATE = "invalid"
        plan = []
        with pytest.raises(ValueError):
            receiver(plan=plan)

    def test_safemigrate_none_value(self, settings, receiver):
        """``None`` is valid but deprecated, and means ``strict``."""
        settings.SAFEMIGRATE = None
        plan = []
        with pytest.warns(DeprecationWarning):
            receiver(plan=plan)

    def test_safemigrate_non_string_value(self, settings, receiver):
        """Non-string values for the SAFEMIGRATE setting will raise an error."""
        settings.SAFEMIGRATE = 1
        plan = []
        with pytest.raises(ValueError):
            receiver(plan=plan)

    def test_string_invalid(self, receiver):
        """Invalid settings of the safe property will raise an error."""
        plan = [(Migration("spam", "0001_initial", safe="before_deploy"), False)]
        with pytest.raises(CommandError):
            receiver(plan=plan)

    def test_boolean_invalid(self, receiver):
        """Booleans are invalid for the safe property."""
        plan = [(Migration("spam", "0001_initial", safe=False), False)]
        with pytest.raises(CommandError):
            receiver(plan=plan)

    def test_migrations_not_detected_when_blocked(self, receiver):
        """If the plan can't advance, the migrations shouldn't be marked as detected."""
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(days=1)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.before_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0004_blocked",
                    safe=Safe.after_deploy(delay=timedelta(days=1)),
                    dependencies=[("spam", "0003_safety")],
                ),
                False,
            ),
        ]
        with pytest.raises(CommandError):
            receiver(plan=plan)
        assert not SafeMigration.objects.exists()

    def test_migrations_detected_when_blocked_nonstrict(self, settings, receiver):
        """Delayed migrations should be detected even if others are blocked.

        This behavior is unique to nonstrict mode, where the migrations
        still run even if there are blocked migrations.
        """
        settings.SAFEMIGRATE = "nonstrict"

        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy), False),
            (
                Migration(
                    "spam",
                    "0002_followup",
                    safe=Safe.after_deploy(delay=timedelta(days=1)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.before_deploy,
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0004_blocked",
                    safe=Safe.after_deploy(delay=timedelta(days=1)),
                    dependencies=[("spam", "0003_safety")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert len(plan) == 1
        assert SafeMigration.objects.count() == 1

    def test_disallow_unsupported_options(self):
        """Early error if using an unsupported option."""
        with pytest.raises(CommandError):
            Command().handle(fake=True)
        with pytest.raises(CommandError):
            Command().handle(fake_initial=True)
        with pytest.raises(CommandError):
            Command().handle(plan=True)
        with pytest.raises(CommandError):
            Command().handle(check_unapplied=True)
        with pytest.raises(CommandError):
            Command().handle(prune=True)
        with pytest.raises(CommandError):
            Command().handle(run_syncdb=True)
        assert not SafeMigration.objects.exists()

    def test_migrations_are_detected(self, receiver):
        """Migrations should be marked as detected during the happy flow."""
        existing = SafeMigration.objects.create(
            app="spam", name="0001_initial", detected=timezone.now() - timedelta(days=1)
        )
        plan = [
            (Migration("spam", "0001_initial", safe=Safe.before_deploy()), False),
            (
                Migration(
                    "spam",
                    "0002_delayed",
                    safe=Safe.after_deploy(delay=timedelta(days=1)),
                    dependencies=[("spam", "0001_initial")],
                ),
                False,
            ),
            (
                Migration(
                    "spam",
                    "0003_safety",
                    safe=Safe.after_deploy(),
                    dependencies=[("spam", "0002_followup")],
                ),
                False,
            ),
        ]
        receiver(plan=plan)
        assert SafeMigration.objects.count() == 2
        # Confirm the existing value is not updated
        assert SafeMigration.objects.filter(detected__gt=existing.detected).count() == 1


class TestCheckMissingSafe:
    """
    Test the check command for migrations
    missing the safe attribute
    """

    MARKED = """
from django.db import migrations
from django_safemigrate import Safe

class Migration(migrations.Migration):
    safe = Safe.always()
"""

    UNMARKED = """
from django.db import migrations

class Migration(migrations.Migration):
    pass
"""

    def test_validate_migrations_success(self, tmp_path):
        with open(tmp_path / "0001_initial.py", "w") as f:
            f.write(self.MARKED)
        assert validate_migrations([tmp_path / "0001_initial.py"])

    def test_validate_migrations_failure(self, tmp_path):
        with open(tmp_path / "0001_initial.py", "w") as f:
            f.write(self.UNMARKED)
        assert not validate_migrations([tmp_path / "0001_initial.py"])

    def test_validate_migrations_falsematch(self, tmp_path):
        with open(tmp_path / "0001_initial.py", "w") as f:
            f.write("THIS IS NOT A MIGRATION")
        assert validate_migrations([tmp_path / "0001_initial.py"])


class TestCheckEnumAttribute:
    """
    Test the check command for migrations
    missing the safe attribute
    """

    ENUM_DEFINITION = """
from django.db import migrations
from django_safemigrate import Safe

class Migration(migrations.Migration):
    safe = Safe.always
"""

    def test_validate_migrations_failure(self, tmp_path):
        with open(tmp_path / "0001_initial.py", "w") as f:
            f.write(self.ENUM_DEFINITION)
        assert not validate_migrations([tmp_path / "0001_initial.py"])
