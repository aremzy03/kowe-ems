from django.urls import path

from platform_admin.views import PlatformRevenueOverviewView

urlpatterns = [
    path(
        'revenue/',
        PlatformRevenueOverviewView.as_view(),
        name='platform-revenue-overview',
    ),
]
