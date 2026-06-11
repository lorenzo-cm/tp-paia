"""DB integration test package marker.

The shared Postgres fixtures (``postgres_url``, ``db_engine``, ``db_session``)
and the Docker-availability skip guard were relocated to the root
``tests/conftest.py`` so suites outside ``tests/db/`` can reuse them. This file
is intentionally thin — fixtures are inherited from the root conftest.
"""
