import uuid

from django.conf import settings
from django.db import models


class NotificationLog(models.Model):
    """
    Tenant-scoped record of one outbound notification attempt.

    One row is one recipient on one channel for one trigger (an invoice,
    a payment, or a published term-result summary). The Celery task in
    ``communications.tasks`` owns delivery. Request handlers insert a
    ``queued`` row and enqueue the task. An admin resend sets that same
    failed row back to ``queued`` and enqueues it again; it does not
    insert a second log.

    ``recipient`` is a cross-schema FK to the public User, same pattern as
    SchoolMembership. ``related_object_id`` stores the UUID primary key of
    the Invoice, Payment, or TermResultSummary that caused the send —
    those three models all use UUID PKs, so a single column is enough to
    trace the row without a content-type join.
    """

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class TriggerType(models.TextChoices):
        INVOICE_GENERATED = 'invoice_generated', 'Invoice generated'
        PAYMENT_CONFIRMED = 'payment_confirmed', 'Payment confirmed'
        RESULT_PUBLISHED = 'result_published', 'Result published'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notification_logs',
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, db_index=True)
    trigger_type = models.CharField(
        max_length=32,
        choices=TriggerType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    related_object_id = models.UUIDField(
        db_index=True,
        help_text='Invoice, Payment, or TermResultSummary primary key.',
    )
    error_message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.trigger_type} via {self.channel} '
            f'→ {self.recipient_id} [{self.status}]'
        )
