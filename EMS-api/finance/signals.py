"""
Invoice and payment notification triggers.

``EmailNotificationService.send_*`` and the WhatsApp equivalents insert
a new log on every call. These receivers are the dedup:

* ``invoice_generated`` runs on insert only. A later save — including
  the status write when the invoice is paid — does not send again.
* ``payment_confirmed`` runs only when status becomes ``success``.
  That covers a Paystack verify/webhook apply and a bursar manual
  receipt, because both write the row through the model. A pending
  checkout, a failed attempt, and a notes edit of an already-successful
  payment do not send again.

Work is registered with ``transaction.on_commit(..., robust=True)``.
The log row and the Celery publish happen after the invoice or payment
transaction commits, so a worker cannot start before the row exists and
a broker error cannot roll back the fee write.

Result publication is not wired here. The assessment publish action
owns ``result_published``.
"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from finance.models import Invoice, Payment
from finance.notifications import queue_invoice_generated, queue_payment_confirmed

# pre_save did not run, so post_save must not guess that this is a new success.
_STATUS_UNSET = object()


@receiver(
    post_save,
    sender=Invoice,
    dispatch_uid='finance.invoice_generated_notification',
)
def invoice_generated_notification(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    invoice_id = instance.pk
    transaction.on_commit(
        lambda invoice_id=invoice_id: queue_invoice_generated(invoice_id),
        robust=True,
    )


@receiver(
    pre_save,
    sender=Payment,
    dispatch_uid='finance.payment_cache_status_for_notification',
)
def payment_cache_status_for_notification(sender, instance, raw=False, **kwargs):
    """Remember the stored status. UUID primary keys exist before insert."""
    if raw:
        instance._notification_previous_status = _STATUS_UNSET
        return
    previous = (
        Payment.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )
    instance._notification_previous_status = previous


@receiver(
    post_save,
    sender=Payment,
    dispatch_uid='finance.payment_confirmed_notification',
)
def payment_confirmed_notification(sender, instance, created, raw=False, **kwargs):
    if raw or instance.status != Payment.Status.SUCCESS:
        return
    previous = getattr(instance, '_notification_previous_status', _STATUS_UNSET)
    if previous is _STATUS_UNSET or previous == Payment.Status.SUCCESS:
        return
    # previous is None on insert (manual receipt). An update whose row
    # was missing in pre_save is not a transition we can prove.
    if previous is None and not created:
        return
    payment_id = instance.pk
    transaction.on_commit(
        lambda payment_id=payment_id: queue_payment_confirmed(payment_id),
        robust=True,
    )
