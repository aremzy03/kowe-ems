"""
URL conf historically used for the public / platform host.

The API is now a single host. Platform, webhook, and school routes all live
in ``config.urls`` (ROOT_URLCONF). This module re-exports that conf so any
remaining PUBLIC_SCHEMA_URLCONF references stay valid.
"""

from config.urls import urlpatterns  # noqa: F401
