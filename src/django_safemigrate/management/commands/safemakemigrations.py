"""Hook into the makemigrations command to add safety."""

from __future__ import annotations
from django.core.management.commands import makemigrations


class Command(makemigrations.Command):
    help = "Creates new migration(s) for apps, with safety annotations."


class SafeMigrationAutodetector(makemigrations.MigrationAutodetector):
    def changes(self, graph, *args, **kwargs):
        # TODO: Add safety import and annotation to migration
        #       Import can happen by adding an operation
        #       I'm not sure how to add the annotation yet
        #       These changes are written in Command.write_migration_files
        #       using MigrationWriter(...).as_string()
        return super().changes(graph, *args, **kwargs)


# Monkeypatch the autodetector
makemigrations.MigrationAutodetector = SafeMigrationAutodetector
