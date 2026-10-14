"""Safety checks that run before authentication integration work."""

import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from paulines.test_settings import isolated_cluster
from paulines.test_runner import IsolatedPostgresRunner


class IsolationConfigurationTests(SimpleTestCase):
    def test_missing_configuration_fails_before_database_access(self):
        with self.assertRaises(ImproperlyConfigured):
            isolated_cluster({})

    def test_inherited_database_options_and_unsafe_override_are_rejected(self):
        for key in ("PGHOSTADDR", "PGSERVICE", "PGPASSWORD", "DJANGO_ALLOW_ASYNC_UNSAFE"):
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured):
                isolated_cluster(dict(os.environ, **{key: "synthetic-override"}))

    def test_signing_key_is_independent_of_public_run_metadata(self):
        self.assertFalse(settings.SECRET_KEY == "isolated-tests-" + settings.CLUSTER_MANIFEST["run_id"])

    def test_nonempty_password_file_is_rejected(self):
        passfile = settings.CLUSTER_ROOT / "pgpass"
        try:
            passfile.write_text("synthetic-content")
            with self.assertRaises(ImproperlyConfigured):
                isolated_cluster(os.environ)
        finally:
            passfile.write_text("")

    def test_external_host_and_application_paths_are_rejected(self):
        for value in ("localhost", "/var/lib/postgresql", str(Path.cwd()), "relative/path"):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                isolated_cluster({"PAULINES_TEST_CLUSTER": value})

    def test_mismatched_database_name_is_rejected(self):
        invalid = dict(settings.CLUSTER_MANIFEST, database="application_database")
        with patch.object(Path, "read_text", return_value=json.dumps(invalid)):
            with self.assertRaises(ImproperlyConfigured):
                isolated_cluster(os.environ)

    def test_incorrect_directory_permissions_are_rejected(self):
        root = settings.CLUSTER_ROOT
        original = root.stat().st_mode & 0o777
        try:
            root.chmod(0o755)
            with self.assertRaises(ImproperlyConfigured):
                isolated_cluster(os.environ)
        finally:
            root.chmod(original)

    def test_existing_test_database_is_never_reset(self):
        fake_connection = MagicMock()
        fake_connection.settings_dict = {
            "NAME": "postgres",
            "HOST": str(settings.CLUSTER_ROOT / "socket"),
            "TEST": {"NAME": settings.CLUSTER_MANIFEST["database"]},
        }
        cursor = fake_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(str(settings.CLUSTER_ROOT / "data"),), ("",), (1,)]
        with (
            patch("paulines.test_runner.connections", {"default": fake_connection}),
            patch("django.test.runner.DiscoverRunner.setup_databases") as create_database,
        ):
            with self.assertRaisesMessage(ImproperlyConfigured, "Refusing to reuse"):
                IsolatedPostgresRunner().setup_databases()
            create_database.assert_not_called()


class DisposableDatabaseTests(TransactionTestCase):
    def test_database_and_server_are_the_private_cluster(self):
        self.assertNotIn("DJANGO_ALLOW_ASYNC_UNSAFE", os.environ)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            self.assertEqual(cursor.fetchone()[0], settings.CLUSTER_MANIFEST["database"])
            cursor.execute("SHOW data_directory")
            self.assertEqual(Path(cursor.fetchone()[0]), settings.CLUSTER_ROOT / "data")
            cursor.execute("SHOW listen_addresses")
            self.assertEqual(cursor.fetchone()[0], "")

    def test_synthetic_record_round_trip_uses_disposable_storage(self):
        user = User.objects.create_user(
            username="isolation-check@example.org", email="isolation-check@example.org"
        )
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(user.has_usable_password())
