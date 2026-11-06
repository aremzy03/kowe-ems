from django.urls import path

from platform_admin.views import (
    PlatformRevenueOverviewView,
    PlatformTenantListView,
    PlatformWebhookLogListView,
)

urlpatterns = [
    path(
        'revenue/',
        PlatformRevenueOverviewView.as_view(),
        name='platform-revenue-overview',
    ),
    path(
        'tenants/',
        PlatformTenantListView.as_view(),
        name='platform-tenant-list',
    ),
    path(
        'webhooks/',
        PlatformWebhookLogListView.as_view(),
        name='platform-webhook-log-list',
    ),
]
