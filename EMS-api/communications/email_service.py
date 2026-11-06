"""
Email channel for tenant NotificationLog rows.

``EmailNotificationService.send_*`` inserts a queued log and calls
``enqueue_notification``. It does not render or send. The Celery task
from Prompt 1 calls the registered sender, which renders the HTML
template and hands it to Django's email backend (console locally,
generic SMTP in production).

Finance signal receivers call ``send_invoice_generated`` and
``send_payment_confirmed`` (Prompt 5). The assessment publish action
calls ``send_result_published``. This module does not listen for
signals and does not send WhatsApp.
"""

import smtplib
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import BadHeaderError
from django.core.validators import validate_email
from django.db import connection
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django_tenants.utils import get_public_schema_name, schema_context

from communications.exceptions import (
    PermanentNotificationError,
    TransientNotificationError,
)
from communications.models import NotificationLog
from communications.tasks import enqueue_notification, register_channel_sender

PARENT_FEES_PATH = '/parent/fees'
PARENT_RESULTS_PATH = '/parent/results'

_INVOICE = NotificationLog.TriggerType.INVOICE_GENERATED
_PAYMENT = NotificationLog.TriggerType.PAYMENT_CONFIRMED
_RESULT = NotificationLog.TriggerType.RESULT_PUBLISHED


class RenderedEmail:
    """Subject, plain text, and HTML for one message."""

    def __init__(self, subject, text_body, html_body):
        self.subject = subject
        self.text_body = text_body
        self.html_body = html_body


class EmailNotificationService:
    """Queue parent emails. Delivery happens inside the Celery task."""

    def send_invoice_generated(self, invoice, recipient):
        """Queue an invoice email. Does not send during the request."""
        _require_saved(invoice, 'invoice')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_INVOICE,
            related_object_id=invoice.pk,
        )

    def send_payment_confirmed(self, payment, recipient):
        """Queue a payment-receipt email. Does not send during the request."""
        _require_saved(payment, 'payment')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_PAYMENT,
            related_object_id=payment.pk,
        )

    def send_result_published(self, summary, recipient):
        """Queue a results-ready email. Does not send during the request."""
        _require_saved(summary, 'term result summary')
        _require_recipient(recipient)
        return self._queue(
            recipient=recipient,
            trigger_type=_RESULT,
            related_object_id=summary.pk,
        )

    def render_invoice_generated(self, invoice, recipient, *, school_name=None, portal_url=None):
        context = self._base_context(
            recipient=recipient,
            student=invoice.student,
            term=invoice.term,
            portal_path=PARENT_FEES_PATH,
            school_name=school_name,
            portal_url=portal_url,
        )
        context['amount_due'] = format_naira(invoice.total_amount)
        context['line_items'] = [
            {
                'name': line.fee_structure.name,
                'amount': format_naira(line.amount),
            }
            for line in invoice.line_items.all()
        ]
        subject = (
            f'Invoice for {context["student_name"]} ({context["term_label"]})'
        )
        return self._render(
            subject,
            'communications/email/invoice_generated.txt',
            'communications/email/invoice_generated.html',
            context,
        )

    def render_payment_confirmed(self, payment, recipient, *, school_name=None, portal_url=None):
        invoice = payment.invoice
        context = self._base_context(
            recipient=recipient,
            student=invoice.student,
            term=invoice.term,
            portal_path=PARENT_FEES_PATH,
            school_name=school_name,
            portal_url=portal_url,
        )
        context['amount_paid'] = format_naira(payment.amount)
        context['invoice_total'] = format_naira(invoice.total_amount)
        subject = (
            f'Payment received for {context["student_name"]} '
            f'({context["term_label"]})'
        )
        return self._render(
            subject,
            'communications/email/payment_confirmed.txt',
            'communications/email/payment_confirmed.html',
            context,
        )

    def render_result_published(self, summary, recipient, *, school_name=None, portal_url=None):
        # Scores, position, and remarks stay in the portal. Email is not
        # a secure channel — the template context has no result numbers.
        context = self._base_context(
            recipient=recipient,
            student=summary.student,
            term=summary.term,
            portal_path=PARENT_RESULTS_PATH,
            school_name=school_name,
            portal_url=portal_url,
        )
        subject = (
            f'Results ready for {context["student_name"]} ({context["term_label"]})'
        )
        return self._render(
            subject,
            'communications/email/result_published.txt',
            'communications/email/result_published.html',
            context,
        )

    def deliver(self, log):
        """
        Render and send one email log.

        Called only by the registered channel sender. Raises
        ``PermanentNotificationError`` or ``TransientNotificationError``
        so the Celery task can fail or retry.
        """
        if log.channel != NotificationLog.Channel.EMAIL:
            raise PermanentNotificationError(
                f'Email sender received a {log.channel} notification.'
            )
        try:
            recipient_email = _validated_recipient_email(log.recipient)
            rendered = self._render_for_log(log)
            _send_rendered(rendered, recipient_email)
        except (PermanentNotificationError, TransientNotificationError):
            raise
        except Exception as exc:
            # A bug in rendering will not succeed on retry. Record it on
            # the log instead of leaving the row queued forever.
            raise PermanentNotificationError(
                f'Email could not be built ({type(exc).__name__}): {exc}'
            ) from exc

    def _queue(self, *, recipient, trigger_type, related_object_id):
        log = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.EMAIL,
            trigger_type=trigger_type,
            related_object_id=related_object_id,
            status=NotificationLog.Status.QUEUED,
        )
        enqueue_notification(log)
        return log

    def _render_for_log(self, log):
        obj = _load_related(log)
        if log.trigger_type == _INVOICE:
            return self.render_invoice_generated(obj, log.recipient)
        if log.trigger_type == _PAYMENT:
            return self.render_payment_confirmed(obj, log.recipient)
        if log.trigger_type == _RESULT:
            return self.render_result_published(obj, log.recipient)
        raise PermanentNotificationError(
            f'No email template for trigger {log.trigger_type!r}.'
        )

    def _base_context(
        self, *, recipient, student, term, portal_path, school_name, portal_url,
    ):
        if school_name is None or portal_url is None:
            resolved_name, origin = school_link_context()
            if school_name is None:
                school_name = resolved_name
            if portal_url is None:
                portal_url = f'{origin.rstrip("/")}{portal_path}'
        return {
            'school_name': school_name,
            'greeting_name': greeting_name(recipient),
            'student_name': student_display_name(student),
            'term_label': str(term),
            'portal_url': portal_url,
        }

    def _render(self, subject, text_template, html_template, context):
        subject = ' '.join(str(subject).split())
        context = {**context, 'subject': subject}
        try:
            text_body = render_to_string(text_template, context).strip() + '\n'
            html_body = render_to_string(html_template, context)
        except TemplateDoesNotExist as exc:
            raise PermanentNotificationError(
                f'Email template is missing: {exc}'
            ) from exc
        return RenderedEmail(subject, text_body, html_body)


def deliver_email_notification(log):
    """Channel sender registered for ``email``. Signature: sender(log)."""
    EmailNotificationService().deliver(log)


def register_email_sender():
    """Register the email sender. Safe to call more than once."""
    register_channel_sender(NotificationLog.Channel.EMAIL, deliver_email_notification)


def format_naira(amount):
    value = Decimal(amount).quantize(Decimal('0.01'))
    return f'₦{value:,.2f}'


def school_link_context():
    """
    School name and frontend origin for the connection's schema.

    The Celery task enters through ``schema_context(schema_name)``, which
    sets a FakeTenant. That object has no ``school_name`` and no
    ``domains``, so the real Tenant row is loaded from the public schema.
    """
    schema_name = getattr(connection, 'schema_name', '') or ''
    if not schema_name or schema_name == get_public_schema_name():
        raise PermanentNotificationError(
            'Cannot build a parent portal link outside a school schema.'
        )
    from platform_admin.models import Tenant
    from platform_admin.tenancy import frontend_origin_for_tenant

    with schema_context(get_public_schema_name()):
        tenant = Tenant.objects.filter(schema_name=schema_name).first()
        if tenant is None:
            raise PermanentNotificationError(
                f'No school found for schema {schema_name!r}.'
            )
        name = (tenant.school_name or '').strip() or 'your school'
        origin = frontend_origin_for_tenant(tenant).rstrip('/')
    return name, origin


def greeting_name(user):
    first = (getattr(user, 'first_name', '') or '').strip()
    if first:
        return first
    return (getattr(user, 'last_name', '') or '').strip()


def student_display_name(student):
    first = (getattr(student, 'first_name', '') or '').strip()
    last = (getattr(student, 'last_name', '') or '').strip()
    return f'{first} {last}'.strip() or 'your child'


def _require_saved(obj, label):
    if obj is None or not getattr(obj, 'pk', None):
        raise ValueError(
            f'{label} must be saved before a notification can be queued.'
        )


def _require_recipient(recipient):
    if recipient is None or not getattr(recipient, 'pk', None):
        raise ValueError('recipient must be a saved user.')


def _validated_recipient_email(recipient):
    email = (getattr(recipient, 'email', '') or '').strip()
    if not email:
        raise PermanentNotificationError('Recipient has no email address.')
    try:
        validate_email(email)
    except ValidationError as exc:
        raise PermanentNotificationError(
            'Recipient email address is invalid.'
        ) from exc
    return email


def _load_related(log):
    related_id = log.related_object_id
    if log.trigger_type == _INVOICE:
        from finance.models import Invoice

        try:
            return (
                Invoice.objects.select_related('student', 'term', 'term__session')
                .prefetch_related('line_items__fee_structure')
                .get(pk=related_id)
            )
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
        f'No email template for trigger {log.trigger_type!r}.'
    )


def _send_rendered(rendered, recipient_email):
    message = EmailMultiAlternatives(
        subject=rendered.subject,
        body=rendered.text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ems.local'),
        to=[recipient_email],
    )
    message.attach_alternative(rendered.html_body, 'text/html')
    try:
        accepted = message.send(fail_silently=False)
    except BadHeaderError as exc:
        raise PermanentNotificationError(
            'Email subject or headers were rejected.'
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise PermanentNotificationError(
            f'Recipient address was refused: {exc}'
        ) from exc
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError) as exc:
        raise PermanentNotificationError(
            f'Mail server rejected the message: {exc}'
        ) from exc
    except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
        _raise_for_smtp_code(exc)
    except smtplib.SMTPResponseException as exc:
        _raise_for_smtp_code(exc)
    except (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        smtplib.SMTPHeloError,
        ConnectionError,
        TimeoutError,
        OSError,
    ) as exc:
        raise TransientNotificationError(
            f'Email could not be sent: {exc}'
        ) from exc
    except smtplib.SMTPException as exc:
        raise TransientNotificationError(
            f'Email could not be sent: {exc}'
        ) from exc
    if not accepted:
        raise TransientNotificationError(
            'Email backend did not accept the message.'
        )


def _raise_for_smtp_code(exc):
    code = int(getattr(exc, 'smtp_code', 0) or 0)
    if 400 <= code < 500:
        raise TransientNotificationError(f'Mail server error: {exc}') from exc
    raise PermanentNotificationError(f'Mail server error: {exc}') from exc
