"""
Payment-account onboarding tests (Phase 4, Prompt 1), fee-structure /
invoicing tests (Phase 4, Prompt 2), payment initialization tests
(Phase 4, Prompt 3), and server-side verify-and-apply tests (Phase 4,
Prompt 4).

The Paystack HTTP layer is mocked at ``requests.request`` so the real client
code in finance/paystack.py (envelope handling, error mapping, kobo
conversion) is exercised. Payload shapes mirror Paystack's documented
test-mode responses.

Money-safety invariants proven here:
  * resolve runs BEFORE subaccount creation; a failed resolve creates nothing
  * the stored account_name is Paystack's resolved value, not admin input
  * account_number never appears unmasked in any API response
  * one payment account per gateway — a second submission is a 409 no-op
  * commission comes from the platform-wide setting, ignoring request input
  * naira→kobo conversion is Decimal-only and happens only at the gateway
    boundary (₦157500.50 → 15750050 kobo)
  * initialize creates a pending Payment and does not mark the invoice paid
  * initialize is blocked without an active verified SchoolPaymentAccount
  * verify_and_apply_payment is the single apply function; the return-flow
    endpoint AND the platform webhook both call it
  * webhook HMAC is verified on raw request.body BEFORE JSON is parsed
  * unknown subaccount is rejected; duplicate webhook does not double-credit
  * amount is matched against the stored Payment in kobo
  * applying the same SUCCESS reference twice does not double-count
  * bursar/admin manual cash/transfer creates SUCCESS gateway=manual and
    updates invoice status via recompute_invoice_payment_status (not
    verify_and_apply_payment)
  * staff invoice list is admin/bursar only, stays in the current tenant
    schema, and can filter by term and class level
  * staff invoice retrieve nests payments; pending Paystack is not paid
  * staff payment list/retrieve is admin/bursar only; filters invoice /
    status / term; successful payments cannot be deleted over HTTP
  * PlatformTransactionLog is written only inside verify_and_apply_payment
    after Paystack SUCCESS (webhook and return-flow share that write);
    manual recordings never write it
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from finance.models import SchoolPaymentAccount
from memberships.models import SchoolMembership
from platform_admin.testing import set_tenant_slug

User = get_user_model()

URL = '/api/finance/payment-account/'

RESOLVE_OK = {
    'status': True,
    'message': 'Account number resolved',
    'data': {
        'account_number': '0000000000',
        'account_name': 'PAYSTACK TEST ACCOUNT',
        'bank_id': 21,
    },
}

SUBACCOUNT_OK = {
    'status': True,
    'message': 'Subaccount created',
    'data': {
        'subaccount_code': 'ACCT_testsubacct123',
        'business_name': 'Test School',
        'settlement_bank': 'Zenith Bank',
        'account_number': '0000000000',
        'percentage_charge': 5.0,
        'is_verified': False,
        'active': True,
    },
}

RESOLVE_FAILED = {
    'status': False,
    'message': 'Could not resolve account name. Check parameters or try again.',
}


def _response(payload, status_code=200):
    resp = mock.Mock()
    resp.ok = 200 <= status_code < 300
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


class SchoolPaymentAccountOnboardingTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Test School'
        return tenant

    def setUp(self):
        super().setUp()
        # NB: class-level @override_settings does not work with TenantTestCase
        # (its setUpClass never calls super().setUpClass(), so the override
        # context is never enabled) — enable per-test instead.
        overrides = override_settings(
            PAYSTACK_SECRET_KEY='sk_test_dummy',
            PLATFORM_COMMISSION_PCT=Decimal('5.00'),
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.admin = User.objects.create_user(
            email='admin-fin@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=self.admin,
            role=SchoolMembership.Role.ADMIN,
            is_active=True,
        )
        # IsSchoolAdmin requires confirmed TOTP (shared User / public schema).
        TOTPDevice.objects.create(user=self.admin, name='test', confirmed=True)

        self.bursar = User.objects.create_user(
            email='bursar-fin@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=self.bursar,
            role=SchoolMembership.Role.BURSAR,
            is_active=True,
        )
        TOTPDevice.objects.create(user=self.bursar, name='test', confirmed=True)

        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

    def _post(self, **overrides):
        payload = {'bank_code': '057', 'account_number': '0000000000'}
        payload.update(overrides)
        return self.api.post(URL, payload, format='json')

    def test_full_onboarding_flow_resolve_then_subaccount_then_store(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK), _response(SUBACCOUNT_OK, 201)],
        ) as http:
            response = self._post()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        # Exact call order: resolve first, subaccount second.
        resolve_call, create_call = http.call_args_list
        self.assertEqual(resolve_call.args, ('GET', 'https://api.paystack.co/bank/resolve'))
        self.assertEqual(
            resolve_call.kwargs['params'],
            {'account_number': '0000000000', 'bank_code': '057'},
        )
        self.assertEqual(create_call.args, ('POST', 'https://api.paystack.co/subaccount'))
        self.assertEqual(
            create_call.kwargs['json'],
            {
                'business_name': 'Test School',
                'settlement_bank': '057',
                'account_number': '0000000000',
                'percentage_charge': 5.0,
            },
        )

        account = SchoolPaymentAccount.objects.get()
        self.assertEqual(account.subaccount_code, 'ACCT_testsubacct123')
        self.assertEqual(account.bank_name, 'Zenith Bank')
        self.assertEqual(account.account_name, 'PAYSTACK TEST ACCOUNT')
        self.assertEqual(account.account_number, '0000000000')
        self.assertEqual(account.platform_commission_pct, Decimal('5.00'))
        self.assertTrue(account.is_verified)
        self.assertTrue(account.is_active)
        self.assertEqual(account.created_by, self.admin)

        # Masked in the response; full number never leaves the API.
        self.assertEqual(response.data['account_number'], '****0000')
        self.assertNotIn('0000000000', str(response.data))

        # Prompt 5: public-schema map written on the same success path.
        from django.db import connection
        from django_tenants.utils import get_public_schema_name, schema_context
        from platform_admin.models import SubaccountTenantMap

        tenant_id = self.tenant.id
        with schema_context(get_public_schema_name()):
            mapping = SubaccountTenantMap.objects.get(
                subaccount_code='ACCT_testsubacct123'
            )
            self.assertEqual(mapping.tenant_id, tenant_id)
        connection.set_tenant(self.tenant)

    def test_resolved_name_stored_not_admin_typed_name(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK), _response(SUBACCOUNT_OK, 201)],
        ):
            # Same tokens, different case/order — accepted, but resolved
            # value is what gets stored.
            response = self._post(account_name='account paystack TEST')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            SchoolPaymentAccount.objects.get().account_name,
            'PAYSTACK TEST ACCOUNT',
        )

    def test_account_name_mismatch_blocks_before_subaccount_creation(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK)],
        ) as http:
            response = self._post(account_name='Someone Else Entirely')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(http.call_count, 1)  # resolve only — no subaccount
        self.assertEqual(SchoolPaymentAccount.objects.count(), 0)

    def test_failed_resolve_stores_nothing_and_never_creates_subaccount(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_FAILED, 422)],
        ) as http:
            response = self._post(account_number='1234567890')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(SchoolPaymentAccount.objects.count(), 0)

        from django.db import connection
        from django_tenants.utils import get_public_schema_name, schema_context
        from platform_admin.models import SubaccountTenantMap

        with schema_context(get_public_schema_name()):
            self.assertEqual(SubaccountTenantMap.objects.count(), 0)
        connection.set_tenant(self.tenant)

    def test_second_submission_is_conflict_without_gateway_calls(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK), _response(SUBACCOUNT_OK, 201)],
        ):
            first = self._post()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        with mock.patch('finance.paystack.requests.request') as http:
            second = self._post()
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        http.assert_not_called()
        self.assertEqual(SchoolPaymentAccount.objects.count(), 1)

    def test_gateway_5xx_maps_to_502_and_stores_nothing(self):
        self.api.force_authenticate(user=self.admin)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response({'status': False, 'message': 'oops'}, 500)],
        ):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(SchoolPaymentAccount.objects.count(), 0)

    def test_bursar_can_onboard(self):
        self.api.force_authenticate(user=self.bursar)
        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK), _response(SUBACCOUNT_OK, 201)],
        ):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(SchoolPaymentAccount.objects.get().created_by, self.bursar)
        self.assertEqual(response.data['account_number'], '****0000')

    def test_teacher_cannot_onboard(self):
        teacher = User.objects.create_user(
            email='teacher-fin@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(
            user=teacher,
            role=SchoolMembership.Role.TEACHER,
            is_active=True,
        )
        self.api.force_authenticate(user=teacher)
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        http.assert_not_called()

    def test_unauthenticated_rejected(self):
        response = self._post()
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_get_reports_onboarding_state_masked(self):
        self.api.force_authenticate(user=self.admin)

        before = self.api.get(URL)
        self.assertEqual(before.status_code, status.HTTP_200_OK)
        self.assertFalse(before.data['onboarded'])

        with mock.patch(
            'finance.paystack.requests.request',
            side_effect=[_response(RESOLVE_OK), _response(SUBACCOUNT_OK, 201)],
        ):
            self._post()

        after = self.api.get(URL)
        self.assertTrue(after.data['onboarded'])
        self.assertEqual(after.data['account']['account_number'], '****0000')
        self.assertEqual(after.data['account']['subaccount_code'], 'ACCT_testsubacct123')


# ---------------------------------------------------------------------------
# Fee structures and invoicing (Prompt 2)
# ---------------------------------------------------------------------------

FEES_URL = '/api/finance/fee-structures/'
GENERATE_URL = '/api/finance/invoices/generate/'
INVOICES_URL = '/api/finance/invoices/'
MY_INVOICES_URL = '/api/finance/my-invoices/'


class FinanceInvoicingTestCase(TenantTestCase):
    """Shared fixture: users of every role plus a class of enrolled students."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.school_name = 'Test School'
        return tenant

    def setUp(self):
        super().setUp()
        from datetime import date

        from academics.models import (
            Arm,
            ClassLevel,
            Enrollment,
            Guardian,
            Session,
            Student,
            StudentGuardianLink,
            Term,
        )

        self.admin = self._make_user('admin-inv', SchoolMembership.Role.ADMIN, totp=True)
        self.bursar = self._make_user(
            'bursar-inv', SchoolMembership.Role.BURSAR, totp=True
        )
        self.teacher = self._make_user('teacher-inv', SchoolMembership.Role.TEACHER)
        self.parent = self._make_user('parent-inv', SchoolMembership.Role.PARENT)
        self.other_parent = self._make_user(
            'parent2-inv', SchoolMembership.Role.PARENT
        )

        self.session = Session.objects.create(
            name='2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            session=self.session,
            name=Term.Name.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18),
            is_active=True,
        )
        self.class_level = ClassLevel.objects.create(name='JSS1')
        self.other_class_level = ClassLevel.objects.create(name='JSS2')
        self.arm = Arm.objects.create(class_level=self.class_level, name='A')

        self.students = []
        for i in range(3):
            student = Student.objects.create(
                first_name=f'First{i}',
                last_name=f'Last{i}',
                date_of_birth=date(2014, 1, 1),
                gender=Student.Gender.MALE,
                admission_number=f'ADM-00{i}',
                admission_date=date(2026, 9, 1),
            )
            Enrollment.objects.create(
                student=student,
                class_level=self.class_level,
                arm=self.arm,
                session=self.session,
                term=self.term,
                status=Enrollment.Status.ACTIVE,
            )
            self.students.append(student)

        # self.parent is linked to students[0] only.
        guardian = Guardian.objects.create(user=self.parent)
        StudentGuardianLink.objects.create(
            student=self.students[0],
            guardian=guardian,
            is_primary_contact=True,
        )

        self.api = APIClient()
        set_tenant_slug(self.api, self.tenant)

    def _make_user(self, prefix, role, totp=False):
        user = User.objects.create_user(
            email=f'{prefix}@example.com',
            password='pass12345',
        )
        SchoolMembership.objects.create(user=user, role=role, is_active=True)
        if totp:
            # IsSchoolAdmin / IsAdminOrBursar require confirmed TOTP.
            TOTPDevice.objects.create(user=user, name='test', confirmed=True)
        return user

    def _make_fees(self):
        from finance.models import FeeStructure

        tuition = FeeStructure.objects.create(
            class_level=self.class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('150000.00'),
        )
        pta = FeeStructure.objects.create(
            class_level=self.class_level,
            term=self.term,
            name='PTA Levy',
            amount=Decimal('5000.00'),
        )
        sports = FeeStructure.objects.create(
            class_level=self.class_level,
            term=self.term,
            name='Sports Fee',
            amount=Decimal('2500.50'),
        )
        return [tuition, pta, sports]

    def _generate(self, user, **overrides):
        self.api.force_authenticate(user=user)
        payload = {
            'class_level': str(self.class_level.id),
            'term': str(self.term.id),
        }
        payload.update(overrides)
        return self.api.post(GENERATE_URL, payload, format='json')


class FeeStructureCrudTests(FinanceInvoicingTestCase):
    def test_admin_can_create_list_update_delete(self):
        self.api.force_authenticate(user=self.admin)

        create = self.api.post(
            FEES_URL,
            {
                'class_level': str(self.class_level.id),
                'term': str(self.term.id),
                'name': 'Tuition',
                'amount': '150000.00',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data['amount'], '150000.00')
        fee_id = create.data['id']

        listed = self.api.get(FEES_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)

        updated = self.api.patch(
            f'{FEES_URL}{fee_id}/', {'amount': '160000.00'}, format='json'
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['amount'], '160000.00')

        deleted = self.api.delete(f'{FEES_URL}{fee_id}/')
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_bursar_can_create_and_list_fee_structures(self):
        self.api.force_authenticate(user=self.bursar)
        create = self.api.post(
            FEES_URL,
            {
                'class_level': str(self.class_level.id),
                'term': str(self.term.id),
                'name': 'Bursar Levy',
                'amount': '5000.00',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        listed = self.api.get(FEES_URL)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(listed.data), 1)

    def test_teacher_and_parent_cannot_touch_fee_structures(self):
        for user in (self.teacher, self.parent):
            self.api.force_authenticate(user=user)
            response = self.api.post(
                FEES_URL,
                {
                    'class_level': str(self.class_level.id),
                    'term': str(self.term.id),
                    'name': 'Tuition',
                    'amount': '1000.00',
                },
                format='json',
            )
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_duplicate_fee_name_for_class_term_rejected(self):
        self._make_fees()
        self.api.force_authenticate(user=self.admin)
        response = self.api.post(
            FEES_URL,
            {
                'class_level': str(self.class_level.id),
                'term': str(self.term.id),
                'name': 'Tuition',
                'amount': '99999.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_positive_amount_rejected(self):
        self.api.force_authenticate(user=self.admin)
        for bad_amount in ('0.00', '-100.00'):
            response = self.api.post(
                FEES_URL,
                {
                    'class_level': str(self.class_level.id),
                    'term': str(self.term.id),
                    'name': 'Weird Fee',
                    'amount': bad_amount,
                },
                format='json',
            )
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, bad_amount
            )

    def test_fee_referenced_by_invoice_cannot_be_deleted(self):
        fees = self._make_fees()
        self._generate(self.admin)
        self.api.force_authenticate(user=self.admin)
        response = self.api.delete(f'{FEES_URL}{fees[0].id}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_schoolwide_fee_has_no_class_level(self):
        self.api.force_authenticate(user=self.bursar)
        created = self.api.post(
            FEES_URL,
            {
                'class_level': None,
                'term': str(self.term.id),
                'name': 'School Bus',
                'amount': '8000.00',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertIsNone(created.data['class_level'])
        self.assertIsNone(created.data['class_level_name'])

        duplicate = self.api.post(
            FEES_URL,
            {
                'term': str(self.term.id),
                'name': 'School Bus',
                'amount': '9000.00',
            },
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)


class InvoiceGenerationTests(FinanceInvoicingTestCase):
    def test_generates_itemized_invoices_for_whole_class(self):
        from finance.models import Invoice, InvoiceLineItem

        self._make_fees()
        response = self._generate(self.admin)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created_count'], 3)
        self.assertEqual(response.data['skipped_count'], 0)

        self.assertEqual(Invoice.objects.count(), 3)
        self.assertEqual(InvoiceLineItem.objects.count(), 9)

        for invoice in Invoice.objects.all():
            # Decimal sum: 150000.00 + 5000.00 + 2500.50
            self.assertEqual(invoice.total_amount, Decimal('157500.50'))
            self.assertEqual(invoice.status, Invoice.Status.UNPAID)
            self.assertEqual(invoice.line_items.count(), 3)
            self.assertEqual(
                sum((li.amount for li in invoice.line_items.all()), Decimal('0.00')),
                invoice.total_amount,
            )

        # Response payload is itemized, and money is serialized as string.
        first = response.data['invoices'][0]
        self.assertEqual(first['total_amount'], '157500.50')
        self.assertEqual(first['status'], 'unpaid')
        self.assertEqual(len(first['line_items']), 3)
        names = {li['name'] for li in first['line_items']}
        self.assertEqual(names, {'Tuition', 'PTA Levy', 'Sports Fee'})

    def test_rerun_skips_existing_invoices_no_duplicates(self):
        from finance.models import Invoice

        self._make_fees()
        first = self._generate(self.admin)
        self.assertEqual(first.data['created_count'], 3)

        rerun = self._generate(self.admin)
        self.assertEqual(rerun.status_code, status.HTTP_200_OK)
        self.assertEqual(rerun.data['created_count'], 0)
        self.assertEqual(rerun.data['skipped_count'], 3)
        self.assertEqual(Invoice.objects.count(), 3)

    def test_rerun_only_creates_for_newly_enrolled_student(self):
        from datetime import date

        from academics.models import Enrollment, Student
        from finance.models import Invoice

        self._make_fees()
        self._generate(self.admin)

        late_student = Student.objects.create(
            first_name='Late',
            last_name='Enrollee',
            date_of_birth=date(2014, 6, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-999',
            admission_date=date(2026, 10, 1),
        )
        Enrollment.objects.create(
            student=late_student,
            class_level=self.class_level,
            arm=self.arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        rerun = self._generate(self.bursar)
        self.assertEqual(rerun.status_code, status.HTTP_201_CREATED)
        self.assertEqual(rerun.data['created_count'], 1)
        self.assertEqual(rerun.data['skipped_count'], 3)
        self.assertEqual(Invoice.objects.count(), 4)
        self.assertEqual(
            rerun.data['invoices'][0]['admission_number'], 'ADM-999'
        )

    def test_withdrawn_students_are_not_invoiced(self):
        from academics.models import Enrollment
        from finance.models import Invoice

        self._make_fees()
        withdrawn = self.students[2]
        Enrollment.objects.filter(student=withdrawn).update(
            status=Enrollment.Status.WITHDRAWN
        )

        response = self._generate(self.admin)
        self.assertEqual(response.data['created_count'], 2)
        self.assertFalse(Invoice.objects.filter(student=withdrawn).exists())

    def test_schoolwide_fee_is_its_own_invoice_in_every_class(self):
        from datetime import date

        from academics.models import Arm, Enrollment, Student
        from finance.models import FeeStructure, Invoice, InvoiceLineItem

        self._make_fees()
        FeeStructure.objects.create(
            class_level=None,
            term=self.term,
            name='School Bus',
            amount=Decimal('8000.00'),
        )
        jss2_arm = Arm.objects.create(class_level=self.other_class_level, name='A')
        jss2_student = Student.objects.create(
            first_name='Jss2',
            last_name='Pupil',
            date_of_birth=date(2014, 3, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-JSS2',
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=jss2_student,
            class_level=self.other_class_level,
            arm=jss2_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        first = self._generate(self.admin)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        # Three JSS1 students: one class invoice plus one bus invoice each.
        self.assertEqual(first.data['created_count'], 6)

        bus_invoices = Invoice.objects.filter(
            line_items__fee_structure__name='School Bus'
        )
        self.assertEqual(bus_invoices.count(), 3)
        for invoice in bus_invoices:
            self.assertEqual(invoice.total_amount, Decimal('8000.00'))
            self.assertEqual(invoice.line_items.count(), 1)

        class_invoices = Invoice.objects.filter(
            line_items__fee_structure__name='Tuition'
        )
        self.assertEqual(class_invoices.count(), 3)
        self.assertTrue(
            all(invoice.total_amount == Decimal('157500.50') for invoice in class_invoices)
        )

        second = self._generate(
            self.bursar, class_level=str(self.other_class_level.id)
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertEqual(second.data['created_count'], 1)
        self.assertEqual(
            InvoiceLineItem.objects.filter(
                fee_structure__name='School Bus',
                invoice__student=jss2_student,
            ).count(),
            1,
        )
        self.assertFalse(
            InvoiceLineItem.objects.filter(
                invoice__student=jss2_student,
                fee_structure__name='Tuition',
            ).exists()
        )

        rerun = self._generate(self.admin)
        self.assertEqual(rerun.status_code, status.HTTP_200_OK)
        self.assertEqual(rerun.data['created_count'], 0)
        self.assertEqual(rerun.data['skipped_count'], 3)

    def test_all_classes_bills_each_class_once_including_schoolwide(self):
        from datetime import date

        from academics.models import Arm, Enrollment, Student
        from finance.models import FeeStructure, Invoice, InvoiceLineItem

        self._make_fees()
        FeeStructure.objects.create(
            class_level=self.other_class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('1000.00'),
        )
        FeeStructure.objects.create(
            class_level=None,
            term=self.term,
            name='School Bus',
            amount=Decimal('8000.00'),
        )
        jss2_arm = Arm.objects.create(class_level=self.other_class_level, name='A')
        jss2_student = Student.objects.create(
            first_name='Jss2',
            last_name='Pupil',
            date_of_birth=date(2014, 3, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-JSS2',
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=jss2_student,
            class_level=self.other_class_level,
            arm=jss2_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        response = self._generate(self.admin, class_level=None)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # JSS1: class invoice + bus for 3 students. JSS2: tuition + bus for 1.
        self.assertEqual(response.data['created_count'], 8)
        self.assertEqual(response.data['skipped_count'], 0)
        self.assertEqual(
            InvoiceLineItem.objects.filter(fee_structure__name='School Bus').count(),
            4,
        )
        self.assertEqual(
            Invoice.objects.filter(
                student=jss2_student,
                line_items__fee_structure__name='Tuition',
            ).count(),
            1,
        )
        self.assertEqual(
            Invoice.objects.get(
                student=jss2_student,
                line_items__fee_structure__name='Tuition',
            ).total_amount,
            Decimal('1000.00'),
        )

        rerun = self._generate(self.bursar, class_level=None)
        self.assertEqual(rerun.status_code, status.HTTP_200_OK)
        self.assertEqual(rerun.data['created_count'], 0)
        self.assertEqual(rerun.data['skipped_count'], 4)
        self.assertEqual(Invoice.objects.count(), 8)

    def test_all_classes_skips_a_class_with_nothing_to_bill(self):
        from datetime import date

        from academics.models import Arm, Enrollment, Student
        from finance.models import Invoice

        self._make_fees()
        jss2_arm = Arm.objects.create(class_level=self.other_class_level, name='A')
        jss2_student = Student.objects.create(
            first_name='Jss2',
            last_name='Pupil',
            date_of_birth=date(2014, 3, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-JSS2',
            admission_date=date(2026, 9, 1),
        )
        Enrollment.objects.create(
            student=jss2_student,
            class_level=self.other_class_level,
            arm=jss2_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )

        response = self._generate(self.admin, class_level=None)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created_count'], 3)
        self.assertFalse(Invoice.objects.filter(student=jss2_student).exists())

    def test_all_classes_with_no_fees_is_a_400(self):
        from finance.models import Invoice

        response = self._generate(self.admin, class_level=None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_no_fee_structures_is_a_400_and_creates_nothing(self):
        from finance.models import Invoice

        response = self._generate(self.admin)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Invoice.objects.count(), 0)

    def test_teacher_and_parent_cannot_generate(self):
        self._make_fees()
        for user in (self.teacher, self.parent):
            response = self._generate(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )


class ParentInvoiceAccessTests(FinanceInvoicingTestCase):
    def test_parent_sees_only_linked_students_invoices_itemized(self):
        self._make_fees()
        self._generate(self.admin)

        self.api.force_authenticate(user=self.parent)
        response = self.api.get(MY_INVOICES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Linked to students[0] only — the other two invoices must not leak.
        self.assertEqual(response.data['count'], 1)
        invoice = response.data['results'][0]
        self.assertEqual(str(invoice['student']), str(self.students[0].id))
        self.assertEqual(invoice['total_amount'], '157500.50')
        self.assertEqual(invoice['amount_paid'], '0.00')
        self.assertEqual(invoice['outstanding_amount'], '157500.50')
        self.assertEqual(invoice['status'], 'unpaid')
        self.assertEqual(len(invoice['line_items']), 3)
        self.assertEqual(invoice['payments'], [])

    def test_unlinked_parent_gets_empty_list(self):
        self._make_fees()
        self._generate(self.admin)

        self.api.force_authenticate(user=self.other_parent)
        response = self.api.get(MY_INVOICES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_non_parent_roles_cannot_use_my_invoices(self):
        for user in (self.admin, self.bursar, self.teacher):
            self.api.force_authenticate(user=user)
            response = self.api.get(MY_INVOICES_URL)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_nested_payments_do_not_count_pending_as_paid(self):
        from finance.models import Invoice, Payment
        from finance.services import record_manual_payment

        self._make_fees()
        self._generate(self.admin)
        invoice = Invoice.objects.get(student=self.students[0])
        Payment.objects.create(
            invoice=invoice,
            amount=Decimal('157500.50'),
            reference='pay_parent_pending',
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        record_manual_payment(
            invoice=invoice,
            amount=Decimal('50000.00'),
            method='cash',
            recorded_by=self.bursar,
        )

        self.api.force_authenticate(user=self.parent)
        response = self.api.get(MY_INVOICES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = response.data['results'][0]
        self.assertEqual(row['status'], 'partially_paid')
        self.assertEqual(row['amount_paid'], '50000.00')
        self.assertEqual(row['outstanding_amount'], '107500.50')
        statuses = {p['status'] for p in row['payments']}
        self.assertEqual(statuses, {'pending', 'success'})
        pending = next(p for p in row['payments'] if p['status'] == 'pending')
        self.assertEqual(pending['gateway'], 'paystack')
        self.assertEqual(pending['amount'], '157500.50')
        self.assertIsNone(pending['paid_at'])
        success = next(p for p in row['payments'] if p['status'] == 'success')
        self.assertEqual(success['gateway'], 'manual')
        self.assertEqual(success['recorded_by_email'], self.bursar.email)


class StaffInvoiceListTests(FinanceInvoicingTestCase):
    """GET /api/finance/invoices/ — staff list for the current tenant schema."""

    def setUp(self):
        super().setUp()
        from datetime import date

        from academics.models import Arm, Enrollment, Student, Term
        from finance.models import FeeStructure, Invoice
        from finance.services import generate_invoices_for_class_term

        self._make_fees()
        self._generate(self.admin)

        self.second_term = Term.objects.create(
            session=self.session,
            name=Term.Name.SECOND,
            start_date=date(2027, 1, 11),
            end_date=date(2027, 4, 10),
            is_active=False,
        )
        self.second_term_invoice = Invoice.objects.create(
            student=self.students[0],
            term=self.second_term,
            total_amount=Decimal('1000.00'),
            status=Invoice.Status.UNPAID,
        )

        self.jss2_student = Student.objects.create(
            first_name='Jss2',
            last_name='Kid',
            date_of_birth=date(2013, 1, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-JSS2',
            admission_date=date(2026, 9, 1),
        )
        jss2_arm = Arm.objects.create(class_level=self.other_class_level, name='A')
        Enrollment.objects.create(
            student=self.jss2_student,
            class_level=self.other_class_level,
            arm=jss2_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )
        FeeStructure.objects.create(
            class_level=self.other_class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('100000.00'),
        )
        generate_invoices_for_class_term(
            class_level=self.other_class_level, term=self.term
        )

    def _list(self, user, **params):
        self.api.force_authenticate(user=user)
        return self.api.get(INVOICES_URL, params)

    def test_admin_and_bursar_see_tenant_invoices_with_balances(self):
        from finance.models import Invoice
        from finance.services import record_manual_payment

        first = self.students[0]
        record_manual_payment(
            invoice=Invoice.objects.get(student=first, term=self.term),
            amount=Decimal('50000.00'),
            method='cash',
            recorded_by=self.bursar,
        )

        for user in (self.admin, self.bursar):
            response = self._list(user)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(response.data['count'], 5)
            self.assertEqual(len(response.data['results']), 5)
            ids = {str(row['id']) for row in response.data['results']}
            self.assertIn(str(self.second_term_invoice.id), ids)
            paid = next(
                row
                for row in response.data['results']
                if str(row['student']) == str(first.id)
                and str(row['term']) == str(self.term.id)
            )
            self.assertEqual(paid['student_name'], 'Last0, First0')
            self.assertEqual(paid['admission_number'], 'ADM-000')
            self.assertEqual(paid['total_amount'], '157500.50')
            self.assertEqual(paid['amount_paid'], '50000.00')
            self.assertEqual(paid['outstanding_amount'], '107500.50')
            self.assertEqual(paid['status'], 'partially_paid')
            self.assertEqual(paid['term_name'], '1st')

    def test_parent_and_teacher_cannot_list(self):
        for user in (self.parent, self.teacher):
            response = self._list(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_filter_by_term_and_class_level(self):
        by_term = self._list(self.bursar, term=str(self.term.id))
        self.assertEqual(by_term.status_code, status.HTTP_200_OK, by_term.data)
        self.assertEqual(by_term.data['count'], 4)
        self.assertTrue(
            all(str(row['term']) == str(self.term.id) for row in by_term.data['results'])
        )

        second = self._list(self.admin, term=str(self.second_term.id))
        self.assertEqual(second.data['count'], 1)
        self.assertEqual(
            str(second.data['results'][0]['id']), str(self.second_term_invoice.id)
        )

        jss1 = self._list(self.bursar, class_level=str(self.class_level.id))
        self.assertEqual(jss1.data['count'], 3)
        self.assertNotIn(
            str(self.jss2_student.id),
            {str(row['student']) for row in jss1.data['results']},
        )

        jss2 = self._list(
            self.admin,
            term=str(self.term.id),
            class_level=str(self.other_class_level.id),
        )
        self.assertEqual(jss2.data['count'], 1)
        self.assertEqual(jss2.data['results'][0]['admission_number'], 'ADM-JSS2')
        self.assertEqual(jss2.data['results'][0]['total_amount'], '100000.00')

        empty = self._list(
            self.bursar,
            term=str(self.second_term.id),
            class_level=str(self.class_level.id),
        )
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertEqual(empty.data['count'], 0)

    def test_unknown_term_or_class_level_is_404(self):
        import uuid

        missing = str(uuid.uuid4())
        term = self._list(self.bursar, term=missing)
        self.assertEqual(term.status_code, status.HTTP_404_NOT_FOUND)
        klass = self._list(self.admin, class_level=missing)
        self.assertEqual(klass.status_code, status.HTTP_404_NOT_FOUND)


class StaffInvoiceRetrieveTests(FinanceInvoicingTestCase):
    """GET /api/finance/invoices/{id}/ — nested payments, SUCCESS-only balances."""

    def setUp(self):
        super().setUp()
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])

    def _get(self, user, pk=None):
        self.api.force_authenticate(user=user)
        invoice_id = pk or self.invoice.id
        return self.api.get(f'{INVOICES_URL}{invoice_id}/')

    def test_admin_and_bursar_retrieve_with_nested_payments(self):
        from finance.models import Payment
        from finance.services import record_manual_payment

        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('157500.50'),
            reference='pay_retrieve_pending',
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        record_manual_payment(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            method='cash',
            recorded_by=self.bursar,
            notes='Window cash',
        )

        for user in (self.admin, self.bursar):
            response = self._get(user)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(response.data['id'], str(self.invoice.id))
            self.assertEqual(response.data['student_name'], 'Last0, First0')
            self.assertEqual(response.data['admission_number'], 'ADM-000')
            self.assertEqual(response.data['total_amount'], '157500.50')
            self.assertEqual(response.data['amount_paid'], '50000.00')
            self.assertEqual(response.data['outstanding_amount'], '107500.50')
            self.assertEqual(response.data['status'], 'partially_paid')
            self.assertEqual(len(response.data['line_items']), 3)
            self.assertEqual(len(response.data['payments']), 2)
            by_status = {p['status']: p for p in response.data['payments']}
            self.assertEqual(by_status['pending']['gateway'], 'paystack')
            self.assertEqual(by_status['pending']['amount'], '157500.50')
            self.assertIsNone(by_status['pending']['paid_at'])
            self.assertEqual(by_status['pending']['initiated_by_email'], self.parent.email)
            self.assertEqual(by_status['success']['gateway'], 'manual')
            self.assertEqual(by_status['success']['method'], 'cash')
            self.assertEqual(by_status['success']['notes'], 'Window cash')
            self.assertEqual(by_status['success']['recorded_by_email'], self.bursar.email)
            self.assertIsNotNone(by_status['success']['paid_at'])

    def test_parent_and_teacher_cannot_retrieve(self):
        for user in (self.parent, self.teacher):
            response = self._get(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_unknown_invoice_is_404(self):
        import uuid

        response = self._get(self.bursar, pk=uuid.uuid4())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


PAYMENTS_URL = '/api/finance/payments/'


class StaffPaymentLedgerTests(FinanceInvoicingTestCase):
    """GET /api/finance/payments/ and retrieve — bursar ledger, read-only."""

    def setUp(self):
        super().setUp()
        from datetime import date

        from academics.models import Term
        from finance.models import Invoice, Payment
        from finance.services import record_manual_payment

        self._make_fees()
        self._generate(self.admin)
        self.invoice = Invoice.objects.get(student=self.students[0])
        self.other_invoice = Invoice.objects.get(student=self.students[1])

        self.pending = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('20000.00'),
            reference='pay_ledger_pending',
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        self.failed = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('10000.00'),
            reference='pay_ledger_failed',
            status=Payment.Status.FAILED,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        self.cash = record_manual_payment(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            method='cash',
            recorded_by=self.bursar,
        )
        self.other_cash = record_manual_payment(
            invoice=self.other_invoice,
            amount=Decimal('150000.00'),
            method='bank_transfer',
            recorded_by=self.admin,
        )

        self.second_term = Term.objects.create(
            session=self.session,
            name=Term.Name.SECOND,
            start_date=date(2027, 1, 11),
            end_date=date(2027, 4, 10),
            is_active=False,
        )
        self.second_invoice = Invoice.objects.create(
            student=self.students[0],
            term=self.second_term,
            total_amount=Decimal('1000.00'),
            status=Invoice.Status.UNPAID,
        )
        self.second_cash = record_manual_payment(
            invoice=self.second_invoice,
            amount=Decimal('1000.00'),
            method='cash',
            recorded_by=self.bursar,
        )

    def _list(self, user, **params):
        self.api.force_authenticate(user=user)
        return self.api.get(PAYMENTS_URL, params)

    def test_admin_and_bursar_see_ledger_rows(self):
        for user in (self.admin, self.bursar):
            response = self._list(user)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(response.data['count'], 5)
            self.assertEqual(len(response.data['results']), 5)
            by_ref = {row['reference']: row for row in response.data['results']}
            pending = by_ref['pay_ledger_pending']
            self.assertEqual(pending['status'], 'pending')
            self.assertEqual(pending['gateway'], 'paystack')
            self.assertEqual(pending['amount'], '20000.00')
            self.assertEqual(pending['student_name'], 'Last0, First0')
            self.assertEqual(pending['admission_number'], 'ADM-000')
            self.assertEqual(str(pending['invoice']), str(self.invoice.id))
            self.assertEqual(str(pending['student']), str(self.students[0].id))
            self.assertEqual(pending['initiated_by_email'], self.parent.email)
            self.assertIsNone(pending['recorded_by'])
            cash = by_ref[self.cash.reference]
            self.assertEqual(cash['status'], 'success')
            self.assertEqual(cash['gateway'], 'manual')
            self.assertEqual(cash['method'], 'cash')
            self.assertEqual(cash['recorded_by_email'], self.bursar.email)
            self.assertIsNotNone(cash['paid_at'])

    def test_filter_by_invoice_status_and_term(self):
        by_invoice = self._list(self.bursar, invoice=str(self.invoice.id))
        self.assertEqual(by_invoice.status_code, status.HTTP_200_OK, by_invoice.data)
        self.assertEqual(by_invoice.data['count'], 3)
        self.assertTrue(
            all(
                str(row['invoice']) == str(self.invoice.id)
                for row in by_invoice.data['results']
            )
        )

        success = self._list(self.admin, status='success')
        self.assertEqual(success.data['count'], 3)
        self.assertTrue(
            all(row['status'] == 'success' for row in success.data['results'])
        )

        pending = self._list(self.bursar, status='pending')
        self.assertEqual(pending.data['count'], 1)
        self.assertEqual(pending.data['results'][0]['reference'], 'pay_ledger_pending')

        by_term = self._list(self.admin, term=str(self.second_term.id))
        self.assertEqual(by_term.data['count'], 1)
        self.assertEqual(
            str(by_term.data['results'][0]['id']), str(self.second_cash.id)
        )

        combined = self._list(
            self.bursar,
            invoice=str(self.invoice.id),
            status='failed',
        )
        self.assertEqual(combined.data['count'], 1)
        self.assertEqual(combined.data['results'][0]['reference'], 'pay_ledger_failed')

    def test_unknown_invoice_or_term_is_404_invalid_status_is_400(self):
        import uuid

        missing = str(uuid.uuid4())
        invoice = self._list(self.bursar, invoice=missing)
        self.assertEqual(invoice.status_code, status.HTTP_404_NOT_FOUND)
        term = self._list(self.admin, term=missing)
        self.assertEqual(term.status_code, status.HTTP_404_NOT_FOUND)
        bad_status = self._list(self.bursar, status='paid')
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_one_payment(self):
        self.api.force_authenticate(user=self.bursar)
        response = self.api.get(f'{PAYMENTS_URL}{self.cash.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['id'], str(self.cash.id))
        self.assertEqual(response.data['amount'], '50000.00')
        self.assertEqual(response.data['gateway'], 'manual')
        self.assertEqual(response.data['student_name'], 'Last0, First0')
        self.assertEqual(response.data['recorded_by_email'], self.bursar.email)

    def test_successful_payment_cannot_be_deleted(self):
        self.api.force_authenticate(user=self.admin)
        listed = self.api.delete(PAYMENTS_URL)
        self.assertEqual(listed.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        detail = self.api.delete(f'{PAYMENTS_URL}{self.cash.id}/')
        self.assertEqual(detail.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        from finance.models import Payment

        self.assertTrue(Payment.objects.filter(pk=self.cash.id).exists())

    def test_parent_and_teacher_cannot_list_or_retrieve(self):
        for user in (self.parent, self.teacher):
            listed = self._list(user)
            self.assertEqual(
                listed.status_code, status.HTTP_403_FORBIDDEN, user.email
            )
            self.api.force_authenticate(user=user)
            detail = self.api.get(f'{PAYMENTS_URL}{self.cash.id}/')
            self.assertEqual(
                detail.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_unknown_payment_is_404(self):
        import uuid

        self.api.force_authenticate(user=self.bursar)
        response = self.api.get(f'{PAYMENTS_URL}{uuid.uuid4()}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Payment initialization (Prompt 3)
# ---------------------------------------------------------------------------

INIT_URL = '/api/finance/payments/initialize/'
VERIFY_URL = '/api/finance/payments/verify/'

INIT_OK = {
    'status': True,
    'message': 'Authorization URL created',
    'data': {
        'authorization_url': 'https://checkout.paystack.com/test_access_code',
        'access_code': 'test_access_code',
        'reference': 'pay_echoed_by_paystack',
    },
}


class NairaToKoboTests(SimpleTestCase):
    """Gateway-boundary conversion — no DB. Decimal only, never float."""

    def test_known_naira_to_kobo(self):
        from finance.paystack import kobo_to_naira, naira_to_kobo

        self.assertEqual(naira_to_kobo(Decimal('157500.50')), 15750050)
        self.assertEqual(naira_to_kobo(Decimal('150000.00')), 15000000)
        self.assertEqual(naira_to_kobo(Decimal('1.00')), 100)
        self.assertEqual(naira_to_kobo(Decimal('0.01')), 1)
        self.assertEqual(kobo_to_naira(15750050), Decimal('157500.50'))
        self.assertEqual(kobo_to_naira(100), Decimal('1.00'))

    def test_initialize_payload_amount_is_integer_kobo(self):
        from finance.paystack import build_initialize_payload

        payload = build_initialize_payload(
            email='parent@example.com',
            amount_naira=Decimal('157500.50'),
            reference='pay_abc123',
            subaccount='ACCT_testsubacct123',
            metadata={'invoice_id': 'inv-1'},
        )
        self.assertEqual(
            payload,
            {
                'email': 'parent@example.com',
                'amount': 15750050,
                'currency': 'NGN',
                'reference': 'pay_abc123',
                'subaccount': 'ACCT_testsubacct123',
                'metadata': {'invoice_id': 'inv-1'},
            },
        )
        self.assertIsInstance(payload['amount'], int)


class InvoiceStatusFromPaymentsTests(FinanceInvoicingTestCase):
    """
    Partial-payment decision is encoded here: cumulative SUCCESS payments
    drive unpaid → partially_paid → paid. Pending payments do not count.
    """

    def test_recompute_unpaid_partial_then_paid(self):
        from finance.models import Invoice, Payment
        from finance.services import recompute_invoice_payment_status

        self._make_fees()
        self._generate(self.admin)
        invoice = Invoice.objects.get(student=self.students[0])
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)

        recompute_invoice_payment_status(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)

        Payment.objects.create(
            invoice=invoice,
            amount=Decimal('50000.00'),
            reference='pay_partial_1',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        recompute_invoice_payment_status(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)

        Payment.objects.create(
            invoice=invoice,
            amount=Decimal('107500.50'),
            reference='pay_rest_1',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        recompute_invoice_payment_status(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_pending_payment_does_not_change_invoice_status(self):
        from finance.models import Invoice, Payment
        from finance.services import recompute_invoice_payment_status

        self._make_fees()
        self._generate(self.admin)
        invoice = Invoice.objects.get(student=self.students[0])
        Payment.objects.create(
            invoice=invoice,
            amount=Decimal('157500.50'),
            reference='pay_pending_only',
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        recompute_invoice_payment_status(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)


class InitializePaymentTests(FinanceInvoicingTestCase):
    def setUp(self):
        super().setUp()
        overrides = override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy')
        overrides.enable()
        self.addCleanup(overrides.disable)
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])
        self.other_invoice = Invoice.objects.get(student=self.students[1])

    def _activate_paystack(self, *, is_verified=True, is_active=True):
        return SchoolPaymentAccount.objects.create(
            gateway=SchoolPaymentAccount.Gateway.PAYSTACK,
            subaccount_code='ACCT_testsubacct123',
            bank_name='Zenith Bank',
            bank_code='057',
            account_number='0000000000',
            account_name='PAYSTACK TEST ACCOUNT',
            platform_commission_pct=Decimal('5.00'),
            is_verified=is_verified,
            is_active=is_active,
            created_by=self.admin,
        )

    def _init(self, user, invoice=None, **payload_extra):
        self.api.force_authenticate(user=user)
        payload = {'invoice': str((invoice or self.invoice).id)}
        payload.update(payload_extra)
        return self.api.post(INIT_URL, payload, format='json')

    def test_parent_initialize_sends_kobo_and_subaccount_keeps_pending(self):
        from finance.models import Invoice, Payment
        from finance.paystack import naira_to_kobo

        self._activate_paystack()
        self.api.force_authenticate(user=self.parent)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ) as http:
            response = self._init(self.parent)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            response.data['authorization_url'],
            'https://checkout.paystack.com/test_access_code',
        )
        self.assertEqual(response.data['access_code'], 'test_access_code')
        self.assertEqual(response.data['amount'], '157500.50')
        self.assertEqual(response.data['payment_status'], 'pending')
        self.assertEqual(response.data['invoice_status'], 'unpaid')

        http.assert_called_once()
        method, url = http.call_args.args
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://api.paystack.co/transaction/initialize')
        sent = http.call_args.kwargs['json']
        payment = Payment.objects.get()
        self.assertEqual(
            sent,
            {
                'email': self.parent.email,
                'amount': 15750050,
                'currency': 'NGN',
                'reference': payment.reference,
                'subaccount': 'ACCT_testsubacct123',
                'metadata': {
                    'invoice_id': str(self.invoice.id),
                    'student_id': str(self.students[0].id),
                },
            },
        )
        self.assertEqual(sent['amount'], naira_to_kobo(Decimal('157500.50')))
        self.assertIsInstance(sent['amount'], int)
        self.assertTrue(payment.reference.startswith('pay_'))
        self.assertRegex(payment.reference, r'^[A-Za-z0-9\-._=]+$')
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.gateway, Payment.Gateway.PAYSTACK)
        self.assertIsNone(payment.paid_at)
        self.assertEqual(payment.initiated_by, self.parent)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)
        self.assertEqual(Invoice.objects.filter(status=Invoice.Status.PAID).count(), 0)

    def test_partial_amount_allowed_still_does_not_mark_paid(self):
        from finance.models import Invoice, Payment

        self._activate_paystack()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ) as http:
            response = self._init(self.parent, amount='50000.00')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '50000.00')
        self.assertEqual(response.data['invoice_status'], 'unpaid')
        sent = http.call_args.kwargs['json']
        self.assertEqual(sent['amount'], 5000000)  # ₦50,000.00 → 5,000,000 kobo
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal('50000.00'))
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)

    def test_amount_above_outstanding_rejected(self):
        self._activate_paystack()
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.parent, amount='157500.51')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        http.assert_not_called()

    def test_omitted_amount_defaults_to_remaining_outstanding(self):
        from finance.models import Payment

        self._activate_paystack()
        # A prior SUCCESS installment of 50,000 — outstanding 107500.50
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            reference='pay_already_success',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        from finance.services import recompute_invoice_payment_status

        recompute_invoice_payment_status(self.invoice)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ) as http:
            response = self._init(self.parent)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '107500.50')
        sent = http.call_args.kwargs['json']
        self.assertEqual(sent['amount'], 10750050)

    def test_blocked_without_active_payment_account(self):
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.parent)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        http.assert_not_called()
        from finance.models import Payment

        self.assertEqual(Payment.objects.count(), 0)

    def test_blocked_when_account_inactive_or_unverified(self):
        self._activate_paystack(is_verified=True, is_active=False)
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.parent)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        http.assert_not_called()

    def test_already_paid_invoice_rejected(self):
        from finance.models import Invoice, Payment
        from finance.services import recompute_invoice_payment_status

        self._activate_paystack()
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('157500.50'),
            reference='pay_full_success',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        recompute_invoice_payment_status(self.invoice)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.parent)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        http.assert_not_called()

    def test_unlinked_parent_gets_404_not_the_invoice(self):
        self._activate_paystack()
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.other_parent, invoice=self.invoice)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        http.assert_not_called()

    def test_parent_cannot_pay_unlinked_students_invoice(self):
        self._activate_paystack()
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._init(self.parent, invoice=self.other_invoice)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        http.assert_not_called()

    def test_non_parent_roles_cannot_initialize(self):
        self._activate_paystack()
        for user in (self.admin, self.bursar, self.teacher):
            with mock.patch('finance.paystack.requests.request') as http:
                response = self._init(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )
            http.assert_not_called()

    def test_gateway_5xx_marks_payment_failed_and_returns_502(self):
        from finance.models import Payment

        self._activate_paystack()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response({'status': False, 'message': 'oops'}, 500),
        ):
            response = self._init(self.parent)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'unpaid')

    def test_retry_supersedes_pending_checkout(self):
        from finance.models import Payment

        self._activate_paystack()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ):
            first = self._init(self.parent, amount='20000.00')
            second = self._init(self.parent, amount='30000.00')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        first_ref = first.data['reference']
        second_ref = second.data['reference']
        self.assertNotEqual(first_ref, second_ref)
        self.assertEqual(
            Payment.objects.get(reference=first_ref).status,
            Payment.Status.FAILED,
        )
        self.assertEqual(
            Payment.objects.get(reference=second_ref).status,
            Payment.Status.PENDING,
        )
        self.assertEqual(Payment.objects.filter(status=Payment.Status.PENDING).count(), 1)

    def test_unlinked_invoice_in_a_bundle_is_404_and_creates_nothing(self):
        from finance.models import Payment, PaymentCheckout

        self._activate_paystack()
        self.api.force_authenticate(user=self.parent)
        with mock.patch('finance.paystack.requests.request') as http:
            response = self.api.post(
                INIT_URL,
                {
                    'invoices': [
                        str(self.invoice.id),
                        str(self.other_invoice.id),
                    ]
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        http.assert_not_called()
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(PaymentCheckout.objects.count(), 0)

    def test_two_students_pay_in_one_paystack_charge(self):
        from academics.models import Guardian, StudentGuardianLink
        from finance.models import Invoice, Payment, PaymentCheckout
        from finance.paystack import naira_to_kobo
        from finance.services import verify_and_apply_payment

        guardian = Guardian.objects.get(user=self.parent)
        StudentGuardianLink.objects.create(
            student=self.students[1],
            guardian=guardian,
            is_primary_contact=False,
        )
        self._activate_paystack()
        self.api.force_authenticate(user=self.parent)
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ) as http:
            response = self.api.post(
                INIT_URL,
                {
                    'invoices': [
                        str(self.invoice.id),
                        str(self.other_invoice.id),
                    ]
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '315001.00')
        self.assertEqual(response.data['payment_status'], 'pending')
        sent = http.call_args.kwargs['json']
        checkout = PaymentCheckout.objects.get()
        self.assertEqual(sent['reference'], checkout.reference)
        self.assertEqual(sent['amount'], naira_to_kobo(Decimal('315001.00')))
        self.assertEqual(checkout.amount, Decimal('315001.00'))
        self.assertEqual(Payment.objects.filter(checkout=checkout).count(), 2)
        self.invoice.refresh_from_db()
        self.other_invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)
        self.assertEqual(self.other_invoice.status, Invoice.Status.UNPAID)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(checkout.reference, checkout.amount)
            ),
        ):
            verify_and_apply_payment(checkout.reference)
        self.invoice.refresh_from_db()
        self.other_invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.other_invoice.status, Invoice.Status.PAID)
        self.assertEqual(
            Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 2
        )

        with mock.patch('finance.paystack.requests.request') as http:
            verify_and_apply_payment(checkout.reference)
        http.assert_not_called()
        logs = _platform_txn_logs(self.tenant)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].payment_reference, checkout.reference)
        self.assertEqual(logs[0].gross_amount, Decimal('315001.00'))

    def test_one_student_two_terms_pay_together(self):
        from datetime import date

        from academics.models import Enrollment, Term
        from finance.models import FeeStructure, Invoice, PaymentCheckout

        second_term = Term.objects.create(
            session=self.session,
            name=Term.Name.SECOND,
            start_date=date(2027, 1, 11),
            end_date=date(2027, 4, 2),
            is_active=False,
        )
        Enrollment.objects.create(
            student=self.students[0],
            class_level=self.class_level,
            arm=self.arm,
            session=self.session,
            term=second_term,
            status=Enrollment.Status.ACTIVE,
        )
        FeeStructure.objects.create(
            class_level=self.class_level,
            term=second_term,
            name='Tuition',
            amount=Decimal('1000.00'),
        )
        generated = self._generate(
            self.admin,
            term=str(second_term.id),
        )
        self.assertEqual(generated.status_code, status.HTTP_201_CREATED, generated.data)
        second_invoice = Invoice.objects.get(student=self.students[0], term=second_term)

        self._activate_paystack()
        self.api.force_authenticate(user=self.parent)
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(INIT_OK),
        ) as http:
            response = self.api.post(
                INIT_URL,
                {'invoices': [str(self.invoice.id), str(second_invoice.id)]},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '158500.50')
        sent = http.call_args.kwargs['json']
        checkout = PaymentCheckout.objects.get()
        self.assertEqual(sent['reference'], checkout.reference)
        self.assertEqual(sent['amount'], 15850050)


# ---------------------------------------------------------------------------
# Server-side verification (Prompt 4)
# ---------------------------------------------------------------------------


def _verify_payload(reference, amount_naira, txn_status='success'):
    from finance.paystack import naira_to_kobo

    return {
        'status': True,
        'message': 'Verification successful',
        'data': {
            'id': 424242,
            'status': txn_status,
            'reference': reference,
            'amount': naira_to_kobo(amount_naira),
            'currency': 'NGN',
            'paid_at': '2026-08-26T12:00:00.000Z',
            'gateway_response': 'Successful' if txn_status == 'success' else 'Declined',
            'channel': 'card',
        },
    }


class VerifyAndApplyPaymentTests(FinanceInvoicingTestCase):
    """
    Shared service + return-flow endpoint. Prompt 5's webhook is NOT
    implemented here; it must call the same ``verify_and_apply_payment``.
    """

    def setUp(self):
        super().setUp()
        overrides = override_settings(PAYSTACK_SECRET_KEY='sk_test_dummy')
        overrides.enable()
        self.addCleanup(overrides.disable)
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])
        self.other_invoice = Invoice.objects.get(student=self.students[1])

    def _pending(self, *, invoice=None, amount=None, reference='pay_verify_ref'):
        from finance.models import Payment

        return Payment.objects.create(
            invoice=invoice or self.invoice,
            amount=amount if amount is not None else Decimal('157500.50'),
            reference=reference,
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )

    def _verify(self, user, reference):
        self.api.force_authenticate(user=user)
        return self.api.post(VERIFY_URL, {'reference': reference}, format='json')

    def test_full_success_marks_payment_and_invoice_paid(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total, verify_and_apply_payment

        payment = self._pending()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(_verify_payload(payment.reference, payment.amount)),
        ) as http:
            result = verify_and_apply_payment(payment.reference)

        method, url = http.call_args.args
        self.assertEqual(method, 'GET')
        self.assertEqual(
            url,
            f'https://api.paystack.co/transaction/verify/{payment.reference}',
        )
        self.assertEqual(result.status, Payment.Status.SUCCESS)
        self.assertIsNotNone(result.paid_at)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))

    def test_partial_success_marks_invoice_partially_paid(self):
        from finance.models import Invoice, Payment
        from finance.services import verify_and_apply_payment

        payment = self._pending(amount=Decimal('50000.00'))
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(_verify_payload(payment.reference, payment.amount)),
        ):
            verify_and_apply_payment(payment.reference)

        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

    def test_idempotent_success_does_not_double_count(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total, verify_and_apply_payment

        payment = self._pending()
        payload = _verify_payload(payment.reference, payment.amount)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ) as http:
            first = verify_and_apply_payment(payment.reference)
        http.assert_called_once()

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ) as http:
            second = verify_and_apply_payment(payment.reference)
        http.assert_not_called()

        self.assertEqual(first.id, second.id)
        self.assertEqual(Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 1)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))

    def test_amount_mismatch_does_not_credit(self):
        from finance.models import Invoice, Payment
        from finance.services import PaymentAmountMismatch, verify_and_apply_payment

        payment = self._pending(amount=Decimal('157500.50'))
        # Gateway reports a smaller charge than the stored Payment.
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(payment.reference, Decimal('1000.00'))
            ),
        ):
            with self.assertRaises(PaymentAmountMismatch):
                verify_and_apply_payment(payment.reference)

        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertIsNone(payment.paid_at)
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)
        self.assertEqual(
            Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 0
        )

    def test_gateway_failed_status_marks_payment_failed(self):
        from finance.models import Invoice, Payment
        from finance.services import verify_and_apply_payment

        payment = self._pending()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(payment.reference, payment.amount, txn_status='failed')
            ),
        ):
            result = verify_and_apply_payment(payment.reference)

        self.assertEqual(result.status, Payment.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)

    def test_unknown_reference_raises(self):
        from finance.models import Payment
        from finance.services import verify_and_apply_payment

        with self.assertRaises(Payment.DoesNotExist):
            verify_and_apply_payment('pay_does_not_exist')

    def test_endpoint_calls_the_shared_service(self):
        from finance.models import Invoice, Payment
        from finance.services import verify_and_apply_payment

        payment = self._pending()
        payload = _verify_payload(payment.reference, payment.amount)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            with mock.patch(
                'finance.views.verify_and_apply_payment',
                wraps=verify_and_apply_payment,
            ) as apply_fn:
                response = self._verify(self.parent, payment.reference)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        apply_fn.assert_called_once_with(payment.reference)
        self.assertEqual(response.data['payment_status'], 'success')
        self.assertEqual(response.data['invoice_status'], 'paid')
        self.assertEqual(response.data['amount'], '157500.50')
        self.assertEqual(response.data['reference'], payment.reference)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_endpoint_idempotent_when_already_success(self):
        from finance.models import Payment
        from finance.services import successful_paid_total

        payment = self._pending()
        payload = _verify_payload(payment.reference, payment.amount)
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            first = self._verify(self.parent, payment.reference)
            second = self._verify(self.parent, payment.reference)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data['payment_status'], 'success')
        self.assertEqual(Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 1)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))

    def test_unlinked_parent_gets_404_and_does_not_apply(self):
        from finance.models import Payment

        payment = self._pending()
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._verify(self.other_parent, payment.reference)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        http.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_unknown_reference_is_404(self):
        self.api.force_authenticate(user=self.parent)
        with mock.patch('finance.paystack.requests.request') as http:
            response = self._verify(self.parent, 'pay_missing')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        http.assert_not_called()

    def test_non_parent_roles_cannot_verify(self):
        payment = self._pending()
        for user in (self.admin, self.bursar, self.teacher):
            with mock.patch('finance.paystack.requests.request') as http:
                response = self._verify(user, payment.reference)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )
            http.assert_not_called()

    def test_amount_mismatch_via_endpoint_is_400(self):
        from finance.models import Invoice, Payment

        payment = self._pending()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(payment.reference, Decimal('1.00'))
            ),
        ):
            response = self._verify(self.parent, payment.reference)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)

    def test_gateway_unreachable_is_502_leaves_pending(self):
        from finance.models import Payment

        payment = self._pending()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response({'status': False, 'message': 'oops'}, 500),
        ):
            response = self._verify(self.parent, payment.reference)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'unpaid')

    def test_exactly_one_apply_function_exists(self):
        import finance.services as services

        apply_fns = [
            name
            for name in dir(services)
            if 'apply' in name.lower()
            and not name.startswith('_')
            and callable(getattr(services, name))
        ]
        self.assertEqual(apply_fns, ['verify_and_apply_payment'])


# ---------------------------------------------------------------------------
# Multi-tenant webhook (Prompt 5)
# ---------------------------------------------------------------------------

WEBHOOK_URL = '/api/webhooks/paystack/'
WEBHOOK_SECRET = 'sk_test_dummy'


def _sign_body(body: bytes, secret=WEBHOOK_SECRET):
    import hashlib
    import hmac

    return hmac.new(secret.encode('utf-8'), body, hashlib.sha512).hexdigest()


def _charge_success_body(*, reference, subaccount_code='ACCT_testsubacct123', extra=None):
    import json

    payload = {
        'event': 'charge.success',
        'data': {
            'id': 424242,
            'status': 'success',
            'reference': reference,
            'amount': 15750050,
            'currency': 'NGN',
            'subaccount': {'subaccount_code': subaccount_code},
        },
    }
    if extra:
        payload['data'].update(extra)
    return json.dumps(payload, separators=(',', ':')).encode('utf-8')


class VerifyWebhookSignatureTests(SimpleTestCase):
    def test_valid_signature_matches_raw_bytes(self):
        from django.test import override_settings
        from finance.paystack import verify_webhook_signature

        body = b'{"event":"charge.success"}'
        with override_settings(PAYSTACK_SECRET_KEY=WEBHOOK_SECRET):
            self.assertTrue(
                verify_webhook_signature(body, _sign_body(body))
            )

    def test_tampered_body_is_rejected(self):
        from django.test import override_settings
        from finance.paystack import verify_webhook_signature

        body = b'{"event":"charge.success"}'
        sig = _sign_body(body)
        with override_settings(PAYSTACK_SECRET_KEY=WEBHOOK_SECRET):
            self.assertFalse(verify_webhook_signature(body + b' ', sig))
            self.assertFalse(verify_webhook_signature(body, 'deadbeef'))
            self.assertFalse(verify_webhook_signature(body, ''))
            self.assertFalse(verify_webhook_signature('not-bytes', sig))

    def test_empty_secret_fails_closed(self):
        from django.test import override_settings
        from finance.paystack import verify_webhook_signature

        body = b'{}'
        with override_settings(PAYSTACK_SECRET_KEY=''):
            self.assertFalse(verify_webhook_signature(body, _sign_body(body, '')))


class PaystackWebhookTests(FinanceInvoicingTestCase):
    """
    Global webhook on the single API host. HMAC on raw bytes BEFORE JSON.
    Tenant comes from SubaccountTenantMap, not Host or X-Tenant-Slug.
    """

    def setUp(self):
        super().setUp()
        overrides = override_settings(PAYSTACK_SECRET_KEY=WEBHOOK_SECRET)
        overrides.enable()
        self.addCleanup(overrides.disable)
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])
        self.public_client = APIClient()

    def _pending(self, *, reference='pay_wh_ref', amount=None):
        from finance.models import Payment

        return Payment.objects.create(
            invoice=self.invoice,
            amount=amount if amount is not None else Decimal('157500.50'),
            reference=reference,
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )

    def _map_subaccount(self, code='ACCT_testsubacct123'):
        from django.db import connection
        from platform_admin.models import SubaccountTenantMap

        SubaccountTenantMap.upsert(code, self.tenant)
        connection.set_tenant(self.tenant)

    def _post_webhook(self, body, signature=None, host='localhost'):
        from django.db import connection

        headers = {}
        if signature is not None:
            headers['HTTP_X_PAYSTACK_SIGNATURE'] = signature
        response = self.public_client.post(
            WEBHOOK_URL,
            data=body,
            content_type='application/json',
            **headers,
        )
        connection.set_tenant(self.tenant)
        return response

    def _logs(self):
        from django.db import connection
        from django_tenants.utils import get_public_schema_name, schema_context
        from platform_admin.models import WebhookLog

        with schema_context(get_public_schema_name()):
            rows = list(WebhookLog.objects.order_by('received_at'))
        connection.set_tenant(self.tenant)
        return rows

    def test_invalid_signature_rejected_and_logged_without_apply(self):
        from finance.models import Payment

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)

        with mock.patch('finance.webhooks.verify_and_apply_payment') as apply_fn:
            response = self._post_webhook(body, signature='not-a-valid-hmac')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        apply_fn.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'unpaid')

        logs = self._logs()
        self.assertEqual(len(logs), 1)
        self.assertFalse(logs[0].signature_valid)
        self.assertEqual(logs[0].outcome, 'signature_invalid')

    def test_missing_signature_rejected(self):
        from finance.models import Payment

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)
        with mock.patch('finance.webhooks.verify_and_apply_payment') as apply_fn:
            response = self._post_webhook(body, signature=None)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        apply_fn.assert_not_called()

    def test_unknown_subaccount_rejected_and_logged(self):
        from finance.models import Payment

        payment = self._pending()
        body = _charge_success_body(
            reference=payment.reference, subaccount_code='ACCT_unknown'
        )
        with mock.patch(
            'finance.paystack.requests.request'
        ) as http, mock.patch(
            'finance.webhooks.verify_and_apply_payment'
        ) as apply_fn:
            response = self._post_webhook(body, signature=_sign_body(body))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        apply_fn.assert_not_called()
        http.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

        logs = self._logs()
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].signature_valid)
        self.assertEqual(logs[0].outcome, 'unknown_subaccount')
        self.assertEqual(logs[0].subaccount_code, 'ACCT_unknown')

    def test_charge_success_applies_via_shared_function(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total, verify_and_apply_payment

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)
        payload = _verify_payload(payment.reference, payment.amount)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            with mock.patch(
                'finance.webhooks.verify_and_apply_payment',
                wraps=verify_and_apply_payment,
            ) as apply_fn:
                response = self._post_webhook(body, signature=_sign_body(body))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        apply_fn.assert_called_once_with(payment.reference)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))

        logs = self._logs()
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].signature_valid)
        self.assertEqual(logs[0].outcome, 'applied')
        self.assertEqual(logs[0].reference, payment.reference)
        self.assertEqual(logs[0].tenant_id, self.tenant.id)

    def test_duplicate_webhook_same_reference_is_idempotent(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)
        payload = _verify_payload(payment.reference, payment.amount)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ) as http:
            first = self._post_webhook(body, signature=_sign_body(body))
            second = self._post_webhook(body, signature=_sign_body(body))

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 1)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))
        # First delivery verifies at Paystack; second is a SUCCESS short-circuit.
        self.assertEqual(http.call_count, 1)

        logs = self._logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual({row.outcome for row in logs}, {'applied'})

    def test_hmac_runs_on_request_body_before_json_parse(self):
        import inspect

        import finance.webhooks as wh

        src = inspect.getsource(inspect.unwrap(wh.paystack_webhook))
        body_pos = src.find('request.body')
        hmac_pos = src.find('verify_webhook_signature')
        parse_pos = src.find('json.loads')
        self.assertGreaterEqual(body_pos, 0)
        self.assertGreater(hmac_pos, body_pos)
        self.assertGreater(parse_pos, hmac_pos)
        # Must not parse JSON (or touch payload fields) before HMAC.
        self.assertNotIn('request.data', src)

    def test_webhook_does_not_duplicate_apply_logic(self):
        import inspect

        import finance.webhooks as wh

        src = inspect.getsource(wh)
        self.assertIn('verify_and_apply_payment', src)
        self.assertNotIn('recompute_invoice_payment_status', src)
        self.assertNotIn('verify_transaction', src)
        self.assertNotIn('PaymentAmountMismatch', src)

    def test_webhook_ignores_host_and_tenant_slug(self):
        """Single API host: tenant comes from subaccount map, not Host/header."""
        from django.db import connection
        from finance.models import Payment

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)
        payload = _verify_payload(payment.reference, payment.amount)
        tenant_host = self.tenant.domains.first().domain

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            response = self.api.post(
                WEBHOOK_URL,
                data=body,
                content_type='application/json',
                HTTP_HOST=tenant_host,
                HTTP_X_TENANT_SLUG=self.tenant.schema_name,
                HTTP_X_PAYSTACK_SIGNATURE=_sign_body(body),
            )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

    def test_csrf_exempt_on_api_host(self):
        from django.db import connection
        from django.test import Client
        from finance.models import Payment

        payment = self._pending()
        self._map_subaccount()
        body = _charge_success_body(reference=payment.reference)
        payload = _verify_payload(payment.reference, payment.amount)
        client = Client(enforce_csrf_checks=True)

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            response = client.post(
                WEBHOOK_URL,
                data=body,
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE=_sign_body(body),
            )
        connection.set_tenant(self.tenant)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

    def test_non_charge_success_is_acked_without_apply(self):
        import json

        self._map_subaccount()
        payload = {
            'event': 'charge.failed',
            'data': {
                'reference': 'pay_failed',
                'subaccount': {'subaccount_code': 'ACCT_testsubacct123'},
            },
        }
        body = json.dumps(payload).encode('utf-8')
        with mock.patch('finance.webhooks.verify_and_apply_payment') as apply_fn:
            response = self._post_webhook(body, signature=_sign_body(body))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        apply_fn.assert_not_called()
        logs = self._logs()
        self.assertEqual(logs[0].outcome, 'ignored_event')


# ---------------------------------------------------------------------------
# Manual payment recording (Prompt 6)
# ---------------------------------------------------------------------------

MANUAL_URL = '/api/finance/payments/manual/'


class RecordManualPaymentTests(FinanceInvoicingTestCase):
    """
    Bursar/admin cash and bank-transfer recording. Not a Paystack verify —
    SUCCESS is written directly, invoice status via the shared recompute.
    """

    def setUp(self):
        super().setUp()
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])
        self.other_invoice = Invoice.objects.get(student=self.students[1])

    def _record(self, user, invoice=None, **payload_extra):
        self.api.force_authenticate(user=user)
        payload = {
            'invoice': str((invoice or self.invoice).id),
            'amount': '157500.50',
            'method': 'cash',
        }
        payload.update(payload_extra)
        return self.api.post(MANUAL_URL, payload, format='json')

    def test_bursar_full_cash_marks_payment_success_and_invoice_paid(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total

        # No SchoolPaymentAccount — manual is the fallback, not blocked.
        response = self._record(
            self.bursar, notes='Cash counted at the window, 26 Aug 2026.'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['payment_status'], 'success')
        self.assertEqual(response.data['gateway'], 'manual')
        self.assertEqual(response.data['method'], 'cash')
        self.assertEqual(response.data['amount'], '157500.50')
        self.assertEqual(response.data['invoice_status'], 'paid')
        self.assertEqual(response.data['recorded_by'], str(self.bursar.id))
        self.assertTrue(response.data['reference'].startswith('manual-'))
        self.assertEqual(
            response.data['notes'], 'Cash counted at the window, 26 Aug 2026.'
        )

        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(payment.gateway, Payment.Gateway.MANUAL)
        self.assertEqual(payment.method, Payment.Method.CASH)
        self.assertIsNone(payment.initiated_by)
        self.assertEqual(payment.recorded_by, self.bursar)
        self.assertIsNotNone(payment.paid_at)
        self.assertTrue(payment.reference.startswith('manual-'))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))

    def test_partial_then_remainder_uses_same_status_writer(self):
        from finance.models import Invoice, Payment
        from finance.services import successful_paid_total

        first = self._record(self.bursar, amount='50000.00', method='cash')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(first.data['invoice_status'], 'partially_paid')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

        second = self._record(
            self.admin, amount='107500.50', method='bank_transfer', notes='GTBank teller'
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertEqual(second.data['invoice_status'], 'paid')
        self.assertEqual(second.data['method'], 'bank_transfer')
        self.assertEqual(second.data['recorded_by'], str(self.admin.id))

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(successful_paid_total(self.invoice), Decimal('157500.50'))
        self.assertEqual(Payment.objects.filter(gateway=Payment.Gateway.MANUAL).count(), 2)
        refs = list(Payment.objects.values_list('reference', flat=True))
        self.assertEqual(len(refs), len(set(refs)))
        self.assertTrue(all(r.startswith('manual-') for r in refs))

    def test_paystack_installment_then_manual_remainder(self):
        """Cumulative SUCCESS total is gateway-agnostic; recompute is shared."""
        from finance.models import Invoice, Payment
        from finance.services import recompute_invoice_payment_status

        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            reference='pay_already_online',
            status=Payment.Status.SUCCESS,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )
        recompute_invoice_payment_status(self.invoice)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

        response = self._record(self.bursar, amount='107500.50', method='cash')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['invoice_status'], 'paid')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_amount_above_outstanding_rejected(self):
        from finance.models import Invoice, Payment

        response = self._record(self.bursar, amount='157500.51')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.UNPAID)

    def test_already_paid_invoice_rejected(self):
        from finance.models import Payment

        first = self._record(self.bursar)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        second = self._record(self.bursar, amount='0.01')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 1)

    def test_invalid_method_rejected(self):
        response = self._record(self.bursar, method='pos')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_and_teacher_cannot_record(self):
        for user in (self.parent, self.teacher):
            response = self._record(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_endpoint_calls_record_manual_payment_not_verify(self):
        from finance.services import record_manual_payment

        with mock.patch(
            'finance.views.record_manual_payment',
            wraps=record_manual_payment,
        ) as record_fn, mock.patch(
            'finance.views.verify_and_apply_payment'
        ) as verify_fn:
            response = self._record(self.bursar, amount='50000.00')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        record_fn.assert_called_once()
        verify_fn.assert_not_called()

    def test_manual_recording_reuses_invoice_status_writer_not_verify(self):
        import inspect

        from finance import services

        src = inspect.getsource(services.record_manual_payment)
        self.assertIn('recompute_invoice_payment_status', src)
        self.assertNotIn('verify_and_apply_payment', src)
        self.assertNotIn('verify_transaction', src)
        self.assertNotIn('naira_to_kobo', src)

        from finance.views import RecordManualPaymentView

        view_src = inspect.getsource(RecordManualPaymentView)
        self.assertIn('record_manual_payment', view_src)
        self.assertNotIn('verify_and_apply_payment', view_src)
        self.assertNotIn('recompute_invoice_payment_status', view_src)

    def test_manual_recording_does_not_write_platform_transaction_log(self):
        response = self._record(self.bursar)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(_platform_txn_logs(self.tenant), [])


# ---------------------------------------------------------------------------
# Platform commission log + school collection dashboard (Prompt 7)
# ---------------------------------------------------------------------------

COLLECTIONS_URL = '/api/finance/dashboard/collections/'


def _platform_txn_logs(tenant):
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, schema_context
    from platform_admin.models import PlatformTransactionLog

    with schema_context(get_public_schema_name()):
        rows = list(
            PlatformTransactionLog.objects.filter(tenant_id=tenant.id).order_by(
                'timestamp', 'payment_reference'
            )
        )
    connection.set_tenant(tenant)
    return rows


class PlatformTransactionLogOnPaystackSuccessTests(FinanceInvoicingTestCase):
    """
    PlatformTransactionLog is written in ONE place: verify_and_apply_payment
    after Paystack SUCCESS. Manual cash must not write it.
    """

    def setUp(self):
        super().setUp()
        overrides = override_settings(
            PAYSTACK_SECRET_KEY='sk_test_dummy',
            PLATFORM_COMMISSION_PCT=Decimal('5.00'),
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice, SchoolPaymentAccount

        self.invoice = Invoice.objects.get(student=self.students[0])
        SchoolPaymentAccount.objects.create(
            gateway=SchoolPaymentAccount.Gateway.PAYSTACK,
            subaccount_code='ACCT_logtest',
            bank_name='Zenith Bank',
            bank_code='057',
            account_number='0000000000',
            account_name='PAYSTACK TEST ACCOUNT',
            platform_commission_pct=Decimal('5.00'),
            is_verified=True,
            is_active=True,
            created_by=self.admin,
        )

    def _pending(self, *, amount=None, reference='pay_p7_ref'):
        from finance.models import Payment

        return Payment.objects.create(
            invoice=self.invoice,
            amount=amount if amount is not None else Decimal('157500.50'),
            reference=reference,
            status=Payment.Status.PENDING,
            gateway=Payment.Gateway.PAYSTACK,
            initiated_by=self.parent,
        )

    def test_verify_success_writes_one_log_with_commission_split(self):
        from finance.services import _commission_split, verify_and_apply_payment

        payment = self._pending()
        expected_commission, expected_net = _commission_split(
            payment.amount, Decimal('5.00')
        )
        self.assertEqual(expected_commission, Decimal('7875.03'))
        self.assertEqual(expected_net, Decimal('149625.47'))

        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(_verify_payload(payment.reference, payment.amount)),
        ):
            verify_and_apply_payment(payment.reference)

        logs = _platform_txn_logs(self.tenant)
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log.payment_reference, payment.reference)
        self.assertEqual(log.tenant_id, self.tenant.id)
        self.assertEqual(log.gross_amount, Decimal('157500.50'))
        self.assertEqual(log.commission_amount, expected_commission)
        self.assertEqual(log.net_to_school, expected_net)
        self.assertIsNotNone(log.timestamp)

    def test_idempotent_verify_does_not_duplicate_log(self):
        from finance.services import verify_and_apply_payment

        payment = self._pending()
        payload = _verify_payload(payment.reference, payment.amount)
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            verify_and_apply_payment(payment.reference)
            verify_and_apply_payment(payment.reference)

        self.assertEqual(len(_platform_txn_logs(self.tenant)), 1)

    def test_failed_and_mismatch_do_not_write_log(self):
        from finance.services import PaymentAmountMismatch, verify_and_apply_payment

        failed = self._pending(reference='pay_p7_fail')
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(failed.reference, failed.amount, txn_status='failed')
            ),
        ):
            verify_and_apply_payment(failed.reference)

        mismatch = self._pending(reference='pay_p7_mismatch')
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(
                _verify_payload(mismatch.reference, Decimal('1000.00'))
            ),
        ):
            with self.assertRaises(PaymentAmountMismatch):
                verify_and_apply_payment(mismatch.reference)

        self.assertEqual(_platform_txn_logs(self.tenant), [])

    def test_webhook_and_return_flow_share_the_log_writer(self):
        import inspect

        from finance import services

        src = inspect.getsource(services.verify_and_apply_payment)
        self.assertIn('_record_platform_transaction_log', src)
        writer_src = inspect.getsource(services._record_platform_transaction_log)
        self.assertIn('PlatformTransactionLog', writer_src)
        self.assertIn('record_paystack_success', writer_src)

        manual_src = inspect.getsource(services.record_manual_payment)
        self.assertNotIn('_record_platform_transaction_log', manual_src)
        self.assertNotIn('record_paystack_success', manual_src)

        import finance.webhooks as wh

        webhook_src = inspect.getsource(wh)
        self.assertIn('verify_and_apply_payment', webhook_src)
        self.assertNotIn('PlatformTransactionLog', webhook_src)
        self.assertNotIn('_record_platform_transaction_log', webhook_src)

    def test_webhook_success_writes_one_log_duplicate_does_not(self):
        from django.db import connection
        from finance.models import Payment
        from platform_admin.models import SubaccountTenantMap

        payment = self._pending(reference='pay_p7_wh')
        SubaccountTenantMap.upsert('ACCT_logtest', self.tenant)
        connection.set_tenant(self.tenant)

        body = _charge_success_body(
            reference=payment.reference, subaccount_code='ACCT_logtest'
        )
        payload = _verify_payload(payment.reference, payment.amount)
        public = APIClient()
        with mock.patch(
            'finance.paystack.requests.request',
            return_value=_response(payload),
        ):
            first = public.post(
                WEBHOOK_URL,
                data=body,
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE=_sign_body(body),
            )
            second = public.post(
                WEBHOOK_URL,
                data=body,
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE=_sign_body(body),
            )
        connection.set_tenant(self.tenant)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(status=Payment.Status.SUCCESS).count(), 1)
        self.assertEqual(len(_platform_txn_logs(self.tenant)), 1)


class CollectionDashboardTests(FinanceInvoicingTestCase):
    def setUp(self):
        super().setUp()
        self._make_fees()
        self._generate(self.admin)
        from finance.models import Invoice

        self.invoice = Invoice.objects.get(student=self.students[0])

    def _get(self, user, **params):
        self.api.force_authenticate(user=user)
        return self.api.get(COLLECTIONS_URL, params)

    def test_unpaid_class_shows_full_outstanding_and_zero_rate(self):
        response = self._get(self.bursar)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['term']['id'], str(self.term.id))
        self.assertEqual(response.data['invoice_count'], 3)
        self.assertEqual(response.data['unpaid_count'], 3)
        self.assertEqual(response.data['invoiced_total'], '472501.50')
        self.assertEqual(response.data['collected_total'], '0.00')
        self.assertEqual(response.data['outstanding_total'], '472501.50')
        self.assertEqual(response.data['collection_rate'], '0.00')
        self.assertEqual(len(response.data['by_class']), 1)
        jss1 = response.data['by_class'][0]
        self.assertEqual(jss1['class_level_name'], 'JSS1')
        self.assertEqual(jss1['invoiced_total'], '472501.50')
        self.assertEqual(jss1['outstanding_total'], '472501.50')

    def test_mixed_payments_and_second_class_breakdown(self):
        from datetime import date

        from academics.models import Arm, Enrollment, Student
        from finance.models import FeeStructure, Invoice
        from finance.services import record_manual_payment

        record_manual_payment(
            invoice=self.invoice,
            amount=Decimal('157500.50'),
            method='cash',
            recorded_by=self.bursar,
        )
        second = Invoice.objects.get(student=self.students[1])
        record_manual_payment(
            invoice=second,
            amount=Decimal('50000.00'),
            method='bank_transfer',
            recorded_by=self.bursar,
        )

        jss2_student = Student.objects.create(
            first_name='Jss2',
            last_name='Kid',
            date_of_birth=date(2013, 1, 1),
            gender=Student.Gender.FEMALE,
            admission_number='ADM-JSS2',
            admission_date=date(2026, 9, 1),
        )
        jss2_arm = Arm.objects.create(class_level=self.other_class_level, name='A')
        Enrollment.objects.create(
            student=jss2_student,
            class_level=self.other_class_level,
            arm=jss2_arm,
            session=self.session,
            term=self.term,
            status=Enrollment.Status.ACTIVE,
        )
        FeeStructure.objects.create(
            class_level=self.other_class_level,
            term=self.term,
            name='Tuition',
            amount=Decimal('100000.00'),
        )
        from finance.services import generate_invoices_for_class_term

        generate_invoices_for_class_term(
            class_level=self.other_class_level, term=self.term
        )

        response = self._get(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        # JSS1: 3 * 157500.50 = 472501.50; JSS2: 100000.00
        self.assertEqual(response.data['invoiced_total'], '572501.50')
        self.assertEqual(response.data['collected_total'], '207500.50')
        self.assertEqual(response.data['outstanding_total'], '365001.00')
        self.assertEqual(response.data['invoice_count'], 4)
        self.assertEqual(response.data['paid_count'], 1)
        self.assertEqual(response.data['partially_paid_count'], 1)
        self.assertEqual(response.data['unpaid_count'], 2)
        # 207500.50 / 572501.50 * 100 = 36.244… → 36.24
        self.assertEqual(response.data['collection_rate'], '36.24')

        by_name = {row['class_level_name']: row for row in response.data['by_class']}
        self.assertEqual(set(by_name), {'JSS1', 'JSS2'})
        self.assertEqual(by_name['JSS1']['invoice_count'], 3)
        self.assertEqual(by_name['JSS1']['collected_total'], '207500.50')
        self.assertEqual(by_name['JSS1']['outstanding_total'], '265001.00')
        self.assertEqual(by_name['JSS2']['invoice_count'], 1)
        self.assertEqual(by_name['JSS2']['invoiced_total'], '100000.00')
        self.assertEqual(by_name['JSS2']['collected_total'], '0.00')
        self.assertEqual(by_name['JSS2']['outstanding_total'], '100000.00')
        self.assertEqual(by_name['JSS2']['collection_rate'], '0.00')

        # Manual collections must not appear on the platform commission ledger.
        self.assertEqual(_platform_txn_logs(self.tenant), [])

    def test_parent_and_teacher_cannot_view(self):
        for user in (self.parent, self.teacher):
            response = self._get(user)
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, user.email
            )

    def test_explicit_term_query_param(self):
        response = self._get(self.bursar, term=str(self.term.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['term']['id'], str(self.term.id))

    def test_unknown_term_404(self):
        import uuid

        response = self._get(self.bursar, term=str(uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaystackStubGatingTests(SimpleTestCase):
    """Prompt 8 local fixture: stub cannot run when DEBUG is False."""

    def test_stub_off_by_default(self):
        from finance.paystack import gateway_stub_enabled

        with override_settings(DEBUG=True, PAYSTACK_STUB_GATEWAY=False):
            self.assertFalse(gateway_stub_enabled())

    def test_stub_disabled_when_not_debug(self):
        from finance.paystack import gateway_stub_enabled

        with override_settings(DEBUG=False, PAYSTACK_STUB_GATEWAY=True):
            self.assertFalse(gateway_stub_enabled())

    def test_stub_on_only_with_debug_and_flag(self):
        from finance.paystack import gateway_stub_enabled

        with override_settings(DEBUG=True, PAYSTACK_STUB_GATEWAY=True):
            self.assertTrue(gateway_stub_enabled())

    def test_stub_resolve_does_not_call_paystack(self):
        from finance.paystack import resolve_bank_account

        with override_settings(DEBUG=True, PAYSTACK_STUB_GATEWAY=True):
            with mock.patch('finance.paystack.requests.request') as http:
                data = resolve_bank_account('0000000000', '057')
        http.assert_not_called()
        self.assertEqual(data['account_name'], 'PAYSTACK TEST ACCOUNT')
        self.assertEqual(data['account_number'], '0000000000')



