"""Verify cluster identity before Django may create or destroy a test database."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner


class IsolatedPostgresRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        if self.keepdb or self.parallel not in (0, 1) or list(connections) != ["default"]:
            raise ImproperlyConfigured("Test database reuse and parallel cloning are disabled.")
        connection = connections["default"]
        expected = settings.CLUSTER_MANIFEST["database"]
        if (
            connection.settings_dict["NAME"] != "postgres"
            or connection.settings_dict["TEST"]["NAME"] != expected
            or connection.settings_dict["HOST"] != str(settings.CLUSTER_ROOT / "socket")
        ):
            raise ImproperlyConfigured("Database configuration escaped the disposable cluster.")
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            if Path(cursor.fetchone()[0]).resolve() != settings.CLUSTER_ROOT / "data":
                raise ImproperlyConfigured("Connected server is not the disposable test cluster.")
            cursor.execute("SHOW listen_addresses")
            if cursor.fetchone()[0] != "":
                raise ImproperlyConfigured("Disposable PostgreSQL must not listen on TCP.")
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [expected])
            if cursor.fetchone():
                raise ImproperlyConfigured("Refusing to reuse or reset an existing test database.")
        return super().setup_databases(**kwargs)
