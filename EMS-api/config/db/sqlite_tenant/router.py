"""Test router: tenant schemas share the tables already created for public."""

from django.db import connections
from django_tenants.routers import TenantSyncRouter
from django_tenants.utils import get_public_schema_name, get_tenant_database_alias


class SqliteTenantRouter(TenantSyncRouter):
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        allowed = super().allow_migrate(
            db, app_label, model_name=model_name, **hints
        )
        if allowed is False or db != get_tenant_database_alias():
            return allowed
        connection = connections[db]
        # contenttypes is in both SHARED_APPS and TENANT_APPS. The public
        # migrate already created its tables in this one SQLite file.
        if (
            connection.vendor == 'sqlite'
            and connection.schema_name != get_public_schema_name()
            and app_label == 'contenttypes'
        ):
            return False
        return allowed
