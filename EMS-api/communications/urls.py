from django.urls import include, path
from rest_framework.routers import DefaultRouter

from communications.views import NotificationLogViewSet

router = DefaultRouter()
router.register(
    'notifications',
    NotificationLogViewSet,
    basename='notification-log',
)

urlpatterns = [
    path('', include(router.urls)),
]
