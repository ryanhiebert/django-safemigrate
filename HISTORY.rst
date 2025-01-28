Pending
*******

* Add support for Django 5.1.
* Drop support for Django 3.2, 4.0, 4.1.
* Convert ``Safe`` to be a custom class rather than an ``Enum``.
* The standard values for ``safe`` are now methods that may be called:

  * ``Safe.before_deploy()``
  * ``Safe.after_deploy()``
  * ``Safe.always()``
* Add support for allowing a ``Safe.after_deploy(delay=timedelta())``
  migration to be migrated after the delay has passed.
* Rename internal enums for clarity and PEP8.
* Change the default safe marking to ``Safe.always``.
  This gives a better default experience for working with third-party apps.
* Add support for Django 5.2.

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
