import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class SchoolMembership(models.Model):
    """
    Per-tenant membership: links a shared User to THIS school with a role.

    Lives in the tenant schema. FK to AUTH_USER_MODEL is a cross-schema
    reference to the public User table (supported by django-tenants).
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', 'Teacher'
        BURSAR = 'bursar', 'Bursar'
        PARENT = 'parent', 'Parent'

    STAFF_ROLES = (Role.ADMIN, Role.TEACHER, Role.BURSAR)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='school_memberships',
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['user'], name='uniq_schoolmembership_user'),
        ]

    def __str__(self):
        return f'{self.user} ({self.role})'


def _default_invite_token():
    return secrets.token_urlsafe(32)


def _default_invite_expires_at():
    days = getattr(settings, 'STAFF_INVITE_EXPIRY_DAYS', 7)
    return timezone.now() + timedelta(days=days)


class StaffInvite(models.Model):
    """
    Tenant-scoped invitation for staff roles (admin / teacher / bursar).

    Staff are not self-signup; an existing school admin issues an invite.
    The invite token is single-use and time-limited.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', 'Teacher'
        BURSAR = 'bursar', 'Bursar'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        EXPIRED = 'expired', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_invites_sent',
    )
    token = models.CharField(max_length=64, unique=True, default=_default_invite_token, editable=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField(default=_default_invite_expires_at)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} → {self.role} ({self.status})'

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def mark_expired_if_needed(self):
        """Persist EXPIRED when a pending invite has passed expires_at."""
        if self.status == self.Status.PENDING and self.is_expired():
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status'])
        return self.status
