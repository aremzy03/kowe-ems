from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, PlatformTransactionLog, SubaccountTenantMap, Tenant, WebhookLog


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    change_form_template = 'admin/platform_admin/tenant/change_form.html'
    list_display = ('school_name', 'schema_name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('school_name', 'schema_name')


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain',)


@admin.register(SubaccountTenantMap)
class SubaccountTenantMapAdmin(admin.ModelAdmin):
    list_display = ('subaccount_code', 'tenant', 'created_at')
    search_fields = ('subaccount_code', 'tenant__school_name', 'tenant__schema_name')
    readonly_fields = ('subaccount_code', 'tenant', 'created_at')


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        'received_at',
        'outcome',
        'event',
        'reference',
        'subaccount_code',
        'signature_valid',
        'tenant',
    )
    list_filter = ('outcome', 'signature_valid', 'event')
    search_fields = ('reference', 'subaccount_code', 'event')
    readonly_fields = (
        'received_at',
        'signature_valid',
        'event',
        'reference',
        'subaccount_code',
        'tenant',
        'outcome',
        'error_message',
        'payload',
    )


@admin.register(PlatformTransactionLog)
class PlatformTransactionLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'tenant',
        'payment_reference',
        'gross_amount',
        'commission_amount',
        'net_to_school',
    )
    list_filter = ('tenant',)
    search_fields = ('payment_reference', 'tenant__school_name', 'tenant__schema_name')
    readonly_fields = (
        'tenant',
        'payment_reference',
        'gross_amount',
        'commission_amount',
        'net_to_school',
        'timestamp',
    )
