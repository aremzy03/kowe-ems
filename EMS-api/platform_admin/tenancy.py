"""
Explicit tenant lookup (Domain / Tenant tables) for header-based resolution.

The Domain model is no longer consumed by django-tenants' Host mapper. It is
a lookup table: ``X-Tenant-Slug`` (or a JWT ``tenant_schema`` claim) → schema.
"""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context

from platform_admin.models import Domain, Tenant

TENANT_SLUG_HEADER = 'X-Tenant-Slug'


def normalize_tenant_slug(raw: str | None) -> str:
    if raw is None:
        return ''
    return raw.strip().lower()


def tenant_slug_for(tenant: Tenant) -> str:
    """
    Canonical slug the frontend should send.

    Prefer the first label of the primary Domain (``testacademy`` from
    ``testacademy.localhost``). Fall back to ``schema_name`` with underscores
    restored to hyphens.
    """
    domain = (
        tenant.domains.filter(is_primary=True).first()
        or tenant.domains.order_by('domain').first()
    )
    if domain and domain.domain:
        return domain.domain.split('.')[0].lower()
    return tenant.schema_name.replace('_', '-')


def resolve_tenant_from_slug(slug: str) -> Tenant | None:
    """
    Map a slug string to an active Tenant.

    Accepts:
    - exact Domain.domain (``testacademy.localhost``)
    - first label of a Domain (``testacademy`` → ``testacademy.localhost``)
    - Tenant.schema_name (``testacademy``; hyphens become underscores)
    """
    slug = normalize_tenant_slug(slug)
    if not slug:
        return None

    public = get_public_schema_name()
    with schema_context(public):
        domain_match = (
            Domain.objects.select_related('tenant')
            .filter(domain__iexact=slug)
            .first()
        )
        if domain_match is None:
            domain_match = (
                Domain.objects.select_related('tenant')
                .filter(domain__istartswith=f'{slug}.')
                .order_by('domain')
                .first()
            )
        if domain_match is not None:
            tenant = domain_match.tenant
            if tenant.is_active:
                return tenant
            return None

        schema_name = slug.replace('-', '_')
        tenant = Tenant.objects.filter(schema_name=schema_name).first()
        if tenant is not None and tenant.is_active:
            return tenant
    return None


def resolve_tenant_from_schema_name(schema_name: str) -> Tenant | None:
    """Active Tenant for a JWT ``tenant_schema`` claim. Public schema → None."""
    schema_name = (schema_name or '').strip()
    if not schema_name or schema_name == get_public_schema_name():
        return None
    with schema_context(get_public_schema_name()):
        tenant = Tenant.objects.filter(schema_name=schema_name).first()
        if tenant is not None and tenant.is_active:
            return tenant
    return None


def is_public_schema_name(schema_name: str | None) -> bool:
    return (schema_name or '').strip() == get_public_schema_name()


def frontend_origin_for_tenant(tenant: Tenant) -> str:
    """
    Origin of the school's frontend subdomain (invite / signup links).

    ``TENANT_FRONTEND_ORIGIN_TEMPLATE`` may include ``{slug}`` and ``{domain}``.
    When empty, ``{scheme}://{primary-domain}[:port]`` is used.
    """
    slug = tenant_slug_for(tenant)
    domain_obj = (
        tenant.domains.filter(is_primary=True).first()
        or tenant.domains.order_by('domain').first()
    )
    domain = domain_obj.domain if domain_obj else f'{slug}.localhost'
    template = getattr(settings, 'TENANT_FRONTEND_ORIGIN_TEMPLATE', '') or ''
    if template:
        return template.format(slug=slug, domain=domain).rstrip('/')

    scheme = getattr(settings, 'TENANT_FRONTEND_SCHEME', 'https')
    port = str(getattr(settings, 'TENANT_FRONTEND_PORT', '') or '').strip()
    origin = f'{scheme}://{domain}'
    if port:
        origin = f'{origin}:{port}'
    return origin


def current_schema_name() -> str:
    return connection.schema_name
