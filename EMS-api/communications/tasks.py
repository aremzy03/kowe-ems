"""
Async notification delivery.

The web process only inserts a NotificationLog and calls
``enqueue_notification``. This task loads that row inside the tenant
schema (workers have no request, so HeaderTenantMiddleware never runs)
and hands it to the channel sender registered by Prompts 2–3.

Retry policy (max 3 attempts = 1 try + 2 retries):

* ``TransientNotificationError`` (network, rate limit) — exponential
  backoff, then ``failed`` once retries are exhausted.
* ``PermanentNotificationError`` (bad phone, rejected template, or no
  sender registered yet) — ``failed`` immediately, no retry.

Task signature::

    send_notification(notification_log_id: str, schema_name: str)

``schema_name`` is required. A log id alone cannot be looked up: the row
lives in a tenant schema, and the worker connection defaults to public.
"""

from celery import shared_task
from celery.utils.time import get_exponential_backoff_interval
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

from communications.exceptions import (
    PermanentNotificationError,
    TransientNotificationError,
)
from communications.models import NotificationLog

# 3 total attempts: the first run plus two retries.
MAX_NOTIFICATION_ATTEMPTS = 3
NOTIFICATION_MAX_RETRIES = MAX_NOTIFICATION_ATTEMPTS - 1

# Exponential backoff: 2s, 4s, 8s… capped at 10 minutes, with full jitter
# so a bulk publish does not retry every recipient on the same second.
RETRY_BACKOFF_FACTOR = 2
RETRY_BACKOFF_MAXIMUM = 600

# sender(notification_log) -> None, or raise Transient/Permanent.
_CHANNEL_SENDERS = {}


def register_channel_sender(channel, sender):
    """Register the callable Prompts 2–3 use for one channel."""
    if channel not in NotificationLog.Channel.values:
        raise ValueError(f'Unknown notification channel: {channel!r}')
    if not callable(sender):
        raise TypeError('sender must be callable')
    _CHANNEL_SENDERS[channel] = sender


def get_channel_sender(channel):
    return _CHANNEL_SENDERS.get(channel)


def clear_channel_senders():
    """Test helper. Production senders register once at import."""
    _CHANNEL_SENDERS.clear()


def dispatch_notification(log):
    """
    Call the sender for ``log.channel``.

    No sender registered is permanent: retrying will not create one, and
    a missing Prompt 2/3 import must not wedge the queue.
    """
    sender = _CHANNEL_SENDERS.get(log.channel)
    if sender is None:
        raise PermanentNotificationError(
            f"No sender registered for channel '{log.channel}'."
        )
    sender(log)


def retry_countdown(retries):
    """Seconds to wait before attempt ``retries + 1`` (0-based)."""
    return get_exponential_backoff_interval(
        factor=RETRY_BACKOFF_FACTOR,
        retries=retries,
        maximum=RETRY_BACKOFF_MAXIMUM,
        full_jitter=True,
    )


def enqueue_notification(log, *, countdown=None):
    """
    Queue delivery. Does not send.

    Must be called while the connection is on the log's tenant schema.
    A resend sets status back to ``queued`` (see
    ``requeue_failed_notification``) before calling this; the task
    ignores rows that are not queued.

    ``countdown`` (seconds) delays the worker. WhatsApp uses it so a
    bulk enqueue is a lane of sends, not one simultaneous burst. Email
    leaves it unset and publishes immediately. Zero or negative is
    immediate, same as omitting it.
    """
    schema_name = connection.schema_name
    if not schema_name or schema_name == get_public_schema_name():
        raise RuntimeError(
            'enqueue_notification must run inside a tenant schema.'
        )
    if log.status != NotificationLog.Status.QUEUED:
        raise RuntimeError(
            'enqueue_notification only accepts status=queued '
            f'(got {log.status!r}).'
        )
    delay = 0.0
    if countdown is not None:
        delay = float(countdown)
    if delay > 0:
        send_notification.apply_async(
            args=(str(log.pk), schema_name),
            countdown=delay,
        )
        return
    send_notification.delay(str(log.pk), schema_name)


def requeue_failed_notification(log):
    """
    Admin resend of one failed NotificationLog.

    Sets that same row back to ``queued``, clears ``error_message`` and
    ``sent_at``, and publishes ``send_notification`` after the status
    write commits. Does not insert a second log. Queued and sent rows
    are refused: the task would ignore them, and a second publish must
    not deliver a message the admin did not mean to repeat.

    A single resend is not a class-wide burst, so it does not take a
    WhatsApp pair-limit slot. The original bulk enqueue already did.

    Must run inside the log's tenant schema. Broker errors are logged
    and do not roll the row back (same ``on_commit(..., robust=True)``
    rule as invoice and payment notifications).
    """
    schema_name = connection.schema_name
    if not schema_name or schema_name == get_public_schema_name():
        raise RuntimeError(
            'requeue_failed_notification must run inside a tenant schema.'
        )

    with transaction.atomic():
        locked = NotificationLog.objects.select_for_update().get(pk=log.pk)
        if locked.status != NotificationLog.Status.FAILED:
            raise ValidationError('Only failed notifications can be resent.')
        locked.status = NotificationLog.Status.QUEUED
        locked.error_message = None
        locked.sent_at = None
        locked.save(update_fields=['status', 'error_message', 'sent_at'])
        log_id = locked.pk
        transaction.on_commit(
            lambda log_id=log_id: _publish_requeued_notification(log_id),
            robust=True,
        )

    log.refresh_from_db()
    return log


def _publish_requeued_notification(log_id):
    """Publish one row that is already queued. Runs on commit."""
    fresh = NotificationLog.objects.get(pk=log_id)
    enqueue_notification(fresh)


def _clip(message):
    text = (message or '').strip()
    if len(text) > 2000:
        return text[:1997] + '...'
    return text or None


def _mark_failed(log, message):
    log.status = NotificationLog.Status.FAILED
    log.error_message = _clip(message)
    log.save(update_fields=['status', 'error_message'])


def _mark_sent(log):
    log.status = NotificationLog.Status.SENT
    log.error_message = None
    log.sent_at = timezone.now()
    log.save(update_fields=['status', 'error_message', 'sent_at'])


@shared_task(
    bind=True,
    max_retries=NOTIFICATION_MAX_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_notification(self, notification_log_id, schema_name):
    """
    Deliver one NotificationLog and record the outcome.

    Signature: ``send_notification(notification_log_id, schema_name)``.
    Retry: ``max_retries=2`` (3 attempts) with exponential backoff via
    ``retry_countdown`` on ``TransientNotificationError`` only.
    """
    with schema_context(schema_name):
        try:
            log = NotificationLog.objects.get(pk=notification_log_id)
        except (NotificationLog.DoesNotExist, ValidationError, ValueError, TypeError):
            # Bad id or already gone. Retrying will not create the row.
            return None

        # Sent rows are not delivered again. Failed rows stay failed
        # until a caller sets them back to queued and re-enqueues.
        if log.status != NotificationLog.Status.QUEUED:
            return str(log.pk)

        try:
            dispatch_notification(log)
        except PermanentNotificationError as exc:
            _mark_failed(log, str(exc))
            return str(log.pk)
        except TransientNotificationError as exc:
            if self.request.retries >= self.max_retries:
                _mark_failed(log, str(exc))
                return str(log.pk)
            log.error_message = _clip(str(exc))
            log.save(update_fields=['error_message'])
            raise self.retry(
                exc=exc,
                countdown=retry_countdown(self.request.retries),
            )
        else:
            _mark_sent(log)
            return str(log.pk)
