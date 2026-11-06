"""
Queue invoice and payment notifications for linked parents.

Called from ``transaction.on_commit`` hooks in ``finance.signals``.
``send_*`` inserts the NotificationLog and publishes the Celery task;
it is not idempotent, so the signal receivers decide whether a save is
a real trigger. This module does not send result-published messages.
"""

import logging

logger = logging.getLogger(__name__)


def queue_invoice_generated(invoice_id):
    """Email every linked parent. WhatsApp only when that parent has a phone."""
    from finance.models import Invoice

    try:
        invoice = Invoice.objects.select_related('student', 'term').get(pk=invoice_id)
    except Invoice.DoesNotExist:
        logger.warning(
            'Invoice %s was gone before invoice_generated could be queued.',
            invoice_id,
        )
        return
    _notify_linked_parents(
        invoice.student_id,
        label='invoice_generated',
        object_id=invoice_id,
        email_send=lambda service, parent: service.send_invoice_generated(
            invoice, parent,
        ),
        whatsapp_send=lambda service, parent: service.send_invoice_generated(
            invoice, parent,
        ),
    )


def queue_payment_confirmed(payment_id):
    """Email every linked parent. WhatsApp only when that parent has a phone."""
    from finance.models import Payment

    try:
        payment = Payment.objects.select_related(
            'invoice__student', 'invoice__term',
        ).get(pk=payment_id)
    except Payment.DoesNotExist:
        logger.warning(
            'Payment %s was gone before payment_confirmed could be queued.',
            payment_id,
        )
        return
    if payment.status != Payment.Status.SUCCESS:
        return
    _notify_linked_parents(
        payment.invoice.student_id,
        label='payment_confirmed',
        object_id=payment_id,
        email_send=lambda service, parent: service.send_payment_confirmed(
            payment, parent,
        ),
        whatsapp_send=lambda service, parent: service.send_payment_confirmed(
            payment, parent,
        ),
    )


def _notify_linked_parents(
    student_id, *, label, object_id, email_send, whatsapp_send,
):
    from communications.email_service import EmailNotificationService
    from communications.whatsapp_service import WhatsAppNotificationService

    email = EmailNotificationService()
    whatsapp = WhatsAppNotificationService()
    for parent in _linked_parent_users(student_id):
        try:
            email_send(email, parent)
        except Exception:
            logger.exception(
                'Could not queue %s email for %s recipient %s',
                label,
                object_id,
                parent.pk,
            )
        if not _guardian_has_phone(parent):
            continue
        try:
            whatsapp_send(whatsapp, parent)
        except Exception:
            logger.exception(
                'Could not queue %s WhatsApp for %s recipient %s',
                label,
                object_id,
                parent.pk,
            )


def _linked_parent_users(student_id):
    """Parent users linked to this student. Unclaimed guardians are skipped."""
    from academics.models import StudentGuardianLink

    links = (
        StudentGuardianLink.objects.filter(
            student_id=student_id,
            guardian__user__isnull=False,
        )
        .select_related('guardian__user')
        .order_by('guardian_id')
    )
    users = []
    seen = set()
    for link in links:
        user = link.guardian.user
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        users.append(user)
    return users


def _guardian_has_phone(user):
    """True when the parent's guardian row has a non-blank phone number."""
    from academics.models import Guardian

    phone = (
        Guardian.objects.filter(user_id=user.pk)
        .values_list('phone_number', flat=True)
        .first()
    )
    return bool(phone and str(phone).strip())
