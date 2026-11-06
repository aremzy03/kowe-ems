"""
TOTP two-factor helpers (shared/public schema via django-otp).

Design (tenant role × shared User login):
- Login is identified by ``X-Tenant-Slug`` (or a JWT ``tenant_schema`` claim),
  so the school schema is already set before password validation runs.
- After password succeeds we resolve SchoolMembership in *this* tenant.
- teacher/parent → issue normal JWT access + refresh immediately.
- admin/bursar → do **not** issue full tokens; return a short-lived pre_2fa
  AccessToken. The client must either enroll (first time) or submit a TOTP
  code, then we mint full tokens. Devices live on the shared User so a person
  who is admin at school A and bursar at school B enrolls once.
"""

from __future__ import annotations

import base64
import io
from datetime import timedelta

import qrcode
from django.conf import settings
from django.db import connection
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_tenants.utils import get_public_schema_name
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from memberships.models import SchoolMembership

PRE_2FA_PURPOSE = 'pre_2fa'
ROLES_REQUIRING_2FA = frozenset(
    {
        SchoolMembership.Role.ADMIN,
        SchoolMembership.Role.BURSAR,
    }
)


def role_requires_2fa(role: str | None) -> bool:
    return role in ROLES_REQUIRING_2FA


def user_has_confirmed_totp(user) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return TOTPDevice.objects.filter(user_id=user.pk, confirmed=True).exists()


def get_confirmed_totp_device(user):
    return (
        TOTPDevice.objects.filter(user_id=user.pk, confirmed=True)
        .order_by('id')
        .first()
    )


def get_pending_totp_device(user):
    return (
        TOTPDevice.objects.filter(user_id=user.pk, confirmed=False)
        .order_by('-id')
        .first()
    )


def stamp_tenant_claims(token, user=None):
    """Embed schema (+ role when known) so middleware can select the tenant."""
    from django.db import connection
    from django_tenants.utils import get_public_schema_name

    token['school_id'] = None
    token['tenant_schema'] = connection.schema_name
    if user is None:
        return token
    membership = resolve_login_membership(user)
    if membership is not None:
        token['role'] = membership.role
    elif (
        getattr(user, 'is_platform_admin', False)
        and connection.schema_name == get_public_schema_name()
    ):
        token['role'] = 'platform_admin'
    return token


def mint_pre_2fa_token(user) -> str:
    """Short-lived access token that authenticates only for 2FA enroll/verify."""
    token = AccessToken.for_user(user)
    token.set_exp(
        lifetime=getattr(settings, 'PRE_2FA_TOKEN_LIFETIME', timedelta(minutes=10))
    )
    token['ems_purpose'] = PRE_2FA_PURPOSE
    stamp_tenant_claims(token, user)
    return str(token)


def access_token_is_pre_2fa(token: AccessToken) -> bool:
    return token.get('ems_purpose') == PRE_2FA_PURPOSE


def request_uses_pre_2fa_token(request) -> bool:
    """True when the Bearer token is a pending-2FA login token (not full session)."""
    auth = getattr(request, 'auth', None)
    if auth is None:
        return False
    try:
        return access_token_is_pre_2fa(auth)
    except (AttributeError, TypeError):
        return False


def parse_pre_2fa_token(raw: str) -> AccessToken:
    try:
        token = AccessToken(raw)
    except TokenError as exc:
        raise InvalidToken('Invalid or expired pre-auth token.') from exc
    if not access_token_is_pre_2fa(token):
        raise InvalidToken('Token is not a pre-2FA login token.')
    return token


def issue_auth_tokens_for_user(user) -> dict:
    """Build the same payload shape SimpleJWT TokenObtainPair would return."""
    refresh = RefreshToken.for_user(user)
    stamp_tenant_claims(refresh, user)
    access = refresh.access_token
    return {
        'access': str(access),
        'refresh': str(refresh),
    }


def resolve_login_membership(user):
    """
    Active SchoolMembership for ``user`` in the currently resolved tenant.

    Returns None on the public schema or when the user has no active membership
    at this school.
    """
    if connection.schema_name == get_public_schema_name():
        return None
    return (
        SchoolMembership.objects.filter(user_id=user.pk, is_active=True)
        .select_related('user')
        .first()
    )


def create_unconfirmed_totp_device(user) -> TOTPDevice:
    """
    Replace any prior unconfirmed device and create a fresh one.

    Refuses if a confirmed device already exists — password / pre_2fa alone
    must never replace an enrolled authenticator (account-takeover guard).
    Deliberate re-enroll (existing TOTP proof / admin reset) is out of scope.
    """
    if user_has_confirmed_totp(user):
        raise ValueError(
            'Cannot create a TOTP device while a confirmed device exists.'
        )
    TOTPDevice.objects.filter(user_id=user.pk, confirmed=False).delete()
    name = getattr(settings, 'TOTP_DEVICE_NAME', 'default')
    return TOTPDevice.objects.create(user=user, name=name, confirmed=False)


def totp_qr_data_uri(config_url: str) -> str:
    img = qrcode.make(config_url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def verify_user_totp(user, code: str) -> bool:
    """Verify against a confirmed device, or the latest unconfirmed during enroll."""
    code = (code or '').strip()
    if not code:
        return False
    device = get_confirmed_totp_device(user) or get_pending_totp_device(user)
    if device is None:
        return False
    return bool(device.verify_token(code))
