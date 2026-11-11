"""SQLite backend that satisfies django-tenants without PostgreSQL schemas.

Tenant and public tables share one database. ``CREATE SCHEMA`` / ``DROP SCHEMA``
and ``pg_catalog`` lookups are translated so ``TenantTestCase`` can migrate.
``schema_name`` and ``tenant`` still change, because the app reads those.
"""

import re

from django.contrib.contenttypes.models import ContentType
from django.db.backends.sqlite3.base import DatabaseWrapper as SqliteDatabaseWrapper
from django.db.migrations.recorder import MigrationRecorder
from django.utils.timezone import now
from django_tenants.utils import get_public_schema_name

_SCHEMA_NAME = re.compile(
    r'(?:CREATE|DROP)\s+SCHEMA(?:\s+IF\s+(?:NOT\s+)?EXISTS)?\s+"?([A-Za-z_][\w$]*)"?',
    re.IGNORECASE,
)
_NOOP = object()


def _migration_table(connection):
    """One django_migrations table per schema name.

    PostgreSQL keeps a migrations table inside each schema. SQLite has one
    database, so the public migrate would otherwise mark tenant migrations
    applied and the tenant migrate would skip creating those tables.
    """
    schema = getattr(connection, 'schema_name', None) or get_public_schema_name()
    if schema == get_public_schema_name():
        return 'django_migrations'
    safe = re.sub(r'\W+', '_', schema.lower()).strip('_')
    return f'django_migrations_{safe}'


def _quote_table(table):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
        raise ValueError(f'Unsafe migration table name: {table}')
    return f'"{table}"'


def _table_exists(connection, table):
    with connection.cursor() as cursor:
        names = connection.introspection.table_names(cursor)
    return table in names


def _has_migration_table(self):
    # Do not cache: the same recorder must follow schema_name changes.
    return _table_exists(self.connection, _migration_table(self.connection))


def _ensure_migration_schema(self):
    table = _migration_table(self.connection)
    if _table_exists(self.connection, table):
        return
    with self.connection.cursor() as cursor:
        cursor.execute(
            f'CREATE TABLE {_quote_table(table)} ('
            '"id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, '
            '"app" varchar(255) NOT NULL, '
            '"name" varchar(255) NOT NULL, '
            '"applied" datetime NOT NULL)'
        )


def _applied_migrations(self):
    table = _migration_table(self.connection)
    if not _table_exists(self.connection, table):
        return {}
    with self.connection.cursor() as cursor:
        cursor.execute(f'SELECT "app", "name" FROM {_quote_table(table)}')
        rows = cursor.fetchall()
    return {(app, name): None for app, name in rows}


def _record_applied(self, app, name):
    self.ensure_schema()
    table = _quote_table(_migration_table(self.connection))
    with self.connection.cursor() as cursor:
        cursor.execute(
            f'INSERT INTO {table} ("app", "name", "applied") VALUES (%s, %s, %s)',
            [app, name, now()],
        )


def _record_unapplied(self, app, name):
    self.ensure_schema()
    table = _quote_table(_migration_table(self.connection))
    with self.connection.cursor() as cursor:
        cursor.execute(
            f'DELETE FROM {table} WHERE "app" = %s AND "name" = %s',
            [app, name],
        )


def _flush_migrations(self):
    self.ensure_schema()
    table = _quote_table(_migration_table(self.connection))
    with self.connection.cursor() as cursor:
        cursor.execute(f'DELETE FROM {table}')


if not getattr(MigrationRecorder, '_kowe_schema_tables', False):
    MigrationRecorder.has_table = _has_migration_table
    MigrationRecorder.ensure_schema = _ensure_migration_schema
    MigrationRecorder.applied_migrations = _applied_migrations
    MigrationRecorder.record_applied = _record_applied
    MigrationRecorder.record_unapplied = _record_unapplied
    MigrationRecorder.flush = _flush_migrations
    MigrationRecorder._kowe_schema_tables = True


class FakeTenant:
    def __init__(self, schema_name, tenant_type=None):
        self.schema_name = schema_name
        self.tenant_type = tenant_type

    def get_tenant_type(self):
        return self.tenant_type


class DatabaseWrapper(SqliteDatabaseWrapper):
    include_public_schema = True

    def __init__(self, *args, **kwargs):
        self.search_path_set_schemas = None
        self._setting_search_path = False
        self.tenant = None
        self.schema_name = None
        self._sqlite_schemas = {get_public_schema_name().lower()}
        super().__init__(*args, **kwargs)
        self.set_schema_to_public()

    def set_tenant(self, tenant, include_public=True):
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.include_public_schema = include_public
        self.settings_dict['SCHEMA'] = self.schema_name
        self.search_path_set_schemas = None
        ContentType.objects.clear_cache()

    def set_schema(self, schema_name, include_public=True, tenant_type=None):
        self.set_tenant(
            FakeTenant(schema_name=schema_name, tenant_type=tenant_type),
            include_public,
        )

    def set_schema_to_public(self):
        self.set_tenant(FakeTenant(schema_name=get_public_schema_name()))

    def _cursor(self, name=None):
        cursor = super()._cursor(name)
        if getattr(cursor, '_kowe_schema_sql', False):
            return cursor
        original_execute = cursor.execute

        def execute(sql, params=None):
            rewritten = self._rewrite_schema_sql(sql, params)
            if rewritten is _NOOP:
                return original_execute('SELECT 1')
            if rewritten is not None:
                sql, params = rewritten
            if params is None:
                return original_execute(sql)
            return original_execute(sql, params)

        cursor.execute = execute
        cursor._kowe_schema_sql = True
        return cursor

    def _rewrite_schema_sql(self, sql, params):
        statement = sql.decode() if isinstance(sql, (bytes, bytearray)) else str(sql)
        upper = statement.lstrip().upper()
        if upper.startswith('CREATE SCHEMA'):
            match = _SCHEMA_NAME.search(statement)
            if match:
                self._sqlite_schemas.add(match.group(1).lower())
            return _NOOP
        if upper.startswith('DROP SCHEMA'):
            # Leave the tables in place. A real DROP SCHEMA would remove the
            # only copy of every tenant table, including ones still in use.
            return _NOOP
        if 'PG_NAMESPACE' in upper:
            name = str(params[0]).lower() if params else ''
            exists = 1 if name in self._sqlite_schemas else 0
            return ('SELECT %s', (exists,))
        if upper.startswith('SET SEARCH_PATH'):
            return _NOOP
        return None
