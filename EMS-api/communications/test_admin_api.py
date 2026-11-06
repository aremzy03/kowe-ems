"""
Admin visibility into notification delivery (Phase 5, Prompt 6).

School admins with confirmed TOTP can list and filter NotificationLog
rows for the current tenant, and re-queue a failed row on the same
primary key. Other roles cannot. Resend does not insert a second log
and does not publish until the status write commits.
"""

import uuid
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from communications.models import NotificationLog
from communications.tasks import (
    get_channel_sender,
    register_channel_sender,
    send_notification,
)
from memberships.models import SchoolMembership
from memberships.permissions import TWO_FACTOR_REQUIRED_MESSAGE
from platform_admin.testing import set_tenant_slug

User = get_user_model()

LIST_URL = '/api/communications/notifications/'


def _aware(year, month, day, hour=0, minute=0, second=0):
    return timezone.make_aware(datetime(year, month, day, hour, minute, second))


class NotificationAdminVisibilityTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Notify Admin School'
        return tenant

    def setUp(self):
        super().setUp()
        self.admin = self._user('admin-vis', SchoolMembership.Role.ADMIN, totp=True)
        self.admin_no_2fa = self._user(
            'admin-vis-plain', SchoolMembership.Role.ADMIN, totp=False,
        )
        self.bursar = self._user('bursar-vis', SchoolMembership.Role.BURSAR, totp=True)
        self.teacher = self._user('teacher-vis', SchoolMembership.Role.TEACHER)
        self.parent = self._user(
            'parent-vis',
            SchoolMembership.Role.PARENT,
            first_name='Ada',
            last_name='Okoye',
        )
        self.other_parent = self._user(
            'parent-vis-2', SchoolMembership.Role.PARENT,
        )
        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

        self.failed_invoice = self._log(
            recipient=self.parent,
            status=NotificationLog.Status.FAILED,
            trigger=NotificationLog.TriggerType.INVOICE_GENERATED,
            channel=NotificationLog.Channel.WHATSAPP,
            created_at=_aware(2026, 11, 2, 12, 0, 0),
            error_message='Template rejected: invoice_generated',
        )
        self.sent_payment = self._log(
            recipient=self.parent,
            status=NotificationLog.Status.SENT,
            trigger=NotificationLog.TriggerType.PAYMENT_CONFIRMED,
            channel=NotificationLog.Channel.EMAIL,
            created_at=_aware(2026, 11, 1, 8, 0, 0),
            sent_at=_aware(2026, 11, 1, 8, 0, 5),
        )
        self.queued_result = self._log(
            recipient=self.other_parent,
            status=NotificationLog.Status.QUEUED,
            trigger=NotificationLog.TriggerType.RESULT_PUBLISHED,
            channel=NotificationLog.Channel.EMAIL,
            created_at=_aware(2026, 11, 3, 9, 30, 0),
        )
        self.edge_start = self._log(
            recipient=self.parent,
            status=NotificationLog.Status.FAILED,
            trigger=NotificationLog.TriggerType.PAYMENT_CONFIRMED,
            channel=NotificationLog.Channel.EMAIL,
            created_at=_aware(2026, 11, 2, 0, 0, 0),
            error_message='smtp down',
        )
        self.before_window = self._log(
            recipient=self.parent,
            status=NotificationLog.Status.FAILED,
            trigger=NotificationLog.TriggerType.INVOICE_GENERATED,
            channel=NotificationLog.Channel.EMAIL,
            created_at=_aware(2026, 11, 1, 23, 59, 59),
            error_message='older failure',
        )

    def _user(self, prefix, role, totp=False, first_name='', last_name=''):
        user = User.objects.create_user(
            email=f'{prefix}@example.com',
            password='pass12345',
            first_name=first_name,
            last_name=last_name,
        )
        SchoolMembership.objects.create(user=user, role=role, is_active=True)
        if totp:
            TOTPDevice.objects.create(user=user, name='test', confirmed=True)
        return user

    def _log(
        self,
        *,
        recipient,
        status,
        trigger,
        channel,
        created_at,
        error_message=None,
        sent_at=None,
    ):
        log = NotificationLog.objects.create(
            recipient=recipient,
            channel=channel,
            trigger_type=trigger,
            status=status,
            related_object_id=uuid.uuid4(),
            error_message=error_message,
            sent_at=sent_at,
        )
        NotificationLog.objects.filter(pk=log.pk).update(created_at=created_at)
        log.refresh_from_db()
        return log

    def tearDown(self):
        # A request with no tenant header leaves the connection on public.
        # Later tests in this class need the tenant schema again.
        connection.set_tenant(self.tenant)
        super().tearDown()

    def _as(self, user):
        self.api.force_authenticate(user=user)
        return self.api

    def _resend(self, user, log, **extra):
        self._as(user)
        return self.api.post(f'{LIST_URL}{log.pk}/resend/', extra, format='json')

    def _ids(self, response):
        return [row['id'] for row in response.data]

    def test_admin_lists_newest_first_with_recipient_and_error(self):
        response = self._as(self.admin).get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = self._ids(response)
        self.assertEqual(
            ids,
            [
                str(self.queued_result.pk),
                str(self.failed_invoice.pk),
                str(self.edge_start.pk),
                str(self.before_window.pk),
                str(self.sent_payment.pk),
            ],
        )
        failed = next(row for row in response.data if row['id'] == str(self.failed_invoice.pk))
        # FK pks stay UUID objects in serializer.data; JSON renders them
        # as strings. Compare both forms.
        self.assertEqual(str(failed['recipient']), str(self.parent.pk))
        self.assertEqual(failed['recipient_email'], 'parent-vis@example.com')
        self.assertEqual(failed['recipient_name'], 'Ada Okoye')
        self.assertEqual(failed['channel'], 'whatsapp')
        self.assertEqual(failed['trigger_type'], 'invoice_generated')
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error_message'], 'Template rejected: invoice_generated')
        self.assertIsNone(failed['sent_at'])
        self.assertEqual(
            str(failed['related_object_id']),
            str(self.failed_invoice.related_object_id),
        )

    def test_filter_by_status_trigger_and_channel(self):
        failed = self._as(self.admin).get(LIST_URL, {'status': 'failed'})
        self.assertEqual(
            set(self._ids(failed)),
            {
                str(self.failed_invoice.pk),
                str(self.edge_start.pk),
                str(self.before_window.pk),
            },
        )

        invoices = self._as(self.admin).get(
            LIST_URL, {'trigger_type': 'invoice_generated'},
        )
        self.assertEqual(
            set(self._ids(invoices)),
            {str(self.failed_invoice.pk), str(self.before_window.pk)},
        )

        whatsapp_failures = self._as(self.admin).get(
            LIST_URL,
            {
                'status': 'failed',
                'trigger_type': 'invoice_generated',
                'channel': 'whatsapp',
            },
        )
        self.assertEqual(self._ids(whatsapp_failures), [str(self.failed_invoice.pk)])

    def test_date_range_includes_the_whole_calendar_day(self):
        response = self._as(self.admin).get(
            LIST_URL,
            {'created_from': '2026-11-02', 'created_to': '2026-11-02'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            set(self._ids(response)),
            {str(self.failed_invoice.pk), str(self.edge_start.pk)},
        )

    def test_datetime_bounds_are_exact(self):
        response = self._as(self.admin).get(
            LIST_URL,
            {
                'created_from': '2026-11-02T12:00:00+01:00',
                'created_to': '2026-11-02T12:00:00+01:00',
            },
        )
        self.assertEqual(self._ids(response), [str(self.failed_invoice.pk)])

    def test_blank_filters_are_ignored(self):
        response = self._as(self.admin).get(LIST_URL, {'status': '', 'channel': '  '})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

    def test_invalid_filters_are_400(self):
        bad_status = self._as(self.admin).get(LIST_URL, {'status': 'bounced'})
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', bad_status.data)

        bad_trigger = self._as(self.admin).get(
            LIST_URL, {'trigger_type': 'fee_reminder'},
        )
        self.assertEqual(bad_trigger.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('trigger_type', bad_trigger.data)

        bad_date = self._as(self.admin).get(LIST_URL, {'created_from': 'yesterday'})
        self.assertEqual(bad_date.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('created_from', bad_date.data)

        backwards = self._as(self.admin).get(
            LIST_URL,
            {'created_from': '2026-11-03', 'created_to': '2026-11-01'},
        )
        self.assertEqual(backwards.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('created_to', backwards.data)

    def test_retrieve_one_log(self):
        response = self._as(self.admin).get(f'{LIST_URL}{self.sent_payment.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.sent_payment.pk))
        self.assertEqual(response.data['status'], 'sent')
        self.assertIsNotNone(response.data['sent_at'])

    def test_unknown_and_malformed_ids_are_404(self):
        missing = self._as(self.admin).get(f'{LIST_URL}{uuid.uuid4()}/')
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        malformed = self._as(self.admin).get(f'{LIST_URL}not-a-uuid/')
        self.assertEqual(malformed.status_code, status.HTTP_404_NOT_FOUND)
        bad_resend = self._as(self.admin).post(f'{LIST_URL}{uuid.uuid4()}/resend/')
        self.assertEqual(bad_resend.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(REQUIRE_ADMIN_2FA=True)
    def test_non_admins_cannot_list_or_resend(self):
        for user in (self.bursar, self.teacher, self.parent, self.admin_no_2fa):
            listed = self._as(user).get(LIST_URL)
            self.assertEqual(listed.status_code, status.HTTP_403_FORBIDDEN, user.email)
            resent = self._resend(user, self.failed_invoice)
            self.assertEqual(resent.status_code, status.HTTP_403_FORBIDDEN, user.email)

        self.failed_invoice.refresh_from_db()
        self.assertEqual(self.failed_invoice.status, NotificationLog.Status.FAILED)
        self.assertEqual(
            self._as(self.admin_no_2fa).get(LIST_URL).data['detail'],
            TWO_FACTOR_REQUIRED_MESSAGE,
        )
        self.assertEqual(
            self._as(self.bursar).get(LIST_URL).data['detail'],
            'School admin role required.',
        )

    def test_anonymous_is_401_and_missing_tenant_is_400(self):
        self.api.force_authenticate(user=None)
        anonymous = self.api.get(LIST_URL)
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

        bare = APIClient()
        missing_tenant = bare.get(LIST_URL)
        self.assertEqual(missing_tenant.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_tenant.json()['detail'], 'Tenant identification required')

    def test_collection_is_read_only(self):
        response = self._as(self.admin).post(LIST_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(NotificationLog.objects.count(), 5)

    def test_resend_requeues_the_same_failed_row_on_commit(self):
        before = NotificationLog.objects.count()
        with mock.patch('communications.tasks.send_notification.delay') as delay, \
                mock.patch('communications.tasks.send_notification.apply_async') as later:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._resend(
                    self.admin,
                    self.failed_invoice,
                    status='sent',
                    error_message='forged',
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['id'], str(self.failed_invoice.pk))
        self.assertEqual(response.data['status'], 'queued')
        self.assertIsNone(response.data['error_message'])
        self.assertIsNone(response.data['sent_at'])
        self.assertEqual(NotificationLog.objects.count(), before)

        self.failed_invoice.refresh_from_db()
        self.assertEqual(self.failed_invoice.status, NotificationLog.Status.QUEUED)
        self.assertIsNone(self.failed_invoice.error_message)
        self.assertIsNone(self.failed_invoice.sent_at)

        delay.assert_called_once_with(
            str(self.failed_invoice.pk),
            self.tenant.schema_name,
        )
        later.assert_not_called()

    def test_resend_does_not_publish_before_commit(self):
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            response = self._resend(self.admin, self.failed_invoice)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'queued')
        delay.assert_not_called()

    def test_resend_refuses_sent_and_queued_rows(self):
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                sent = self._resend(self.admin, self.sent_payment)
                queued = self._resend(self.admin, self.queued_result)
        self.assertEqual(sent.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(queued.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(sent.data['detail'], 'Only failed notifications can be resent.')
        delay.assert_not_called()
        self.sent_payment.refresh_from_db()
        self.queued_result.refresh_from_db()
        self.assertEqual(self.sent_payment.status, NotificationLog.Status.SENT)
        self.assertEqual(self.queued_result.status, NotificationLog.Status.QUEUED)
        self.assertIsNotNone(self.sent_payment.sent_at)

    def test_second_resend_while_queued_is_refused(self):
        with mock.patch('communications.tasks.send_notification.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                first = self._resend(self.admin, self.failed_invoice)
                second = self._resend(self.admin, self.failed_invoice)
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(NotificationLog.objects.count(), 5)
        delay.assert_called_once()

    def test_requeued_row_is_delivered_by_the_existing_task(self):
        """The same primary key goes back through send_notification."""
        previous = get_channel_sender(NotificationLog.Channel.WHATSAPP)
        seen = []

        def sender(notification):
            seen.append(notification.pk)

        register_channel_sender(NotificationLog.Channel.WHATSAPP, sender)

        def _restore_sender():
            if previous is None:
                from communications.whatsapp_service import register_whatsapp_sender
                register_whatsapp_sender()
            else:
                register_channel_sender(
                    NotificationLog.Channel.WHATSAPP, previous,
                )

        self.addCleanup(_restore_sender)

        with mock.patch('communications.tasks.send_notification.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self._resend(self.admin, self.failed_invoice)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        result = send_notification.apply(
            args=(str(self.failed_invoice.pk), self.tenant.schema_name),
        )
        self.assertEqual(result.result, str(self.failed_invoice.pk))
        self.assertEqual(seen, [self.failed_invoice.pk])
        self.failed_invoice.refresh_from_db()
        self.assertEqual(self.failed_invoice.status, NotificationLog.Status.SENT)
        self.assertIsNone(self.failed_invoice.error_message)
        self.assertIsNotNone(self.failed_invoice.sent_at)
        self.assertEqual(NotificationLog.objects.count(), 5)
