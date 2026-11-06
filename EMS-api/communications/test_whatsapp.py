"""
WhatsApp notification service (Phase 5, Prompt 3).

Proves send_* only queues, a bad guardian number fails that log without
raising, the Cloud API client posts a Utility template, result messages
omit scores, and a bulk enqueue is spaced by the pair interval.
"""

import io
import uuid
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from academics.models import ClassLevel, Guardian, Session, Student, Term
from assessment.models import TermResultSummary
from communications.exceptions import PermanentNotificationError
from communications.models import NotificationLog
from communications.tasks import clear_channel_senders, send_notification
from communications.whatsapp_client import WhatsAppCloudClient
from communications.whatsapp_schedule import MemorySchedule, RedisSchedule
from communications.whatsapp_service import (
    WhatsAppNotificationService,
    normalize_phone_e164,
    register_whatsapp_sender,
)
from communications.whatsapp_templates import (
    INVOICE_TEMPLATE,
    PAYMENT_TEMPLATE,
    RESULT_TEMPLATE,
    TEMPLATES,
    draft_text,
)
from finance.models import FeeStructure, Invoice, InvoiceLineItem, Payment

User = get_user_model()


class WhatsAppSettingsTests(SimpleTestCase):
    def test_local_settings_use_the_console_backend(self):
        import config.settings.local as local_settings

        self.assertEqual(local_settings.WHATSAPP_BACKEND, 'console')

    def test_production_settings_use_the_cloud_api(self):
        import config.settings.production as production

        self.assertEqual(production.WHATSAPP_BACKEND, 'cloud')
        self.assertNotIn('twilio', production.WHATSAPP_BACKEND.lower())
        self.assertNotIn('messagebird', production.WHATSAPP_BACKEND.lower())


class PhoneNormalizationTests(SimpleTestCase):
    def test_nigerian_national_and_international_forms(self):
        self.assertEqual(normalize_phone_e164('08012345678'), '+2348012345678')
        self.assertEqual(normalize_phone_e164('8012345678'), '+2348012345678')
        self.assertEqual(normalize_phone_e164('2348012345678'), '+2348012345678')
        self.assertEqual(
            normalize_phone_e164('+234 801 234 5678'), '+2348012345678',
        )
        self.assertEqual(
            normalize_phone_e164('002348012345678'), '+2348012345678',
        )
        self.assertEqual(normalize_phone_e164('+14155552671'), '+14155552671')

    def test_missing_and_malformed_are_permanent(self):
        for raw in ('', '   ', None):
            with self.assertRaises(PermanentNotificationError) as raised:
                normalize_phone_e164(raw)
            self.assertIn('missing', str(raised.exception).lower())
        for raw in ('abc', '12345', '08012', '+0123456789', '++2348012345678'):
            with self.assertRaises(PermanentNotificationError) as raised:
                normalize_phone_e164(raw)
            self.assertIn('not a valid E.164', str(raised.exception))


class TemplateDraftTests(SimpleTestCase):
    def test_three_utility_templates_are_ready_to_submit(self):
        self.assertEqual(
            [template.name for template in TEMPLATES],
            [
                'kowe_invoice_generated',
                'kowe_payment_confirmed',
                'kowe_result_published',
            ],
        )
        text = draft_text()
        for template in TEMPLATES:
            submission = template.submission()
            self.assertEqual(submission['category'], 'UTILITY')
            self.assertEqual(submission['language'], 'en')
            body = submission['components'][0]
            self.assertEqual(body['type'], 'BODY')
            self.assertFalse(body['text'].startswith('{{'))
            self.assertFalse(body['text'].rstrip().endswith('}}'))
            self.assertEqual(
                len(body['example']['body_text'][0]),
                len(template.parameter_names),
            )
            self.assertIn(template.name, text)
            self.assertIn(template.body, text)

    def test_result_template_has_no_score_variable(self):
        names = ' '.join(RESULT_TEMPLATE.parameter_names)
        self.assertNotIn('score', names)
        self.assertNotIn('position', names)
        self.assertNotIn('remark', names)
        self.assertNotIn('average', names)
        self.assertIn('portal_url', RESULT_TEMPLATE.parameter_names)
        self.assertNotIn('73.25', RESULT_TEMPLATE.preview(RESULT_TEMPLATE.example))


class PairScheduleTests(SimpleTestCase):
    def test_bulk_enqueue_is_one_lane_six_seconds_apart(self):
        schedule = MemorySchedule()
        now = 1_000_000.0
        first = schedule.reserve('+2348011111111', now=now, interval=6)
        second = schedule.reserve('+2348022222222', now=now, interval=6)
        third = schedule.reserve('+2348011111111', now=now, interval=6)
        self.assertEqual(first, 0.0)
        self.assertEqual(second, 6.0)
        # Same parent as the first send still waits behind the lane,
        # and never shares a 6-second window with their own earlier send.
        self.assertEqual(third, 12.0)
        self.assertGreaterEqual(third - first, 6.0)

    def test_redis_schedule_uses_the_same_lane(self):
        class FakeRedis:
            def __init__(self):
                self.values = {}

            def eval(self, script, numkeys, phone_key, global_key, now, interval, ttl):
                now = float(now)
                interval = float(interval)
                phone_next = float(self.values.get(phone_key, 0))
                global_next = float(self.values.get(global_key, 0))
                slot = max(now, phone_next, global_next)
                nxt = slot + interval
                self.values[phone_key] = nxt
                self.values[global_key] = nxt
                return str(slot - now)

        schedule = RedisSchedule(FakeRedis())
        now = 1_000_000.0
        self.assertEqual(
            schedule.reserve('+2348011111111', now=now, interval=6), 0.0,
        )
        self.assertEqual(
            schedule.reserve('+2348022222222', now=now, interval=6), 6.0,
        )


CLOUD = dict(
    WHATSAPP_BACKEND='cloud',
    WHATSAPP_ACCESS_TOKEN='test-token',
    WHATSAPP_PHONE_NUMBER_ID='106540352242922',
    WHATSAPP_API_VERSION='v21.0',
    WHATSAPP_API_BASE_URL='https://graph.facebook.com',
    WHATSAPP_PAIR_INTERVAL_SECONDS=6,
)


class WhatsAppCloudClientTests(SimpleTestCase):
    @override_settings(**CLOUD)
    def test_posts_a_template_without_a_leading_plus(self):
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = {'messages': [{'id': 'wamid.1'}]}
        with mock.patch(
            'communications.whatsapp_client.requests.post',
            return_value=response,
        ) as post:
            WhatsAppCloudClient().send_template(
                to_e164='+2348012345678',
                template_name='kowe_invoice_generated',
                language='en',
                body_parameters=['Chinedu', 'Adaeze'],
            )
        url = post.call_args.args[0]
        self.assertEqual(
            url,
            'https://graph.facebook.com/v21.0/106540352242922/messages',
        )
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['to'], '2348012345678')
        self.assertEqual(payload['type'], 'template')
        self.assertEqual(payload['template']['name'], 'kowe_invoice_generated')
        self.assertNotIn('test-token', str(payload))
        self.assertTrue(post.call_args.kwargs['headers']['Authorization'].startswith('Bearer '))

    @override_settings(**CLOUD)
    def test_pair_limit_is_transient_and_template_rejection_is_permanent(self):
        client = WhatsAppCloudClient()
        with mock.patch(
            'communications.whatsapp_client.requests.post',
            return_value=_error_response(400, 131056, 'Pair rate limit hit'),
        ):
            with self.assertRaises(Exception) as raised:
                client.send_template(
                    to_e164='+2348012345678',
                    template_name='kowe_invoice_generated',
                    language='en',
                    body_parameters=['Chinedu'],
                )
        from communications.exceptions import TransientNotificationError
        self.assertIsInstance(raised.exception, TransientNotificationError)
        self.assertIn('131056', str(raised.exception))

        with mock.patch(
            'communications.whatsapp_client.requests.post',
            return_value=_error_response(404, 132000, 'Template name does not exist'),
        ):
            with self.assertRaises(PermanentNotificationError) as raised:
                client.send_template(
                    to_e164='+2348012345678',
                    template_name='missing',
                    language='en',
                    body_parameters=['Chinedu'],
                )
        self.assertIn('132000', str(raised.exception))

    @override_settings(**CLOUD)
    def test_network_failure_is_transient(self):
        from communications.exceptions import TransientNotificationError

        with mock.patch(
            'communications.whatsapp_client.requests.post',
            side_effect=requests.Timeout('timed out'),
        ):
            with self.assertRaises(TransientNotificationError) as raised:
                WhatsAppCloudClient().send_template(
                    to_e164='+2348012345678',
                    template_name='kowe_invoice_generated',
                    language='en',
                    body_parameters=['Chinedu'],
                )
        self.assertIn('timed out', str(raised.exception))

    @override_settings(WHATSAPP_BACKEND='cloud', WHATSAPP_ACCESS_TOKEN='', WHATSAPP_PHONE_NUMBER_ID='')
    def test_missing_credentials_are_permanent(self):
        with self.assertRaises(PermanentNotificationError) as raised:
            WhatsAppCloudClient().send_template(
                to_e164='+2348012345678',
                template_name='kowe_invoice_generated',
                language='en',
                body_parameters=['Chinedu'],
            )
        self.assertIn('not configured', str(raised.exception))


def _error_response(status, code, message):
    response = mock.Mock(ok=False, status_code=status)
    response.json.return_value = {'error': {'code': code, 'message': message}}
    return response


class WhatsAppNotificationServiceTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'WhatsApp School'
        return tenant

    def setUp(self):
        super().setUp()
        from communications.whatsapp_schedule import use_memory_schedule

        use_memory_schedule()
        self.addCleanup(use_memory_schedule)
        clear_channel_senders()
        register_whatsapp_sender()
        self.addCleanup(register_whatsapp_sender)
        self.addCleanup(clear_channel_senders)

        self.service = WhatsAppNotificationService()
        self.parent = User.objects.create_user(
            email='parent-wa-p3@example.com',
            password='pass12345',
            first_name='Chinedu',
            last_name='Okonkwo',
        )
        self.bursar = User.objects.create_user(
            email='bursar-wa-p3@example.com',
            password='pass12345',
        )
        Guardian.objects.create(
            user=self.parent,
            full_name='Chinedu Okonkwo',
            relationship_to_student=Guardian.Relationship.FATHER,
            phone_number='08012345678',
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
            admission_number='TA-2042',
            admission_date=date(2024, 9, 9),
        )
        class_level = ClassLevel.objects.create(name='JSS1')
        tuition = FeeStructure.objects.create(
            class_level=class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('150000.00'),
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

    def test_send_invoice_queues_without_calling_graph(self):
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            with mock.patch('communications.whatsapp_client.requests.post') as post:
                log = self.service.send_invoice_generated(self.invoice, self.parent)
        post.assert_not_called()
        delay.assert_called_once_with(str(log.pk), self.tenant.schema_name)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.QUEUED)
        self.assertEqual(log.channel, NotificationLog.Channel.WHATSAPP)
        self.assertEqual(log.trigger_type, NotificationLog.TriggerType.INVOICE_GENERATED)
        self.assertEqual(log.related_object_id, self.invoice.pk)
        self.assertIsNone(log.sent_at)

    def test_each_call_queues_its_own_log(self):
        with mock.patch('communications.whatsapp_schedule.time.time', return_value=1_000_000.0):
            with mock.patch('communications.tasks.send_notification.delay'):
                with mock.patch('communications.tasks.send_notification.apply_async'):
                    first = self.service.send_invoice_generated(self.invoice, self.parent)
                    second = self.service.send_invoice_generated(self.invoice, self.parent)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            NotificationLog.objects.filter(channel=NotificationLog.Channel.WHATSAPP).count(),
            2,
        )

    def test_bulk_queue_staggers_by_the_pair_interval(self):
        other = User.objects.create_user(
            email='parent-wa-p3-b@example.com',
            password='pass12345',
            first_name='Amaka',
        )
        Guardian.objects.create(
            user=other,
            full_name='Amaka Okonkwo',
            phone_number='08098765432',
        )
        with mock.patch(
            'communications.whatsapp_schedule.time.time', return_value=1_000_000.0,
        ):
            with mock.patch('communications.tasks.send_notification.delay') as delay:
                with mock.patch(
                    'communications.tasks.send_notification.apply_async',
                ) as apply_async:
                    first = self.service.send_invoice_generated(self.invoice, self.parent)
                    second = self.service.send_invoice_generated(self.invoice, other)
                    third = self.service.send_invoice_generated(self.invoice, self.parent)
        delay.assert_called_once_with(str(first.pk), self.tenant.schema_name)
        self.assertEqual(apply_async.call_count, 2)
        self.assertEqual(
            apply_async.call_args_list[0].kwargs['countdown'], 6.0,
        )
        self.assertEqual(
            apply_async.call_args_list[0].kwargs['args'],
            (str(second.pk), self.tenant.schema_name),
        )
        self.assertEqual(apply_async.call_args_list[1].kwargs['countdown'], 12.0)
        self.assertEqual(
            apply_async.call_args_list[1].kwargs['args'],
            (str(third.pk), self.tenant.schema_name),
        )

    def test_console_backend_prints_the_invoice_template(self):
        log = self._queue_invoice()
        printed = io.StringIO()
        with mock.patch('communications.whatsapp_client.requests.post') as post:
            with redirect_stdout(printed):
                result = send_notification.apply(
                    args=(str(log.pk), self.tenant.schema_name),
                )
        if not result.successful():
            self.fail(result.traceback)
        post.assert_not_called()
        output = printed.getvalue()
        self.assertIn('kowe_invoice_generated', output)
        self.assertIn('+2348012345678', output)
        self.assertIn('Hello Chinedu', output)
        self.assertIn('₦157,500.50', output)
        self.assertIn('Adaeze Okonkwo', output)
        self.assertIn('WhatsApp School', output)
        self.assertIn('http://tenant.localhost:3000/parent/fees', output)
        self.assertIn('fee notice', output)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNone(log.error_message)

    def test_cloud_backend_sends_invoice_parameters(self):
        log = self._queue_invoice()
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = {'messages': [{'id': 'wamid.1'}]}
        with override_settings(**CLOUD):
            with mock.patch(
                'communications.whatsapp_client.requests.post',
                return_value=response,
            ) as post:
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['template']['name'], INVOICE_TEMPLATE.name)
        values = [
            item['text']
            for item in payload['template']['components'][0]['parameters']
        ]
        self.assertEqual(values[0], 'Chinedu')
        self.assertEqual(values[1], 'Adaeze Okonkwo')
        self.assertIn('2026/2027', values[2])
        self.assertEqual(values[3], 'WhatsApp School')
        self.assertEqual(values[4], '₦157,500.50')
        self.assertEqual(values[5], 'http://tenant.localhost:3000/parent/fees')
        self.assertEqual(payload['to'], '2348012345678')
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_payment_template_includes_both_amounts(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            reference='manual-%s' % uuid.uuid4().hex[:12],
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.MANUAL,
            method=Payment.Method.CASH,
            recorded_by=self.bursar,
            paid_at=timezone.now(),
        )
        with mock.patch('communications.tasks.send_notification.delay'):
            log = self.service.send_payment_confirmed(payment, self.parent)
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = {'messages': [{'id': 'wamid.2'}]}
        with override_settings(**CLOUD):
            with mock.patch(
                'communications.whatsapp_client.requests.post',
                return_value=response,
            ) as post:
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        values = [
            item['text']
            for item in post.call_args.kwargs['json']['template']['components'][0]['parameters']
        ]
        self.assertEqual(post.call_args.kwargs['json']['template']['name'], PAYMENT_TEMPLATE.name)
        self.assertIn('₦50,000.00', values)
        self.assertIn('₦157,500.50', values)
        self.assertIn('http://tenant.localhost:3000/parent/fees', values)

    def test_result_message_omits_scores(self):
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
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = {'messages': [{'id': 'wamid.3'}]}
        with override_settings(**CLOUD):
            with mock.patch(
                'communications.whatsapp_client.requests.post',
                return_value=response,
            ) as post:
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['template']['name'], RESULT_TEMPLATE.name)
        rendered = str(payload)
        self.assertIn('/parent/results', rendered)
        self.assertNotIn('73.25', rendered)
        self.assertNotIn('917', rendered)
        self.assertNotIn('SECRET-REMARK-9f3a', rendered)
        self.assertNotIn('SECRET-ADMIN-REMARK', rendered)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_missing_guardian_fails_without_raising_or_blocking_the_next(self):
        other = User.objects.create_user(
            email='parent-wa-p3-nophone@example.com',
            password='pass12345',
            first_name='Ngozi',
        )
        with mock.patch('communications.tasks.send_notification.delay'):
            bad = self.service.send_invoice_generated(self.invoice, other)
            good = self.service.send_result_published(
                TermResultSummary.objects.create(
                    student=self.student,
                    term=self.term,
                    overall_average=Decimal('10.00'),
                ),
                self.parent,
            )
        self.assertEqual(bad.status, NotificationLog.Status.QUEUED)
        send_notification.apply(args=(str(bad.pk), self.tenant.schema_name))
        bad.refresh_from_db()
        self.assertEqual(bad.status, NotificationLog.Status.FAILED)
        self.assertIn('no guardian profile', bad.error_message)
        printed = io.StringIO()
        with redirect_stdout(printed):
            send_notification.apply(args=(str(good.pk), self.tenant.schema_name))
        good.refresh_from_db()
        self.assertEqual(good.status, NotificationLog.Status.SENT)
        self.assertIn('+2348012345678', printed.getvalue())

    def test_malformed_phone_fails_immediately_and_does_not_retry(self):
        Guardian.objects.filter(user=self.parent).update(phone_number='not-a-number')
        log = self._queue_invoice()
        with mock.patch('communications.whatsapp_client.requests.post') as post:
            with override_settings(**CLOUD):
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        post.assert_not_called()
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('not a valid E.164', log.error_message)

    def test_blank_phone_fails_with_a_missing_message(self):
        Guardian.objects.filter(user=self.parent).update(phone_number='   ')
        log = self._queue_invoice()
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('missing', log.error_message.lower())

    def test_pair_limit_from_graph_retries_then_fails(self):
        log = self._queue_invoice()
        with override_settings(**CLOUD):
            with mock.patch(
                'communications.whatsapp_client.requests.post',
                return_value=_error_response(400, 131056, 'Pair rate limit hit'),
            ) as post:
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        self.assertEqual(post.call_count, 3)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('131056', log.error_message)

    def test_rejected_template_does_not_retry(self):
        log = self._queue_invoice()
        with override_settings(**CLOUD):
            with mock.patch(
                'communications.whatsapp_client.requests.post',
                return_value=_error_response(404, 132000, 'Template name does not exist'),
            ) as post:
                send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        self.assertEqual(post.call_count, 1)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('132000', log.error_message)

    def test_deleted_invoice_fails_immediately(self):
        log = self._queue_invoice()
        self.invoice.delete()
        send_notification.apply(args=(str(log.pk), self.tenant.schema_name))
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('no longer exists', log.error_message)

    def _queue_invoice(self):
        with mock.patch('communications.tasks.send_notification.delay'):
            return self.service.send_invoice_generated(self.invoice, self.parent)
