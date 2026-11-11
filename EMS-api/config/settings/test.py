"""Pytest settings. SQLite only — the suite never opens the app database.

A file (not ``:memory:``) is required. django-tenants drops the connection
after each schema migrate, and SQLite discards an in-memory database when
that happens. The file lives in the system temp directory.
"""

import os
import tempfile
from pathlib import Path

from .base import *  # noqa: F401, F403

DEBUG = False

_TEST_DB = Path(tempfile.gettempdir()) / f'kowe-ems-pytest-{os.getpid()}.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'config.db.sqlite_tenant',
        'NAME': str(_TEST_DB),
        'TEST': {'NAME': str(_TEST_DB)},
    }
}

# Public migrate and tenant migrate must not share one django_migrations
# history, and contenttypes must not be created twice. See sqlite_tenant.
TENANT_SYNC_ROUTER = 'config.db.sqlite_tenant.router.SqliteTenantRouter'
DATABASE_ROUTERS = [TENANT_SYNC_ROUTER]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
WHATSAPP_BACKEND = 'console'
PAYSTACK_STUB_GATEWAY = False
