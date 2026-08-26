from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, Tenant


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('school_name', 'schema_name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('school_name', 'schema_name')


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain',)
