"""Test helpers for header-based tenant resolution."""


def set_tenant_slug(client, tenant):
    """Send ``X-Tenant-Slug`` so APIClient requests resolve this school schema."""
    client.defaults['HTTP_X_TENANT_SLUG'] = tenant.schema_name
    return client
