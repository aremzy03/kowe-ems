from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.parent_access import (
    filter_queryset_for_parent_student_access,
    parent_has_link_to_student,
)
from finance.models import FeeStructure, Invoice, Payment, SchoolPaymentAccount
from finance.paystack import PaystackError
from finance.serializers import (
    FeeStructureSerializer,
    InitializePaymentSerializer,
    InvoiceGenerateSerializer,
    InvoiceSerializer,
    PaymentAccountOnboardSerializer,
    RecordManualPaymentSerializer,
    SchoolPaymentAccountSerializer,
    VerifyPaymentSerializer,
)
from finance.services import (
    OnlinePaymentsUnavailable,
    PaymentAccountExists,
    PaymentAmountMismatch,
    collection_dashboard_for_term,
    current_active_term,
    generate_invoices_for_class_term,
    initialize_invoice_payment,
    onboard_school_payment_account,
    paid_amount_annotation,
    record_manual_payment,
    verify_and_apply_payment,
)
from memberships.permissions import IsAdminOrBursar, IsParent, IsSchoolAdmin


class SchoolPaymentAccountView(APIView):
    """
    GET  /api/finance/payment-account/ — current onboarding state (masked).
    POST /api/finance/payment-account/ — submit bank_code + account_number;
         server resolves the account with Paystack, creates the split
         subaccount, and stores the verified result. Admin-only (2FA-gated
         via IsSchoolAdmin).
    """

    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        account = SchoolPaymentAccount.objects.first()
        if account is None:
            return Response(
                {
                    'onboarded': False,
                    'detail': (
                        'No payment account yet. Online fee payments are '
                        'disabled until bank details are verified.'
                    ),
                }
            )
        return Response(
            {'onboarded': True, 'account': SchoolPaymentAccountSerializer(account).data}
        )

    def post(self, request):
        serializer = PaymentAccountOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            account = onboard_school_payment_account(
                bank_code=data['bank_code'],
                account_number=data['account_number'],
                created_by=request.user,
                expected_account_name=data.get('account_name') or None,
            )
        except PaymentAccountExists as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)
        except PaystackError as exc:
            # 4xx from Paystack (e.g. unresolvable account number) is the
            # caller's problem; anything else is a gateway failure.
            gateway_client_error = (
                exc.status_code is not None and 400 <= exc.status_code < 500
            )
            return Response(
                {'detail': exc.message},
                status=status.HTTP_400_BAD_REQUEST
                if gateway_client_error
                else status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            SchoolPaymentAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Fee structures and invoicing (Prompt 2)
# ---------------------------------------------------------------------------


class FeeStructureViewSet(viewsets.ModelViewSet):
    """Full CRUD for fee items — school admin only."""

    queryset = FeeStructure.objects.select_related(
        'class_level',
        'term',
        'term__session',
    ).all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsSchoolAdmin]

    def destroy(self, request, *args, **kwargs):
        # PROTECT on InvoiceLineItem.fee_structure: a fee referenced by an
        # issued invoice is part of the billing audit trail and cannot be
        # deleted out from under it.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'This fee structure is referenced by issued invoices '
                        'and cannot be deleted.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )


class InvoiceGenerateView(APIView):
    """
    POST /api/finance/invoices/generate/ — admin or bursar.

    Generates invoices for every actively-enrolled student in a class
    level + term in one call. Students who already have an invoice for the
    term are skipped (idempotent re-run — no duplicates).
    """

    permission_classes = [IsAdminOrBursar]

    def post(self, request):
        serializer = InvoiceGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = generate_invoices_for_class_term(
                class_level=serializer.validated_data['class_level'],
                term=serializer.validated_data['term'],
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        created = (
            Invoice.objects.filter(pk__in=[inv.pk for inv in result['created']])
            .select_related('student', 'term', 'term__session')
            .prefetch_related('line_items__fee_structure')
            .annotate(amount_paid_total=paid_amount_annotation())
        )
        return Response(
            {
                'created_count': len(result['created']),
                'skipped_count': len(result['skipped_student_ids']),
                'skipped_student_ids': [
                    str(sid) for sid in result['skipped_student_ids']
                ],
                'invoices': InvoiceSerializer(created, many=True).data,
            },
            status=status.HTTP_201_CREATED
            if result['created']
            else status.HTTP_200_OK,
        )


class MyInvoicesView(APIView):
    """
    GET /api/finance/my-invoices/ — parent only.

    Itemized invoices (with current payment status) for students the parent
    is linked to via StudentGuardianLink. Parents with no links get an empty
    list — no leakage of other students' billing.
    """

    permission_classes = [IsParent]

    def get(self, request):
        qs = (
            filter_queryset_for_parent_student_access(
                Invoice.objects.all(),
                request.user,
                student_field='student_id',
            )
            .select_related('student', 'term', 'term__session')
            .prefetch_related('line_items__fee_structure')
            .annotate(amount_paid_total=paid_amount_annotation())
            .order_by('-created_at')
        )
        data = InvoiceSerializer(qs, many=True).data
        return Response({'count': len(data), 'results': data})


class InitializePaymentView(APIView):
    """
    POST /api/finance/payments/initialize/ — parent only.

    Starts Paystack checkout for a linked student's invoice. Returns
    authorization_url; does NOT mark the invoice or payment as paid.
    Blocked when the school has no active SchoolPaymentAccount.
    """

    permission_classes = [IsParent]

    def post(self, request):
        serializer = InitializePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.validated_data['invoice']

        # 404 rather than 403 so invoice IDs of other students don't leak.
        if not parent_has_link_to_student(request.user, invoice.student_id):
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment, gateway_data = initialize_invoice_payment(
                invoice=invoice,
                parent=request.user,
                amount=serializer.validated_data.get('amount'),
            )
        except OnlinePaymentsUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)
        except PaystackError as exc:
            gateway_client_error = (
                exc.status_code is not None and 400 <= exc.status_code < 500
            )
            return Response(
                {'detail': exc.message},
                status=status.HTTP_400_BAD_REQUEST
                if gateway_client_error
                else status.HTTP_502_BAD_GATEWAY,
            )

        invoice.refresh_from_db()
        return Response(
            {
                'authorization_url': gateway_data['authorization_url'],
                'access_code': gateway_data.get('access_code'),
                'reference': payment.reference,
                'amount': str(payment.amount),
                'payment_id': str(payment.id),
                'invoice': str(invoice.id),
                'invoice_status': invoice.status,
                'payment_status': payment.status,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyPaymentView(APIView):
    """
    POST /api/finance/payments/verify/ — parent only.

    Return-flow check after Paystack checkout. Does not trust the
    frontend redirect: calls ``verify_and_apply_payment(reference)``,
    the same function Prompt 5's webhook will use. Idempotent for an
    already-SUCCESS reference.
    """

    permission_classes = [IsParent]

    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = serializer.validated_data['reference']

        try:
            payment = Payment.objects.select_related('invoice').get(
                reference=reference
            )
        except Payment.DoesNotExist:
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 404 rather than 403 so references for other students don't leak.
        if not parent_has_link_to_student(request.user, payment.invoice.student_id):
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = verify_and_apply_payment(reference)
        except Payment.DoesNotExist:
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PaymentAmountMismatch as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)
        except PaystackError as exc:
            gateway_client_error = (
                exc.status_code is not None and 400 <= exc.status_code < 500
            )
            return Response(
                {'detail': exc.message},
                status=status.HTTP_400_BAD_REQUEST
                if gateway_client_error
                else status.HTTP_502_BAD_GATEWAY,
            )

        invoice = payment.invoice
        invoice.refresh_from_db()
        return Response(
            {
                'reference': payment.reference,
                'payment_id': str(payment.id),
                'amount': str(payment.amount),
                'payment_status': payment.status,
                'paid_at': payment.paid_at,
                'invoice': str(invoice.id),
                'invoice_status': invoice.status,
            }
        )


class RecordManualPaymentView(APIView):
    """
    POST /api/finance/payments/manual/ — admin or bursar.

    Records cash or bank transfer against an invoice. Creates a SUCCESS
    Payment with gateway='manual' (no Paystack verify). Invoice status is
    updated inside ``record_manual_payment`` via the shared status writer.
    Available even when the school has no SchoolPaymentAccount.
    """

    permission_classes = [IsAdminOrBursar]

    def post(self, request):
        serializer = RecordManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment = record_manual_payment(
                invoice=data['invoice'],
                amount=data['amount'],
                method=data['method'],
                recorded_by=request.user,
                notes=data.get('notes') or '',
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        invoice = payment.invoice
        invoice.refresh_from_db()
        return Response(
            {
                'reference': payment.reference,
                'payment_id': str(payment.id),
                'amount': str(payment.amount),
                'payment_status': payment.status,
                'gateway': payment.gateway,
                'method': payment.method,
                'paid_at': payment.paid_at,
                'notes': payment.notes,
                'invoice': str(invoice.id),
                'invoice_status': invoice.status,
                'recorded_by': str(payment.recorded_by_id),
            },
            status=status.HTTP_201_CREATED,
        )


def _money_as_api_string(value):
    from decimal import Decimal

    from rest_framework import serializers as drf_serializers

    field = drf_serializers.DecimalField(max_digits=12, decimal_places=2)
    if value is None:
        value = Decimal('0.00')
    return field.to_representation(value)


def _serialize_collection_bucket(bucket):
    return {
        'invoiced_total': _money_as_api_string(bucket['invoiced_total']),
        'collected_total': _money_as_api_string(bucket['collected_total']),
        'outstanding_total': _money_as_api_string(bucket['outstanding_total']),
        'collection_rate': _money_as_api_string(bucket['collection_rate']),
        'invoice_count': bucket['invoice_count'],
        'paid_count': bucket['paid_count'],
        'partially_paid_count': bucket['partially_paid_count'],
        'unpaid_count': bucket['unpaid_count'],
    }


class CollectionDashboardView(APIView):
    """
    GET /api/finance/dashboard/collections/ — admin or bursar.

    Outstanding total and collection rate (collected vs invoiced) for the
    current term, broken down by class. Pass ``?term=<uuid>`` to pick a
    term; otherwise the school's active term is used.
    """

    permission_classes = [IsAdminOrBursar]

    def get(self, request):
        from academics.models import Term

        term_id = request.query_params.get('term')
        if term_id:
            try:
                term = Term.objects.select_related('session').get(pk=term_id)
            except (Term.DoesNotExist, ValueError, DjangoValidationError):
                return Response(
                    {'detail': 'Term not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            term = current_active_term()
            if term is None:
                return Response(
                    {
                        'detail': (
                            'No active term. Pass ?term=<id> or set an active term.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        data = collection_dashboard_for_term(term)
        overall = _serialize_collection_bucket(data['overall'])
        return Response(
            {
                'term': {
                    'id': str(term.id),
                    'name': term.name,
                    'session': term.session.name,
                    'is_active': term.is_active,
                },
                **overall,
                'by_class': [
                    {
                        'class_level_id': row['class_level_id'],
                        'class_level_name': row['class_level_name'],
                        **_serialize_collection_bucket(row),
                    }
                    for row in data['by_class']
                ],
            }
        )
