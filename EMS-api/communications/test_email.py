"""
Email notification service (Phase 5, Prompt 2).

Proves send_* only queues, the Celery task renders and sends, the local
backend is console, and result emails do not include scores.
"""

import io
import smtplib
import uuid
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from academics.models import ClassLevel, Session, Student, Term
from assessment.models import TermResultSummary
from communications.email_service import (
    EmailNotificationService,
    deliver_email_notification,
    register_email_sender,
)
from communications.models import NotificationLog
from communications.tasks import (
    clear_channel_senders,
    get_channel_sender,
    send_notification,
)
from finance.models import FeeStructure, Invoice, InvoiceLineItem, Payment

User = get_user_model()

LOCMAIL = 'django.core.mail.backends.locmem.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


class EmailSettingsTests(SimpleTestCase):
    def test_local_settings_use_the_console_backend(self):
        # The test runner forces locmem on django.conf.settings for the
        # whole suite. The local module itself still selects console.
        import config.settings.local as local_settings

        self.assertEqual(local_settings.EMAIL_BACKEND, CONSOLE)
        self.assertTrue(local_settings.DEFAULT_FROM_EMAIL)

    def test_production_settings_are_generic_smtp(self):
        import config.settings.production as production

        self.assertEqual(
            production.EMAIL_BACKEND,
            'django.core.mail.backends.smtp.EmailBackend',
        )
        self.assertEqual(production.EMAIL_HOST, 'localhost')
        self.assertEqual(production.EMAIL_PORT, 25)
        self.assertEqual(production.EMAIL_HOST_USER, '')
        self.assertEqual(production.EMAIL_HOST_PASSWORD, '')
        self.assertFalse(production.EMAIL_USE_TLS)
        self.assertFalse(production.EMAIL_USE_SSL)
        self.assertEqual(production.EMAIL_TIMEOUT, 30)
        self.assertNotIn('sendgrid', production.EMAIL_BACKEND.lower())
        self.assertNotIn('mailgun', production.EMAIL_BACKEND.lower())


class EmailNotificationServiceTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Email School'
        return tenant

    def setUp(self):
        super().setUp()
        overrides = override_settings(EMAIL_BACKEND=LOCMAIL)
        overrides.enable()
        self.addCleanup(overrides.disable)
        mail.outbox = []

        clear_channel_senders()
        register_email_sender()
        self.addCleanup(register_email_sender)
        self.addCleanup(clear_channel_senders)

        self.service = EmailNotificationService()
        self.parent = User.objects.create_user(
            email='parent-email-p2@example.com',
            password='pass12345',
            first_name='Chinedu',
            last_name='Okonkwo',
        )
        self.bursar = User.objects.create_user(
            email='bursar-email-p2@example.com',
            password='pass12345',
        )
        session = Session.objects.create(
            name='2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            session=session,
            name=Term.Name.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18),
            is_active=True,
        )
        self.student = Student.objects.create(
            first_name='Adaeze',
            last_name='Okonkwo',
            date_of_birth=date(2015, 4, 12),
            gender=Student.Gender.FEMALE,
            admission_number='TA-1042',
            admission_date=date(2024, 9, 9),
        )
        class_level = ClassLevel.objects.create(name='JSS1')
        tuition = FeeStructure.objects.create(
            class_level=class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('150000.00'),
        )
        levy = FeeStructure.objects.create(
            class_level=class_level,
            term=self.term,
            name='PTA Levy',
            amount=Decimal('7500.50'),
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            term=self.term,
            total_amount=Decimal('157500.50'),
            status=Invoice.Status.UNPAID,
        )
        InvoiceLineItem.objects.create(
            invoice=self.invoice, fee_structure=tuition, amount=Decimal('150000.00'),
        )
        InvoiceLineItem.objects.create(
            invoice=self.invoice, fee_structure=levy, amount=Decimal('7500.50'),
        )

    def test_app_ready_registers_the_email_sender(self):
        clear_channel_senders()
        from django.apps import apps

        from communications.whatsapp_service import deliver_whatsapp_notification

        apps.get_app_config('communications').ready()
        self.assertIs(
            get_channel_sender(NotificationLog.Channel.EMAIL),
            deliver_email_notification,
        )
        # Prompt 3 registers WhatsApp from the same ready() hook.
        self.assertIs(
            get_channel_sender(NotificationLog.Channel.WHATSAPP),
            deliver_whatsapp_notification,
        )

    def test_send_invoice_generated_queues_without_sending(self):
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            with mock.patch(
                'communications.email_service.EmailMultiAlternatives',
            ) as message_cls:
                log = self.service.send_invoice_generated(self.invoice, self.parent)

        message_cls.assert_not_called()
        delay.assert_called_once_with(str(log.pk), self.tenant.schema_name)
        self.assertEqual(mail.outbox, [])
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.QUEUED)
        self.assertEqual(log.channel, NotificationLog.Channel.EMAIL)
        self.assertEqual(log.trigger_type, NotificationLog.TriggerType.INVOICE_GENERATED)
        self.assertEqual(log.related_object_id, self.invoice.pk)
        self.assertEqual(log.recipient_id, self.parent.pk)
        self.assertIsNone(log.sent_at)

    def test_each_call_queues_its_own_log(self):
        with mock.patch('communications.tasks.send_notification.delay'):
            first = self.service.send_invoice_generated(self.invoice, self.parent)
            second = self.service.send_invoice_generated(self.invoice, self.parent)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(NotificationLog.objects.count(), 2)

    def test_task_sends_invoice_email_with_amount_and_portal_link(self):
        log = self._queue_invoice()
        result = send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        if not result.successful():
            self.fail(result.traceback)

        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNone(log.error_message)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.parent.email])
        self.assertEqual(message.from_email, 'noreply@ems.local')
        self.assertEqual(
            message.subject,
            'Invoice for Adaeze Okonkwo (2026/2027 — 1st)',
        )
        self.assertIn('Hello Chinedu,', message.body)
        self.assertIn('Amount due: ₦157,500.50', message.body)
        self.assertIn('Tuition: ₦150,000.00', message.body)
        self.assertIn('PTA Levy: ₦7,500.50', message.body)
        self.assertIn('http://tenant.localhost:3000/parent/fees', message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('Amount due', html)
        self.assertIn('₦157,500.50', html)
        self.assertIn('Tuition', html)
        self.assertIn('href="http://tenant.localhost:3000/parent/fees"', html)
        self.assertIn('Email School', html)
        self.assertNotIn('73.25', html)

    def test_console_backend_prints_the_invoice_email(self):
        log = self._queue_invoice()
        printed = io.StringIO()
        with override_settings(EMAIL_BACKEND=CONSOLE):
            with redirect_stdout(printed):
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        output = printed.getvalue()
        self.assertIn('Invoice for Adaeze Okonkwo', output)
        self.assertIn('₦157,500.50', output)
        self.assertIn('text/html', output)
        self.assertIn('http://tenant.localhost:3000/parent/fees', output)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_task_sends_payment_email(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            reference=f'manual-{uuid.uuid4().hex[:12]}',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.MANUAL,
            method=Payment.Method.CASH,
            recorded_by=self.bursar,
            paid_at=timezone.now(),
        )
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            log = self.service.send_payment_confirmed(payment, self.parent)
        delay.assert_called_once()
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))

        message = mail.outbox[0]
        self.assertIn('Amount paid: ₦50,000.00', message.body)
        self.assertIn('Invoice total: ₦157,500.50', message.body)
        self.assertIn('http://tenant.localhost:3000/parent/fees', message.body)
        html, _mimetype = message.alternatives[0]
        self.assertIn('₦50,000.00', html)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_result_email_links_to_the_portal_and_omits_scores(self):
        summary = TermResultSummary.objects.create(
            student=self.student,
            term=self.term,
            overall_average=Decimal('73.25'),
            class_position=917,
            teacher_remark='SECRET-REMARK-9f3a',
            admin_remark='SECRET-ADMIN-REMARK',
        )
        with mock.patch('communications.tasks.send_notification.delay'):
            log = self.service.send_result_published(summary, self.parent)
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))

        message = mail.outbox[0]
        self.assertEqual(
            message.subject,
            'Results ready for Adaeze Okonkwo (2026/2027 — 1st)',
        )
        html, _mimetype = message.alternatives[0]
        combined = f'{message.body}\n{html}'
        self.assertIn('are now available', combined)
        self.assertIn('http://tenant.localhost:3000/parent/results', combined)
        self.assertNotIn('73.25', combined)
        self.assertNotIn('917', combined)
        self.assertNotIn('SECRET-REMARK-9f3a', combined)
        self.assertNotIn('SECRET-ADMIN-REMARK', combined)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_missing_invoice_fails_immediately(self):
        log = self._queue_invoice()
        self.invoice.delete()
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('no longer exists', log.error_message)
        self.assertEqual(mail.outbox, [])

    def test_blank_recipient_email_is_permanent(self):
        User.objects.filter(pk=self.parent.pk).update(email='')
        self.parent.refresh_from_db()
        log = self._queue_invoice()
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('no email address', log.error_message)
        self.assertEqual(mail.outbox, [])

    def test_smtp_disconnect_retries_then_fails(self):
        log = self._queue_invoice()
        with mock.patch(
            'communications.email_service.EmailMultiAlternatives',
        ) as message_cls:
            message_cls.return_value.send.side_effect = (
                smtplib.SMTPServerDisconnected('connection lost')
            )
            send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        self.assertEqual(message_cls.return_value.send.call_count, 3)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('connection lost', log.error_message)

    def test_refused_recipient_does_not_retry(self):
        log = self._queue_invoice()
        with mock.patch(
            'communications.email_service.EmailMultiAlternatives',
        ) as message_cls:
            message_cls.return_value.send.side_effect = smtplib.SMTPRecipientsRefused(
                {self.parent.email: (550, b'User unknown')},
            )
            send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        self.assertEqual(message_cls.return_value.send.call_count, 1)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('refused', log.error_message.lower())

    def _queue_invoice(self):
        with mock.patch('communications.tasks.send_notification.delay'):
            return self.service.send_invoice_generated(self.invoice, self.parent)
