"""Independent settings for the private PostgreSQL cluster created by our test script."""

import json
import os
from pathlib import Path
import re
import secrets
import stat

from django.core.exceptions import ImproperlyConfigured


def isolated_cluster(environment):
    """Fail before connecting unless the explicit, private test manifest is valid."""
    if any(key.startswith("PG") for key in environment) or "DJANGO_ALLOW_ASYNC_UNSAFE" in environment:
        raise ImproperlyConfigured("Inherited PostgreSQL options and async-unsafe overrides are forbidden.")
    value = environment.get("PAULINES_TEST_CLUSTER")
    if not value:
        raise ImproperlyConfigured("Use scripts/run_auth_tests.py to create a disposable cluster.")
    root = Path(value)
    if (
        not root.is_absolute()
        or root.parent != Path("/tmp")
        or not re.fullmatch(r"paulines-auth-tests-[a-z0-9_]+", root.name)
        or root.is_symlink()
        or not root.is_dir()
    ):
        raise ImproperlyConfigured("Test cluster must be a private directory directly under /tmp.")
    info = root.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ImproperlyConfigured("Test cluster must be owned by this user with mode 0700.")
    try:
        manifest_path = root / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError
        manifest = json.loads(manifest_path.read_text())
        run_id = manifest["run_id"]
        if (
            not isinstance(run_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", run_id)
            or manifest["database"] != "test_paulines_auth_" + run_id
            or manifest["role"] != "paulines_test_runner"
            or manifest["port"] != 55432
        ):
            raise ValueError
        for name in ("data", "socket"):
            child = root / name
            if child.is_symlink() or not child.is_dir():
                raise ValueError
        if not (root / "data" / "PG_VERSION").is_file():
            raise ValueError
        passfile = root / "pgpass"
        if passfile.is_symlink() or not passfile.is_file():
            raise ValueError
        passfile_info = passfile.stat()
        if (
            passfile_info.st_uid != os.getuid()
            or stat.S_IMODE(passfile_info.st_mode) != 0o600
            or passfile_info.st_size != 0
        ):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError):
        raise ImproperlyConfigured("Invalid disposable test-cluster manifest.") from None
    return root, manifest


CLUSTER_ROOT, CLUSTER_MANIFEST = isolated_cluster(os.environ)
SECRET_KEY = secrets.token_urlsafe(48)
JWT_SECRET_KEY = SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "accounts.apps.AccountsConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": CLUSTER_MANIFEST["role"],
        "PASSWORD": "",
        "HOST": str(CLUSTER_ROOT / "socket"),
        "PORT": CLUSTER_MANIFEST["port"],
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 5, "passfile": str(CLUSTER_ROOT / "pgpass")},
        "TEST": {"NAME": CLUSTER_MANIFEST["database"]},
    }
}
TEST_RUNNER = "paulines.test_runner.IsolatedPostgresRunner"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
