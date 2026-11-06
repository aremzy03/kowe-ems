"""
Tenant-aware DRF permission classes based on SchoolMembership.role.

Roles live on per-tenant SchoolMembership, not on the shared User. These
classes resolve the caller's active membership in the *current* tenant schema
(set by HeaderTenantMiddleware) and attach it to ``request.membership`` so
viewsets can filter querysets without repeating the lookup.

Admin and bursar also require a confirmed TOTP device (shared/public schema).
Login-time 2FA is not enough on its own — these gates block role endpoints if
enrollment was skipped or a pre_2fa token is still in use.
"""

from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.permissions import BasePermission

from accounts.two_factor import (
    request_uses_pre_2fa_token,
    role_requires_2fa,
    user_has_confirmed_totp,
)
from memberships.models import SchoolMembership

_MEMBERSHIP_RESOLVED_ATTR = '_ems_membership_resolved'

TWO_FACTOR_REQUIRED_MESSAGE = (
    'Two-factor authentication is required for this role. '
    'Enroll at POST /api/auth/2fa/enroll/ (then confirm), or finish login '
    'with POST /api/auth/2fa/verify/ if already enrolled.'
)


def resolve_request_membership(request):
    """
    Return the active SchoolMembership for ``request.user`` in this tenant.

    Caches the result on ``request.membership`` (may be ``None``) and sets
    ``request._ems_membership_resolved`` so repeated permission checks and
    later queryset filters do not hit the DB again.

    Returns None when the user is anonymous, the connection is on the public
    schema (no school context), or there is no active membership for this user
    in the current tenant.
    """
    if getattr(request, _MEMBERSHIP_RESOLVED_ATTR, False):
        return getattr(request, 'membership', None)

    membership = None
    user = getattr(request, 'user', None)
    if (
        user is not None
        and getattr(user, 'is_authenticated', False)
        and connection.schema_name != get_public_schema_name()
    ):
        membership = (
            SchoolMembership.objects.filter(user_id=user.pk, is_active=True)
            .select_related('user')
            .first()
        )

    request.membership = membership
    setattr(request, _MEMBERSHIP_RESOLVED_ATTR, True)
    return membership


class HasActiveMembership(BasePermission):
    """
    Authenticated user with an active SchoolMembership in the current tenant.

    Being logged in is not enough: a valid JWT from another school must not
    grant access when the JWT ``tenant_schema`` (or ``X-Tenant-Slug``) resolves
    to a different tenant schema.
    """

    message = 'Active membership at this school is required.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        return resolve_request_membership(request) is not None


class _HasMembershipRole(HasActiveMembership):
    """Base for role-gated permissions. Subclasses set ``allowed_roles``."""

    allowed_roles = ()
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.membership.role not in self.allowed_roles:
            # Prefer the subclass role message (may have been overwritten by 2FA).
            self.message = type(self).message
            return False
        # Defense in depth: admin/bursar need confirmed TOTP even if they hold
        # a full JWT (e.g. enrollment was skipped, or a pre_2fa token is used).
        if role_requires_2fa(request.membership.role):
            if request_uses_pre_2fa_token(request) or not user_has_confirmed_totp(
                request.user
            ):
                self.message = TWO_FACTOR_REQUIRED_MESSAGE
                return False
        return True


class IsSchoolAdmin(_HasMembershipRole):
    allowed_roles = (SchoolMembership.Role.ADMIN,)
    message = 'School admin role required.'


class IsTeacher(_HasMembershipRole):
    allowed_roles = (SchoolMembership.Role.TEACHER,)
    message = 'Teacher role required.'


class IsBursar(_HasMembershipRole):
    allowed_roles = (SchoolMembership.Role.BURSAR,)
    message = 'Bursar role required.'


class IsParent(_HasMembershipRole):
    allowed_roles = (SchoolMembership.Role.PARENT,)
    message = 'Parent role required.'


class IsAdminOrBursar(_HasMembershipRole):
    """Composable gate for endpoints shared by admin and bursar (e.g. finance)."""

    allowed_roles = (
        SchoolMembership.Role.ADMIN,
        SchoolMembership.Role.BURSAR,
    )
    message = 'School admin or bursar role required.'


class IsAdminOrTeacher(_HasMembershipRole):
    """
    Composable gate for endpoints shared by admin and teacher
    (e.g. read-only ClassLevel / Arm / Subject lists for marks entry).
    """

    allowed_roles = (
        SchoolMembership.Role.ADMIN,
        SchoolMembership.Role.TEACHER,
    )
    message = 'School admin or teacher role required.'
