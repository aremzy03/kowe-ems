from django.urls import include, path
from rest_framework.routers import DefaultRouter

from finance.views import (
    CollectionDashboardView,
    FeeStructureViewSet,
    InitializePaymentView,
    InvoiceGenerateView,
    MyInvoicesView,
    RecordManualPaymentView,
    SchoolPaymentAccountView,
    StaffInvoiceListView,
    VerifyPaymentView,
)

router = DefaultRouter()
router.register('fee-structures', FeeStructureViewSet, basename='fee-structure')

urlpatterns = [
    path(
        'payment-account/',
        SchoolPaymentAccountView.as_view(),
        name='finance-payment-account',
    ),
    path(
        'invoices/generate/',
        InvoiceGenerateView.as_view(),
        name='finance-invoice-generate',
    ),
    path(
        'invoices/',
        StaffInvoiceListView.as_view(),
        name='finance-invoice-list',
    ),
    path(
        'my-invoices/',
        MyInvoicesView.as_view(),
        name='finance-my-invoices',
    ),
    path(
        'payments/initialize/',
        InitializePaymentView.as_view(),
        name='finance-payment-initialize',
    ),
    path(
        'payments/verify/',
        VerifyPaymentView.as_view(),
        name='finance-payment-verify',
    ),
    path(
        'payments/manual/',
        RecordManualPaymentView.as_view(),
        name='finance-payment-manual',
    ),
    path(
        'dashboard/collections/',
        CollectionDashboardView.as_view(),
        name='finance-collection-dashboard',
    ),
    path('', include(router.urls)),
]
