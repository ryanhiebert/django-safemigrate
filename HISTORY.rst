6.0 (2025-06-03)
++++++++++++++++

* Drop support for Python 3.8.
* Raise errors early for unsupported options,
  including ``--fake-initial``, ``--plan``, ``--check``,
  ``--prune``, and ``--run-syncdb``.

5.3 (2025-04-02)
++++++++++++++++

* Add some helpful urls metadata to pyproject.toml

5.2 (2025-04-02)
++++++++++++++++

* Fix undocumented backward incompatible change
  that caused ``None`` to no longer be allowed
  as the value of the ``SAFEMIGRATE`` setting.
* Warn when ``None`` is used as the value of ``SAFEMIGRATE``,
  instead of the preferred ``"strict"`` value.

5.1 (2025-03-27)
++++++++++++++++

* Declared the default auto field for the app to ``BigAutoField``.
  This avoids issues where projects that have their ``DEFAULT_AUTO_FIELD``
  set to ``"django.db.models.AutoField"``
  from seeing this app as needing migrations generated.
  ``django.db.models.AutoField`` is the default auto field
  if the setting is not set,
  but newly generated projects
  automatically set it to ``django.db.models.BigAutoField``.

5.0 (2025-03-18)
++++++++++++++++

Breaking Changes:

* Drop support for Django 3.2, 4.0, 4.1.
* Change the default safe marking to ``Safe.always``.
  This gives a better default experience for working with third-party apps.
* Disallow faking migrations when using ``safemigrate``.
* ``Safe.after_deploy`` and ``Safe.always`` migrations will be
  reported as blocked if they are behind a blocked ``Safe.before_deploy``
  migration.
* ``Safe.after_deploy`` migrations are now reported along with other
  delayed migrations instead of being separately reported as protected.

Other improvements:

* Add support for Django 5.1 and 5.2.
* Add support for Python 3.13.
* The standard values for ``safe`` are now methods that may be called:

  * ``Safe.before_deploy()``
  * ``Safe.after_deploy()``
  * ``Safe.always()``
* Add support for allowing a ``Safe.after_deploy(delay=timedelta())``
  migration to be migrated after the delay has passed.
* Convert ``Safe`` to be a custom class rather than an ``Enum``.
* Rename internal enums for clarity and PEP 8 alignment.
* Use ``uv`` as the build tool.

4.3 (2024-03-28)
++++++++++++++++

* Add ``settings.SAFEMIGRATE = "disabled"`` setting to disable ``safemigrate``
  protections.

4.2 (2023-12-13)
++++++++++++++++

* Add support for Django 5.0.
* Add support for Python 3.12.
* Expand test matrix to all supported combinations of Django and Python.

4.1 (2023-09-13)
++++++++++++++++

* Add a pre-commit hook to ensure migrations have a safe attribute.

4.0 (2022-10-07)
++++++++++++++++

* Add support for Django 4.1, 4.2.
* Add support for Python 3.11.
* Drop support for Django 3.0, 3.1.
* Drop support for Python 3.6, 3.7.

3.1 (2021-12-08)
++++++++++++++++

* Add support for Django 4.0.

3.0 (2020-10-07)
++++++++++++++++

* Drop support for Django<3.


2.1 (2019-12-05)
++++++++++++++++

* Add support for Django 3.

2.0 (2019-01-17)
++++++++++++++++

* The valid values for ``safe`` are:

  * ``Safe.before_deploy``
  * ``Safe.after_deploy``
  * ``Safe.always``

  Import with ``from django_safemigrate import Safe``.
  ``True`` is now ``Safe.before_deploy``,
  and ``False`` is now ``Safe.after_deploy``.
* The default safety marking, when unspecified,
  is now ``Safe.after_deploy``, instead of ``Safe.before_deploy``.
* ``Safe.always`` allows for migrations that may be run
  either before or after deployment,
  because they don't require any database changes.
* Multiple dependent ``Safe.after_deploy`` migrations do not block deployment
  as long as there are no dependent ``Safe.before_deploy`` migrations.
* Enforce that any given value of safe is valid.

1.0 (2019-01-13)
++++++++++++++++

* Initial Release
