"""
Header- and JWT-based tenant resolution.

Replaces django-tenants' ``TenantMainMiddleware`` (Host → schema). The API is
a single host; the school schema is selected per request from:

1. A valid JWT ``tenant_schema`` claim (access Bearer or refresh cookie)
2. Else ``X-Tenant-Slug``, looked up against Domain / Tenant
3. Else public schema for platform/webhook/auth/admin paths, or 400
"""

from __future__ import annotations

import json

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django_tenants.utils import get_public_schema_name, get_tenant_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from platform_admin.tenancy import (
    TENANT_SLUG_HEADER,
    is_public_schema_name,
    normalize_tenant_slug,
    resolve_tenant_from_schema_name,
    resolve_tenant_from_slug,
)

# Paths that may run on the public schema without a tenant signal.
# ``/admin`` (no trailing slash) is public too, so CommonMiddleware can
# APPEND_SLASH to ``/admin/`` instead of this middleware returning 400.
_PUBLIC_PATH_PREFIXES = (
    '/api/webhooks/',
    '/api/platform/',
    '/api/auth/',
    '/admin/',
)

_MISSING_DETAIL = 'Tenant identification required'
_UNKNOWN_SLUG_DETAIL = 'Unknown tenant.'
_INVALID_CLAIM_DETAIL = 'Invalid tenant claim in token.'


def _json_error(detail: str, status: int) -> HttpResponse:
    payload = json.dumps({'detail': detail})
    return HttpResponse(payload, status=status, content_type='application/json')


def _bearer_token(request) -> str:
    header = request.META.get('HTTP_AUTHORIZATION') or ''
    if not header.lower().startswith('bearer '):
        return ''
    return header.split(' ', 1)[1].strip()


def _decode_untyped(raw: str):
    if not raw:
        return None
    try:
        return UntypedToken(raw)
    except (TokenError, KeyError, TypeError, ValueError):
        return None


def _jwt_from_request(request):
    """
    Return a verified JWT payload or None.

    Expired / malformed tokens are treated as absent (fall through to header),
    not as an auth error — DRF JWT authentication still 401s the view.
    """
    token = _decode_untyped(_bearer_token(request))
    if token is not None:
        return token
    cookie_name = getattr(settings, 'AUTH_REFRESH_COOKIE_NAME', 'refresh_token')
    return _decode_untyped(request.COOKIES.get(cookie_name) or '')


def _is_public_path(path: str) -> bool:
    if path == '/admin':
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


class HeaderTenantMiddleware:
    """
    First middleware: set ``connection`` schema and ``request.tenant``.

    Must run before SecurityMiddleware / CORS so views and later middleware
    see the correct search_path. OPTIONS is forced public so CORS preflight
    can succeed without tenant headers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Public schema until a school claim or slug selects one.
        # ``request.tenant`` must be an object with ``schema_name``: django-tenants'
        # ``is_public_schema`` tag reads it, and ``None`` crashes the admin index.
        connection.set_schema_to_public()
        request.tenant = connection.tenant

        if request.method == 'OPTIONS':
            self._bind_public_tenant(request)
            return self.get_response(request)

        jwt = _jwt_from_request(request)
        if jwt is not None:
            claim = jwt.get('tenant_schema')
            if not claim:
                return _json_error(_INVALID_CLAIM_DETAIL, 401)
            if is_public_schema_name(claim):
                self._bind_public_tenant(request)
                return self.get_response(request)
            tenant = resolve_tenant_from_schema_name(claim)
            if tenant is None:
                return _json_error(_INVALID_CLAIM_DETAIL, 401)
            self._activate_tenant(request, tenant)
            return self.get_response(request)

        slug = normalize_tenant_slug(
            request.headers.get(TENANT_SLUG_HEADER)
            or request.META.get('HTTP_X_TENANT_SLUG')
        )
        if slug:
            tenant = resolve_tenant_from_slug(slug)
            if tenant is None:
                return _json_error(_UNKNOWN_SLUG_DETAIL, 400)
            self._activate_tenant(request, tenant)
            return self.get_response(request)

        if _is_public_path(request.path):
            self._bind_public_tenant(request)
            return self.get_response(request)

        return _json_error(_MISSING_DETAIL, 400)

    @staticmethod
    def _bind_public_tenant(request):
        """
        Attach the public tenant for a request that stays on the public schema.

        Prefer the real public ``Tenant`` row (what Host middleware would set).
        If that row does not exist, keep the ``FakeTenant`` already installed by
        ``connection.set_schema_to_public()`` — it has ``schema_name`` equal to
        ``get_public_schema_name()``, which is all ``is_public_schema`` checks.
        """
        public_name = get_public_schema_name()
        tenant = get_tenant_model().objects.filter(schema_name=public_name).first()
        if tenant is None:
            request.tenant = connection.tenant
            return
        connection.set_tenant(tenant)
        request.tenant = tenant

    @staticmethod
    def _activate_tenant(request, tenant):
        request.tenant = tenant
        connection.set_tenant(tenant)
