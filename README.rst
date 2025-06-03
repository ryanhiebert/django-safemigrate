===========================================================
django-safemigrate: Safely run migrations before deployment
===========================================================

.. image:: https://img.shields.io/pypi/v/django-safemigrate.svg
   :target: https://pypi.org/project/django-safemigrate/
   :alt: Latest Version

.. image:: https://github.com/ryanhiebert/django-safemigrate/workflows/Build/badge.svg
   :target: https://github.com/ryanhiebert/django-safemigrate/actions/
   :alt: Build status

.. image:: https://codecov.io/gh/ryanhiebert/django-safemigrate/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/ryanhiebert/django-safemigrate
   :alt: Code Coverage

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/ambv/black
   :alt: Code style: black

|

django-safemigrate adds a ``safemigrate`` command to Django
to allow for safely running a migration command when deploying.

Usage
=====

Install ``django-safemigrate``, then add this to the
``INSTALLED_APPS`` in the settings file:

.. code-block:: python

    INSTALLED_APPS = [
        # ...
        "django_safemigrate",
    ]

Then mark any migration that may be run
during a pre-deployment stage,
such as a migration to add a column.

.. code-block:: python

    from django_safemigrate import Safe

    class Migration(migrations.Migration):
        safe = Safe.before_deploy

At this point you can run the ``safemigrate`` Django command
to run the migrations, and only these migrations will run.
However, if migrations that are not safe to run before
the code is deployed are dependencies of this migration,
then these migrations will be blocked, and the safemigrate
command will fail with an error.

When the code is fully deployed, just run the normal ``migrate``
Django command, which still functions normally.
For example, you could add the command to the release phase
for your Heroku app, and the safe migrations will be run
automatically when the new release is promoted.

Safety Options
==============

There are three options for the value of the
``safe`` property of the migration.

* ``Safe.before_deploy``

  This migration is only safe to run before the code change is deployed.
  For example, a migration that adds a new field to a model.

* ``Safe.after_deploy``

  This migration is only safe to run after the code change is deployed.
  For example, a migration that removes a field from a model.

  By specifying a ``delay`` parameter, you can specify when a
  ``Safe.after_deploy`` migration can be run with the ``safemigrate``
  command. For example, if it's desired to wait a week before applying
  a migration, you can specify ``Safe.after_deploy(delay=timedelta(days=7))``.

  The ``delay`` is used with the datetime when the migration is first detected.
  The detection datetime is when the ``safemigrate`` command detects the
  migration in a plan that successfully runs. If the migration plan is blocked,
  such when a ``Safe.after_deploy`` is in front of a
  ``Safe.before_deploy``, no migrations are marked as detected.

  Note that a ``Safe.after_deploy`` migration will not run the first
  time it's encountered.

* ``Safe.always``

  This migration is safe to run before *and* after
  the code change is deployed.
  This is the default that is applied if no ``safe`` property is given.
  For example, a migration that changes the ``help_text`` of a field.

Pre-commit Hook
===============

To get the most from django-safemigrate,
it is important to make sure that all migrations
are marked with the appropriate ``safe`` value.
To help with this, we provide a hook for use with ``pre-commit``.
`Install and configure pre-commit`_,
then add this to the ``repos`` key of your ``.pre-commit-config.yaml``:

.. code-block:: yaml

    repos:
        -   repo: https://github.com/ryanhiebert/django-safemigrate
            rev: "6.0"
            hooks:
            -   id: check

.. _Install and configure pre-commit: https://pre-commit.com/

Nonstrict Mode
==============

Under normal operation, if there are migrations
that must run before the deployment that depend
on any migration that is marked to run after deployment,
the command will raise an error to indicate
that there are protected migrations that
should have already been run, but have not been,
and are blocking migrations that are expected to run.

In development, however, it is common that these
would accumulate between developers,
and since it is acceptable for there to be downtime
during the transitional period in development,
it is better to allow the command to continue without raising.

To enable nonstrict mode, add the ``SAFEMIGRATE`` setting:

.. code-block:: python

    SAFEMIGRATE = "nonstrict"

In this mode ``safemigrate`` will run all the migrations
that are not blocked by any unsafe migrations.
Any remaining migrations can be run after the fact
using the normal ``migrate`` Django command.

Disabled Mode
=============

To disable the protections of ``safemigrate`` entirely, add the
``SAFEMIGRATE`` setting:

.. code-block:: python

    SAFEMIGRATE = "disabled"

In this mode ``safemigrate`` will migrations as if they were
using the normal ``migrate`` Django command.

Contributing
============

To get started contributing, you'll want to clone the repository,
install dependencies with `uv <https://docs.astral.sh/uv/>`_,
and set up `pre-commit <https://pre-commit.com/>`_.

.. code-block:: bash

    git clone git@github.com:ryanhiebert/django-safemigrate.git
    cd django-safemigrate
    uv sync
    pre-commit install

To run the tests use:

.. code-block:: bash

    uvx --with tox-uv tox

To publish a new version:

1. Find and replace all instances of the previous version with the new version.
2. Commit and push that to origin.
3. Tag the commit with the new version ``git tag 1.0`` and push that to origin.
4. Create the
   `new release <https://github.com/ryanhiebert/django-safemigrate/releases/new>`_
   on GitHub. It will be published to PyPI automatically.
