"""
WhatsApp channel for tenant NotificationLog rows.

``WhatsAppNotificationService.send_*`` inserts a queued log and calls
``enqueue_notification``. It does not call the Graph API. The Celery
task from Prompt 1 calls the registered sender, which resolves
``Guardian.phone_number``, normalises it to E.164, and either prints the
template (local console backend) or posts it to Cloud API.

Sends are not idempotent: two calls insert two logs. Dedup for
invoice and payment lives in the finance signal receivers, which call
these methods only when an invoice is created or a payment becomes
success. The assessment publish action calls ``send_result_published``
once per summary that moves from unpublished to published. This
module does not listen for signals.

A missing or malformed guardian number is a permanent failure on that
log. It is not raised to the caller, so one bad number in a bulk loop
does not stop the others.

Callers that invoke ``send_*`` inside ``transaction.atomic()`` must
queue on commit (same rule as email). This module does not open a
transaction of its own.
"""

from django.conf import settings
from django.db import connection

from communications.email_service import (
    PARENT_FEES_PATH,
    PARENT_RESULTS_PATH,
    format_naira,
    greeting_name,
    school_link_context,
    student_display_name,
)
from communications.exceptions import (
    PermanentNotificationError,
    TransientNotificationError,
)
from communications.models import NotificationLog
from communications.tasks import enqueue_notification, register_channel_sender
from communications.whatsapp_client import WhatsAppCloudClient
from communications.whatsapp_schedule import reserve_pair_countdown
from communications.whatsapp_templates import (
    INVOICE_TEMPLATE,
    PAYMENT_TEMPLATE,
    RESULT_TEMPLATE,
)

_INVOICE = NotificationLog.TriggerType.INVOICE_GENERATED
_PAYMENT = NotificationLog.TriggerType.PAYMENT_CONFIRMED
_RESULT = NotificationLog.TriggerType.RESULT_PUBLISHED

_TEMPLATES = {
    _INVOICE: INVOICE_TEMPLATE,
    _PAYMENT: PAYMENT_TEMPLATE,
    _RESULT: RESULT_TEMPLATE,
}

CONSOLE_BACKEND = 'console'
CLOUD_BACKEND = 'cloud'


class WhatsAppNotificationService:
    """Queue parent WhatsApp messages. Delivery happens in the Celery task."""

    def send_invoice_generated(self, invoice, recipient):
        """Queue an invoice WhatsApp. Does not send during the request."""
        _require_saved(invoice, 'invoice')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_INVOICE,
            related_object_id=invoice.pk,
        )

    def send_payment_confirmed(self, payment, recipient):
        """Queue a payment-receipt WhatsApp. Does not send during the request."""
        _require_saved(payment, 'payment')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_PAYMENT,
            related_object_id=payment.pk,
        )

    def send_result_published(self, summary, recipient):
        """Queue a results-ready WhatsApp. Does not send during the request."""
        _require_saved(summary, 'term result summary')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_RESULT,
            related_object_id=summary.pk,
        )

    def deliver(self, log):
        """
        Send one WhatsApp log.

        Called only by the registered channel sender. Raises
        ``PermanentNotificationError`` or ``TransientNotificationError``
        so the Celery task can fail or retry.
        """
        if log.channel != NotificationLog.Channel.WHATSAPP:
            raise PermanentNotificationError(
                'WhatsApp sender received a %s notification.' % log.channel
            )
        try:
            phone = guardian_phone_e164(log.recipient)
            template, parameters = self._parameters_for_log(log)
            _deliver(phone, template, parameters)
        except (PermanentNotificationError, TransientNotificationError):
            raise
        except Exception as exc:
            raise PermanentNotificationError(
                'WhatsApp message could not be built (%s): %s' % (
                    type(exc).__name__, exc,
                )
            ) from exc

    def _queue(self, *, recipient, trigger_type, related_object_id):
        log = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.WHATSAPP,
            trigger_type=trigger_type,
            related_object_id=related_object_id,
            status=NotificationLog.Status.QUEUED,
        )
        # A bad number still gets a queued row. The task marks it failed.
        # Do not take a lane slot for it, and do not raise into the caller.
        try:
            phone = guardian_phone_e164(recipient)
        except PermanentNotificationError:
            phone = ''
        countdown = reserve_pair_countdown(phone)
        enqueue_notification(log, countdown=countdown)
        return log

    def _parameters_for_log(self, log):
        template = _TEMPLATES.get(log.trigger_type)
        if template is None:
            raise PermanentNotificationError(
                'No WhatsApp template for trigger %r.' % log.trigger_type
            )
        obj = _load_related(log)
        if log.trigger_type == _INVOICE:
            parameters = _invoice_parameters(obj, log.recipient)
        elif log.trigger_type == _PAYMENT:
            parameters = _payment_parameters(obj, log.recipient)
        elif log.trigger_type == _RESULT:
            parameters = _result_parameters(obj, log.recipient)
        else:
            raise PermanentNotificationError(
                'No WhatsApp template for trigger %r.' % log.trigger_type
            )
        if len(parameters) != len(template.parameter_names):
            raise PermanentNotificationError(
                'WhatsApp template %s expected %s parameters, got %s.' % (
                    template.name, len(template.parameter_names), len(parameters),
                )
            )
        return template, parameters


def deliver_whatsapp_notification(log):
    """Channel sender registered for ``whatsapp``. Signature: sender(log)."""
    WhatsAppNotificationService().deliver(log)


def register_whatsapp_sender():
    """Register the WhatsApp sender. Safe to call more than once."""
    register_channel_sender(
        NotificationLog.Channel.WHATSAPP,
        deliver_whatsapp_notification,
    )


def guardian_phone_e164(recipient):
    """
    E.164 number from the recipient's tenant Guardian row.

    Raises ``PermanentNotificationError`` when the profile is missing,
    the number is blank, or it cannot be normalised. Never returns ''.
    """
    from academics.models import Guardian

    user_id = getattr(recipient, 'pk', None)
    guardian = (
        Guardian.objects.filter(user_id=user_id).order_by('id').first()
        if user_id
        else None
    )
    if guardian is None:
        raise PermanentNotificationError(
            'Recipient has no guardian profile, so there is no WhatsApp number.'
        )
    return normalize_phone_e164(guardian.phone_number)


def normalize_phone_e164(raw):
    """
    Return ``+<country><number>``.

    Accepts an already-international number, a leading 00, Nigerian
    national format (``080…`` / 11 digits), a 10-digit Nigerian mobile
    with the trunk 0 dropped, or ``234…`` without a plus. Anything else
    is a permanent failure — the caller logs it and moves on.
    """
    import re

    if raw is None or not str(raw).strip():
        raise PermanentNotificationError('Guardian phone number is missing.')
    cleaned = re.sub(r'[\s\-\.\(\)]', '', str(raw).strip())
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    if cleaned.startswith('+'):
        digits = cleaned[1:]
        if not digits.isdigit():
            raise PermanentNotificationError(
                'Guardian phone number is not a valid E.164 number.'
            )
        return _as_e164('+' + digits)
    if not cleaned.isdigit():
        raise PermanentNotificationError(
            'Guardian phone number is not a valid E.164 number.'
        )
    if cleaned.startswith('0'):
        # Nigerian national: trunk 0 plus a 10-digit subscriber number.
        if len(cleaned) == 11:
            return _as_e164('+234' + cleaned[1:])
        raise PermanentNotificationError(
            'Guardian phone number is not a valid E.164 number.'
        )
    if len(cleaned) == 10 and cleaned[0] in '789':
        return _as_e164('+234' + cleaned)
    if cleaned.startswith('234') and len(cleaned) == 13:
        return _as_e164('+' + cleaned)
    if 8 <= len(cleaned) <= 15:
        return _as_e164('+' + cleaned)
    raise PermanentNotificationError(
        'Guardian phone number is not a valid E.164 number.'
    )


def _as_e164(value):
    import re

    if not re.fullmatch(r'\+[1-9]\d{7,14}', value):
        raise PermanentNotificationError(
            'Guardian phone number is not a valid E.164 number.'
        )
    return value


def _invoice_parameters(invoice, recipient):
    context = _base_context(recipient, invoice.student, invoice.term, PARENT_FEES_PATH)
    context['amount_due'] = format_naira(invoice.total_amount)
    return _pack(
        context['parent_name'],
        context['student_name'],
        context['term_label'],
        context['school_name'],
        context['amount_due'],
        context['portal_url'],
    )


def _payment_parameters(payment, recipient):
    invoice = payment.invoice
    context = _base_context(
        recipient, invoice.student, invoice.term, PARENT_FEES_PATH,
    )
    return _pack(
        context['parent_name'],
        context['student_name'],
        context['term_label'],
        context['school_name'],
        format_naira(payment.amount),
        format_naira(invoice.total_amount),
        context['portal_url'],
    )


def _result_parameters(summary, recipient):
    # Scores, position, and remarks stay in the portal.
    context = _base_context(
        recipient, summary.student, summary.term, PARENT_RESULTS_PATH,
    )
    return _pack(
        context['parent_name'],
        context['student_name'],
        context['term_label'],
        context['school_name'],
        context['portal_url'],
    )


def _base_context(recipient, student, term, portal_path):
    school_name, origin = school_link_context()
    return {
        'parent_name': greeting_name(recipient) or 'there',
        'student_name': student_display_name(student),
        'term_label': str(term) if term is not None else 'this term',
        'school_name': school_name,
        'portal_url': '%s%s' % (origin.rstrip('/'), portal_path),
    }


def _pack(*values):
    packed = []
    for value in values:
        text = ' '.join(str(value or '').split())
        if not text:
            raise PermanentNotificationError(
                'WhatsApp template parameter was empty.'
            )
        if len(text) > 1024:
            text = text[:1021] + '...'
        packed.append(text)
    return packed


def _deliver(phone, template, parameters):
    backend = getattr(settings, 'WHATSAPP_BACKEND', CLOUD_BACKEND)
    if backend == CONSOLE_BACKEND:
        _print_console(phone, template, parameters)
        return
    if backend != CLOUD_BACKEND:
        raise PermanentNotificationError(
            'Unknown WhatsApp backend %r.' % backend
        )
    WhatsAppCloudClient().send_template(
        to_e164=phone,
        template_name=template.name,
        language=template.language,
        body_parameters=parameters,
    )


def _print_console(phone, template, parameters):
    # Local stand-in for the Cloud API, same idea as the console email
    # backend: the worker stdout shows the message, nothing is sent.
    preview = template.preview(parameters)
    print(
        '---------- WhatsApp console message ----------\n'
        'To: %s\n'
        'Template: %s (%s, %s)\n'
        'Schema: %s\n'
        '%s\n'
        '----------------------------------------------' % (
            phone,
            template.name,
            template.language,
            template.category,
            getattr(connection, 'schema_name', ''),
            preview,
        )
    )


def _require_saved(obj, label):
    if obj is None or not getattr(obj, 'pk', None):
        raise ValueError(
            '%s must be saved before a notification can be queued.' % label
        )


def _require_recipient(recipient):
    if recipient is None or not getattr(recipient, 'pk', None):
        raise ValueError('recipient must be a saved user.')


def _load_related(log):
    related_id = log.related_object_id
    if log.trigger_type == _INVOICE:
        from finance.models import Invoice

        try:
            return Invoice.objects.select_related(
                'student', 'term', 'term__session',
            ).get(pk=related_id)
        except Invoice.DoesNotExist as exc:
            raise PermanentNotificationError(
                'Invoice for this notification no longer exists.'
            ) from exc
    if log.trigger_type == _PAYMENT:
        from finance.models import Payment

        try:
            return Payment.objects.select_related(
                'invoice',
                'invoice__student',
                'invoice__term',
                'invoice__term__session',
            ).get(pk=related_id)
        except Payment.DoesNotExist as exc:
            raise PermanentNotificationError(
                'Payment for this notification no longer exists.'
            ) from exc
    if log.trigger_type == _RESULT:
        from assessment.models import TermResultSummary

        try:
            return TermResultSummary.objects.select_related(
                'student', 'term', 'term__session',
            ).get(pk=related_id)
        except TermResultSummary.DoesNotExist as exc:
            raise PermanentNotificationError(
                'Term result summary for this notification no longer exists.'
            ) from exc
    raise PermanentNotificationError(
        'No WhatsApp template for trigger %r.' % log.trigger_type
    )
