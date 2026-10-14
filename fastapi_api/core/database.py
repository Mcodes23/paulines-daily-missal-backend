"""Connection lifecycle for synchronous ORM operations served by FastAPI workers."""

from functools import wraps

from django.db import connections


def database_operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        for connection in connections.all():
            if not connection.in_atomic_block:
                connection.close_if_unusable_or_obsolete()
        try:
            return function(*args, **kwargs)
        finally:
            for connection in connections.all():
                if not connection.in_atomic_block:
                    connection.close()

    return wrapped
