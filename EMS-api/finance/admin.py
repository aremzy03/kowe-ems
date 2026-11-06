from django.contrib import admin

from finance.models import (
    FeeStructure,
    Invoice,
    InvoiceLineItem,
    Payment,
    SchoolPaymentAccount,
)


@admin.register(SchoolPaymentAccount)
class SchoolPaymentAccountAdmin(admin.ModelAdmin):
    list_display = (
        'gateway',
        'subaccount_code',
        'bank_name',
        'masked_account_number',
        'account_name',
        'platform_commission_pct',
        'is_verified',
        'is_active',
        'created_at',
    )
    readonly_fields = ('subaccount_code', 'account_name', 'created_at')

    def masked_account_number(self, obj):
        return obj.masked_account_number


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_level', 'term', 'amount')
    list_filter = ('class_level', 'term')


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0
    readonly_fields = ('fee_structure', 'amount')
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'term')
    readonly_fields = ('student', 'term', 'total_amount', 'created_at')
    inlines = [InvoiceLineItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'invoice',
        'amount',
        'status',
        'gateway',
        'method',
        'paid_at',
        'created_at',
    )
    list_filter = ('status', 'gateway', 'method')
    readonly_fields = (
        'invoice',
        'amount',
        'reference',
        'gateway',
        'method',
        'initiated_by',
        'recorded_by',
        'created_at',
    )
    search_fields = ('reference',)
