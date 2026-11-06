"""
Permissions for platform endpoints (public schema).

School roles live on SchoolMembership and do not apply here. Platform
operators are shared ``User`` rows with ``is_platform_admin=True`` and
authenticate on the public schema without a tenant membership.
"""

from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    """
    Authenticated user with ``User.is_platform_admin``.

    Also requires the public schema: a school JWT must not reach
    cross-tenant revenue even if the same person later gains a membership.
    """

    message = 'Platform administrator access required.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if not getattr(user, 'is_platform_admin', False):
            return False
        return connection.schema_name == get_public_schema_name()
