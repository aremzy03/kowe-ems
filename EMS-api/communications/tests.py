"""
NotificationLog + Celery skeleton (Phase 5, Prompt 1).

Proves the task updates the log from inside the tenant schema, retries
only transient failures (3 attempts total), and that enqueue publishes
to the broker instead of sending inline.
"""

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name, schema_context

from communications.exceptions import (
    PermanentNotificationError,
    TransientNotificationError,
)
from communications.models import NotificationLog
from communications.tasks import (
    MAX_NOTIFICATION_ATTEMPTS,
    NOTIFICATION_MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    clear_channel_senders,
    enqueue_notification,
    register_channel_sender,
    retry_countdown,
    send_notification,
)

User = get_user_model()


class NotificationLogTaskTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Notify School'
        return tenant

    def setUp(self):
        super().setUp()
        clear_channel_senders()
        self.addCleanup(clear_channel_senders)
        self.recipient = User.objects.create_user(
            email='parent-notify@example.com',
            password='pass12345',
        )

    def _log(self, **overrides):
        fields = {
            'recipient': self.recipient,
            'channel': NotificationLog.Channel.EMAIL,
            'trigger_type': NotificationLog.TriggerType.INVOICE_GENERATED,
            'related_object_id': uuid.uuid4(),
        }
        fields.update(overrides)
        return NotificationLog.objects.create(**fields)

    def _apply(self, log):
        return send_notification.apply(
            args=(str(log.pk), self.tenant.schema_name),
        )

    def test_model_defaults_to_queued(self):
        log = self._log()
        self.assertEqual(log.status, NotificationLog.Status.QUEUED)
        self.assertIsNone(log.sent_at)
        self.assertIsNone(log.error_message)
        self.assertEqual(log.channel, NotificationLog.Channel.EMAIL)

    def test_success_marks_sent(self):
        log = self._log()
        seen = []

        def sender(notification):
            seen.append(notification.pk)

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        result = self._apply(log)

        self.assertEqual(result.result, str(log.pk))
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNotNone(log.sent_at)
        self.assertIsNone(log.error_message)
        self.assertEqual(seen, [log.pk])

    def test_permanent_failure_does_not_retry(self):
        log = self._log(channel=NotificationLog.Channel.WHATSAPP)
        calls = {'n': 0}

        def sender(notification):
            calls['n'] += 1
            raise PermanentNotificationError('Template rejected: invoice_generated')

        register_channel_sender(NotificationLog.Channel.WHATSAPP, sender)
        self._apply(log)

        self.assertEqual(calls['n'], 1)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIsNone(log.sent_at)
        self.assertIn('Template rejected', log.error_message)

    def test_missing_sender_is_permanent_failure(self):
        log = self._log()
        self._apply(log)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('No sender registered', log.error_message)

    def test_transient_failure_retries_then_marks_failed(self):
        log = self._log()
        calls = {'n': 0}

        def sender(notification):
            calls['n'] += 1
            raise TransientNotificationError('WhatsApp rate limit')

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        self._apply(log)

        self.assertEqual(calls['n'], MAX_NOTIFICATION_ATTEMPTS)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('rate limit', log.error_message)
        self.assertIsNone(log.sent_at)

    def test_transient_then_success_on_retry(self):
        log = self._log()
        calls = {'n': 0}

        def sender(notification):
            calls['n'] += 1
            if calls['n'] == 1:
                raise TransientNotificationError('temporary network error')

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        self._apply(log)

        self.assertEqual(calls['n'], 2)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNone(log.error_message)
        self.assertIsNotNone(log.sent_at)

    def test_already_sent_is_not_delivered_again(self):
        log = self._log()
        calls = {'n': 0}

        def sender(notification):
            calls['n'] += 1

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        self._apply(log)
        self._apply(log)

        self.assertEqual(calls['n'], 1)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_task_switches_to_the_named_tenant_schema(self):
        log = self._log()
        seen_schema = {}

        def sender(notification):
            seen_schema['name'] = connection.schema_name
            self.assertEqual(notification.pk, log.pk)

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        with schema_context(get_public_schema_name()):
            send_notification.apply(args=(str(log.pk), self.tenant.schema_name))

        connection.set_tenant(self.tenant)
        self.assertEqual(seen_schema['name'], self.tenant.schema_name)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_unknown_log_id_is_a_no_op(self):
        result = send_notification.apply(
            args=(str(uuid.uuid4()), self.tenant.schema_name),
        )
        self.assertIsNone(result.result)

    def test_malformed_log_id_is_a_no_op(self):
        result = send_notification.apply(
            args=('not-a-uuid', self.tenant.schema_name),
        )
        self.assertIsNone(result.result)

    def test_enqueue_publishes_id_and_schema_without_sending(self):
        log = self._log()

        def sender(notification):
            raise AssertionError('enqueue must not call the sender')

        register_channel_sender(NotificationLog.Channel.EMAIL, sender)
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            enqueue_notification(log)

        delay.assert_called_once_with(str(log.pk), self.tenant.schema_name)
        log.refresh_from_db()
        self.assertEqual(log.status, NotificationLog.Status.QUEUED)
        self.assertIsNone(log.sent_at)

    def test_retry_configuration(self):
        self.assertEqual(send_notification.max_retries, NOTIFICATION_MAX_RETRIES)
        self.assertEqual(NOTIFICATION_MAX_RETRIES, MAX_NOTIFICATION_ATTEMPTS - 1)
        self.assertTrue(send_notification.acks_late)
        # Jitter is on in production; the unjittered curve is factor * 2**n.
        from celery.utils.time import get_exponential_backoff_interval

        self.assertEqual(
            get_exponential_backoff_interval(
                RETRY_BACKOFF_FACTOR, 0, 600, full_jitter=False,
            ),
            2,
        )
        self.assertEqual(
            get_exponential_backoff_interval(
                RETRY_BACKOFF_FACTOR, 1, 600, full_jitter=False,
            ),
            4,
        )
        self.assertEqual(
            get_exponential_backoff_interval(
                RETRY_BACKOFF_FACTOR, 2, 600, full_jitter=False,
            ),
            8,
        )
        # The live countdown stays inside that cap.
        self.assertLessEqual(retry_countdown(0), 2)
        self.assertLessEqual(retry_countdown(1), 4)
        self.assertGreaterEqual(retry_countdown(0), 0)
