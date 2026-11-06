"""
Invoice and payment notification triggers (Phase 5, Prompt 5).

Proves one queued message per invoice or successful payment, both
channels when the guardian has a phone and email only when they do
not, and no second send when the same row is saved again. Result
publication is not triggered from these signals.
"""

import inspect
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from rest_framework import status

from academics.models import Guardian, StudentGuardianLink
from communications.email_service import EmailNotificationService
from communications.models import NotificationLog
from communications.whatsapp_schedule import use_memory_schedule
from finance.models import Invoice, Payment
from finance.services import (
    PaymentAmountMismatch,
    record_manual_payment,
    verify_and_apply_payment,
)
from finance.tests import FinanceInvoicingTestCase, _response, _verify_payload

_EMAIL = NotificationLog.Channel.EMAIL
_WHATSAPP = NotificationLog.Channel.WHATSAPP
_INVOICE = NotificationLog.TriggerType.INVOICE_GENERATED
_PAYMENT = NotificationLog.TriggerType.PAYMENT_CONFIRMED
_RESULT = NotificationLog.TriggerType.RESULT_PUBLISHED


class FinanceNotificationSignalTests(FinanceInvoicingTestCase):
    def setUp(self):
        super().setUp()
        use_memory_schedule()
        self._make_fees()

    def _logs(self, trigger):
        return NotificationLog.objects.filter(trigger_type=trigger)

    def _set_phone(self, user, phone):
        Guardian.objects.filter(user=user).update(phone_number=phone)

    def _link_parent(self, user, student, phone=''):
        guardian = Guardian.objects.create(user=user, phone_number=phone)
        return StudentGuardianLink.objects.create(
            student=student,
            guardian=guardian,
            is_primary_contact=True,
        )

    def _run(self, fn, *, execute=True):
        delay = mock.patch('communications.tasks.send_notification.delay')
        later = mock.patch('communications.tasks.send_notification.apply_async')
        with delay as delay_mock, later as later_mock:
            with self.captureOnCommitCallbacks(execute=execute) as callbacks:
                result = fn()
        return result, callbacks, delay_mock, later_mock

    def test_bulk_generate_notifies_each_linked_parent_after_line_items_exist(self):
        self._link_parent(self.other_parent, self.students[1], phone='08039876543')
        # students[2] has no guardian. students[0]'s parent has no phone.
        line_counts = []
        original = EmailNotificationService.send_invoice_generated

        def wrapped(service, invoice, recipient):
            line_counts.append(invoice.line_items.count())
            return original(service, invoice, recipient)

        with mock.patch(
            'communications.tasks.send_notification.delay',
        ) as delay, mock.patch(
            'communications.tasks.send_notification.apply_async',
        ) as later, mock.patch.object(
            EmailNotificationService,
            'send_invoice_generated',
            wrapped,
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                held = self._generate(self.admin)
                self.assertEqual(held.status_code, status.HTTP_201_CREATED, held.data)
                self.assertEqual(held.data['created_count'], 3)
                self.assertEqual(line_counts, [])
                self.assertEqual(self._logs(_INVOICE).count(), 0)
                delay.assert_not_called()
                later.assert_not_called()
            self.assertEqual(len(callbacks), 3)
            for callback in callbacks:
                callback()

        self.assertEqual(line_counts, [3, 3])
        invoices = {
            invoice.student_id: invoice
            for invoice in Invoice.objects.all()
        }
        logs = list(self._logs(_INVOICE))
        self.assertEqual(len(logs), 3)
        self.assertEqual(
            {(log.recipient_id, log.channel, log.related_object_id) for log in logs},
            {
                (self.parent.pk, _EMAIL, invoices[self.students[0].pk].pk),
                (self.other_parent.pk, _EMAIL, invoices[self.students[1].pk].pk),
                (self.other_parent.pk, _WHATSAPP, invoices[self.students[1].pk].pk),
            },
        )
        self.assertTrue(all(log.status == NotificationLog.Status.QUEUED for log in logs))
        self.assertFalse(
            any(log.related_object_id == invoices[self.students[2].pk].pk for log in logs)
        )
        self.assertFalse(self._logs(_RESULT).exists())

    def test_phone_adds_whatsapp_and_a_blank_number_stays_email_only(self):
        self._set_phone(self.parent, '08031234567')
        self._link_parent(self.other_parent, self.students[0], phone='   ')
        response, callbacks, delay, _later = self._run(
            lambda: self._generate(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(callbacks), 3)

        invoice = Invoice.objects.get(student=self.students[0])
        logs = list(self._logs(_INVOICE).order_by('channel', 'recipient_id'))
        self.assertEqual(
            {(log.recipient_id, log.channel) for log in logs},
            {
                (self.parent.pk, _EMAIL),
                (self.parent.pk, _WHATSAPP),
                (self.other_parent.pk, _EMAIL),
            },
        )
        self.assertTrue(all(log.related_object_id == invoice.pk for log in logs))
        delay.assert_called()
        self.assertFalse(self._logs(_RESULT).exists())

    def test_unclaimed_guardian_is_skipped_and_regenerate_does_not_resend(self):
        Guardian.objects.create(
            user=None,
            full_name='No account yet',
            phone_number='08030000000',
        )
        # The unclaimed row is not linked; linking it still must not notify.
        unclaimed = Guardian.objects.create(
            user=None,
            full_name='Linked but no login',
            phone_number='08031110000',
        )
        StudentGuardianLink.objects.create(
            student=self.students[2],
            guardian=unclaimed,
            is_primary_contact=True,
        )
        first, _, _, _ = self._run(lambda: self._generate(self.admin))
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._logs(_INVOICE).count(), 1)

        second, callbacks, delay, later = self._run(
            lambda: self._generate(self.admin),
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data['created_count'], 0)
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        later.assert_not_called()
        self.assertEqual(self._logs(_INVOICE).count(), 1)

    def test_invoice_status_save_does_not_resend(self):
        self._run(lambda: self._generate(self.admin))
        self.assertEqual(self._logs(_INVOICE).count(), 1)
        invoice = Invoice.objects.get(student=self.students[0])

        def edit():
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=['status'])
            invoice.save()

        _, callbacks, delay, _later = self._run(edit)
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        self.assertEqual(self._logs(_INVOICE).count(), 1)
        self.assertFalse(self._logs(_PAYMENT).exists())

    def test_paystack_success_notifies_once_across_verify_and_webhook_path(self):
        self._set_phone(self.parent, '08031234567')
        self._run(lambda: self._generate(self.admin))
        invoice = Invoice.objects.get(student=self.students[0])

        def create_pending():
            return Payment.objects.create(
                invoice=invoice,
                amount=Decimal('157500.50'),
                reference='pay_notify_once',
                status=Payment.Status.PENDING,
                gateway=Payment.Gateway.PAYSTACK,
                initiated_by=self.parent,
            )

        payment, pending_callbacks, pending_delay, pending_later = self._run(
            create_pending,
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(pending_callbacks, [])
        pending_delay.assert_not_called()
        pending_later.assert_not_called()
        self.assertFalse(self._logs(_PAYMENT).exists())

        def verify():
            with mock.patch(
                'finance.paystack.requests.request',
                return_value=_response(
                    _verify_payload(payment.reference, payment.amount),
                ),
            ):
                with override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy'):
                    return verify_and_apply_payment(payment.reference)

        invoice_notifications = self._logs(_INVOICE).count()
        first, _, delay, _later = self._run(verify)
        self.assertEqual(first.status, Payment.Status.SUCCESS)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(self._logs(_INVOICE).count(), invoice_notifications)
        self.assertEqual(invoice_notifications, 2)
        payment_logs = list(self._logs(_PAYMENT))
        self.assertEqual(len(payment_logs), 2)
        self.assertEqual(
            {(log.channel, log.recipient_id, log.related_object_id) for log in payment_logs},
            {
                (_EMAIL, self.parent.pk, payment.pk),
                (_WHATSAPP, self.parent.pk, payment.pk),
            },
        )
        delay.assert_called()

        def verify_again():
            with mock.patch(
                'finance.paystack.requests.request',
                return_value=_response(
                    _verify_payload(payment.reference, payment.amount),
                ),
            ) as http:
                with override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy'):
                    again = verify_and_apply_payment(payment.reference)
            return again, http

        (again, http), callbacks, delay, later = self._run(verify_again)
        self.assertEqual(again.pk, payment.pk)
        http.assert_not_called()
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        later.assert_not_called()
        self.assertEqual(self._logs(_PAYMENT).count(), 2)

        def edit_notes():
            payment.notes = 'Parent asked for a duplicate receipt.'
            payment.save(update_fields=['notes'])

        _, callbacks, delay, _later = self._run(edit_notes)
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        self.assertEqual(self._logs(_PAYMENT).count(), 2)
        self.assertFalse(self._logs(_RESULT).exists())

    def test_failed_paystack_attempt_does_not_notify(self):
        self._run(lambda: self._generate(self.admin))
        invoice = Invoice.objects.get(student=self.students[0])
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('1000.00'),
            reference='pay_notify_failed',
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )

        def mismatch():
            with mock.patch(
                'finance.paystack.requests.request',
                return_value=_response(
                    _verify_payload(payment.reference, Decimal('50.00')),
                ),
            ):
                with override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy'):
                    with self.assertRaises(PaymentAmountMismatch):
                        verify_and_apply_payment(payment.reference)

        _, callbacks, delay, later = self._run(mismatch)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        later.assert_not_called()
        self.assertFalse(self._logs(_PAYMENT).exists())

    def test_manual_payment_notifies_each_receipt_and_not_a_resave(self):
        self._set_phone(self.parent, 'not-a-number')
        self._run(lambda: self._generate(self.admin))
        invoice = Invoice.objects.get(student=self.students[0])

        def record():
            return record_manual_payment(
                invoice=invoice,
                amount=Decimal('50000.00'),
                method=Payment.Method.CASH,
                recorded_by=self.bursar,
                notes='Cash at the window.',
            )

        first, _, _, _ = self._run(record)
        self.assertEqual(first.status, Payment.Status.SUCCESS)
        logs = list(self._logs(_PAYMENT))
        self.assertEqual(len(logs), 2)
        self.assertEqual(
            {log.channel for log in logs},
            {_EMAIL, _WHATSAPP},
        )
        self.assertTrue(all(log.related_object_id == first.pk for log in logs))
        self.assertEqual(self._logs(_INVOICE).count(), 2)

        def record_rest():
            return record_manual_payment(
                invoice=invoice,
                amount=Decimal('107500.50'),
                method=Payment.Method.BANK_TRANSFER,
                recorded_by=self.bursar,
            )

        second, _, _, _ = self._run(record_rest)
        self.assertEqual(self._logs(_PAYMENT).count(), 4)
        self.assertEqual(
            set(self._logs(_PAYMENT).values_list('related_object_id', flat=True)),
            {first.pk, second.pk},
        )

        def resave():
            first.notes = 'Counted again, same receipt.'
            first.save(update_fields=['notes'])

        _, callbacks, delay, later = self._run(resave)
        self.assertEqual(callbacks, [])
        delay.assert_not_called()
        later.assert_not_called()
        self.assertEqual(self._logs(_PAYMENT).count(), 4)

    def test_manual_endpoint_queues_on_commit(self):
        self._run(lambda: self._generate(self.admin))
        invoice = Invoice.objects.get(student=self.students[0])
        self.api.force_authenticate(user=self.bursar)

        def post():
            return self.api.post(
                '/api/finance/payments/manual/',
                {
                    'invoice': str(invoice.pk),
                    'amount': '157500.50',
                    'method': 'cash',
                },
                format='json',
            )

        with mock.patch(
            'communications.tasks.send_notification.delay',
        ) as delay, mock.patch(
            'communications.tasks.send_notification.apply_async',
        ):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = post()
                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED, response.data,
                )
                self.assertEqual(self._logs(_PAYMENT).count(), 0)
                delay.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
        self.assertEqual(self._logs(_PAYMENT).count(), 1)
        self.assertEqual(self._logs(_PAYMENT).get().channel, _EMAIL)
        self.assertEqual(self._logs(_PAYMENT).get().recipient_id, self.parent.pk)

    def test_email_failure_still_queues_whatsapp_and_keeps_the_invoice(self):
        self._set_phone(self.parent, '08031234567')
        with mock.patch.object(
            EmailNotificationService,
            'send_invoice_generated',
            side_effect=RuntimeError('smtp down'),
        ):
            response, _, _, _ = self._run(lambda: self._generate(self.admin))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Invoice.objects.count(), 3)
        self.assertEqual(self._logs(_INVOICE).filter(channel=_EMAIL).count(), 0)
        whatsapp = self._logs(_INVOICE).get()
        self.assertEqual(whatsapp.channel, _WHATSAPP)
        self.assertEqual(whatsapp.recipient_id, self.parent.pk)

    def test_whatsapp_failure_still_queues_email(self):
        self._set_phone(self.parent, '08031234567')
        from communications.whatsapp_service import WhatsAppNotificationService

        with mock.patch.object(
            WhatsAppNotificationService,
            'send_invoice_generated',
            side_effect=RuntimeError('graph down'),
        ):
            response, _, _, _ = self._run(lambda: self._generate(self.admin))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        log = self._logs(_INVOICE).get()
        self.assertEqual(log.channel, _EMAIL)
        self.assertEqual(log.recipient_id, self.parent.pk)

    def test_signals_do_not_send_result_published(self):
        import finance.notifications as notifications
        import finance.signals as signals

        for fn in (
            signals.invoice_generated_notification,
            signals.payment_cache_status_for_notification,
            signals.payment_confirmed_notification,
            notifications.queue_invoice_generated,
            notifications.queue_payment_confirmed,
            notifications._notify_linked_parents,
        ):
            source = inspect.getsource(fn)
            self.assertNotIn('send_result_published', source)
            self.assertNotIn('TermResultSummary', source)
            self.assertNotIn('result_published', source)

        with mock.patch(
            'communications.email_service.EmailNotificationService.send_result_published',
        ) as email_result, mock.patch(
            'communications.whatsapp_service.WhatsAppNotificationService.send_result_published',
        ) as whatsapp_result:
            self._run(lambda: self._generate(self.admin))
            invoice = Invoice.objects.get(student=self.students[0])
            self._run(lambda: record_manual_payment(
                invoice=invoice,
                amount=Decimal('1000.00'),
                method=Payment.Method.CASH,
                recorded_by=self.bursar,
            ))
        email_result.assert_not_called()
        whatsapp_result.assert_not_called()
        self.assertFalse(self._logs(_RESULT).exists())
        self.assertGreater(self._logs(_INVOICE).count(), 0)
        self.assertGreater(self._logs(_PAYMENT).count(), 0)
