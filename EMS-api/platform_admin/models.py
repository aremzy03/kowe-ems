import uuid

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    """
    School tenant (public schema). ``schema_name`` is inherited from TenantMixin.
    TenantMixin is abstract and does not define a primary key, so we use a UUID PK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['school_name']

    def __str__(self):
        return self.school_name


class Domain(DomainMixin):
    """Standard django-tenants domain mapping (hostname → Tenant)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        ordering = ['domain']
