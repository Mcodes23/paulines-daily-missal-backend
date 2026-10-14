"""Run Django tests on a fresh private PostgreSQL cluster; never load project .env."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


def run(*command, environment, **kwargs):
    return subprocess.run(command, env=environment, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", nargs="*", default=["accounts.test_isolation"])
    args = parser.parse_args()
    for binary in ("initdb", "pg_ctl"):
        if not shutil.which(binary):
            parser.error(f"{binary} is required; no database fallback is permitted")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    environment.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["DJANGO_SETTINGS_MODULE"] = "paulines.test_settings"
    root = Path(tempfile.mkdtemp(prefix="paulines-auth-tests-", dir="/tmp"))
    data = root / "data"
    socket = root / "socket"
    socket.mkdir(mode=0o700)
    manifest = {
        "run_id": uuid.uuid4().hex,
        "role": "paulines_test_runner",
        "port": 55432,
    }
    manifest["database"] = "test_paulines_auth_" + manifest["run_id"]
    (root / "manifest.json").write_text(json.dumps(manifest))
    passfile = root / "pgpass"
    passfile.touch(mode=0o600)
    environment["PAULINES_TEST_CLUSTER"] = str(root)
    started = False
    try:
        run(
            "initdb", "-D", str(data), "-U", manifest["role"],
            "--auth=trust", "--no-locale", "--encoding=UTF8",
            environment=environment, stdout=subprocess.DEVNULL,
        )
        with (data / "postgresql.conf").open("a") as config:
            config.write(
                f"\nlisten_addresses = ''\nunix_socket_directories = '{socket}'\n"
                "unix_socket_permissions = 0700\nport = 55432\n"
            )
        run(
            "pg_ctl", "-D", str(data), "-l", str(root / "postgres.log"), "-w", "start",
            environment=environment, stdout=subprocess.DEVNULL,
        )
        started = True
        print("Disposable PostgreSQL ready; TCP disabled. Cluster:", root, flush=True)
        project = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-B", str(project / "manage.py"), "test", *args.labels,
             "--settings=paulines.test_settings", "--verbosity=2"],
            cwd=project, env=environment,
        )
        return result.returncode
    finally:
        if started or (data / "postmaster.pid").exists():
            run("pg_ctl", "-D", str(data), "-m", "fast", "-w", "stop",
                environment=environment, stdout=subprocess.DEVNULL)
            print("Only the disposable PostgreSQL cluster was stopped.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
