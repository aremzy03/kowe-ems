from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.class_teacher_assignments import (
    IsAssignedClassTeacherOrAdmin,
    filter_queryset_for_class_teacher_assignments,
)
from academics.models import Student, Term
from attendance.models import AttendanceAuditLog, DailyAttendance
from attendance.serializers import (
    AdminAttendanceOverviewQuerySerializer,
    AttendanceAuditLogSerializer,
    BulkAttendanceUpsertSerializer,
    ClassRegisterQuerySerializer,
    DailyAttendanceSerializer,
    ParentDailyAttendanceQuerySerializer,
    StudentTermAttendanceQuerySerializer,
)
from attendance.services import (
    assert_actor_may_view_attendance,
    build_admin_attendance_overview,
    build_class_register,
    compute_term_attendance_summary,
)
from memberships.models import SchoolMembership
from memberships.permissions import (
    IsAdminOrTeacher,
    IsParent,
    IsSchoolAdmin,
    resolve_request_membership,
)


def _drf_from_django(exc: DjangoValidationError):
    from rest_framework.exceptions import ValidationError as DRFValidationError

    if hasattr(exc, 'message_dict'):
        raise DRFValidationError(exc.message_dict)
    if hasattr(exc, 'messages'):
        raise DRFValidationError(list(exc.messages))
    raise DRFValidationError(str(exc))


class DailyAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Daily register listing + bulk mark endpoint.

    POST /bulk-upsert/ — idempotent batch upsert with per-entry results.
    Write path is bulk-only (matches Phase 2 score entry); list/retrieve for
    class teachers and admins.
    """

    serializer_class = DailyAttendanceSerializer
    permission_classes = [IsAssignedClassTeacherOrAdmin]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = DailyAttendance.objects.select_related(
            'student',
            'class_level',
            'arm',
            'term',
            'term__session',
            'marked_by',
        ).all()
        membership = resolve_request_membership(self.request)
        if membership is None:
            return qs.none()
        if membership.role == SchoolMembership.Role.ADMIN:
            return qs
        if membership.role == SchoolMembership.Role.TEACHER:
            return filter_queryset_for_class_teacher_assignments(
                qs,
                self.request.user,
            )
        return qs.none()

    def get_class_teacher_scope(self, obj):
        """Resolve ClassTeacherAssignment scope for IsAssignedClassTeacherOrAdmin."""
        return (obj.class_level_id, obj.arm_id, obj.term_id)

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        params = self.request.query_params
        if params.get('date'):
            qs = qs.filter(date=params['date'])
        if params.get('class_level'):
            qs = qs.filter(class_level_id=params['class_level'])
        if params.get('arm'):
            qs = qs.filter(arm_id=params['arm'])
        if params.get('term'):
            qs = qs.filter(term_id=params['term'])
        if params.get('student'):
            qs = qs.filter(student_id=params['student'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        return qs

    @action(detail=False, methods=['post'], url_path='bulk-upsert')
    def bulk_upsert(self, request):
        """
        Upsert {student_id, status, remarks}[] for a class/arm/term/date.

        Each entry succeeds or fails independently. Re-submitting the same
        payload is safe (unique student+date; no-op status skips audit).
        """
        serializer = BulkAttendanceUpsertSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        results = serializer.save()
        succeeded = sum(1 for r in results if r.get('success'))
        failed = len(results) - succeeded
        http_status = (
            status.HTTP_200_OK
            if failed == 0
            else status.HTTP_207_MULTI_STATUS
            if succeeded > 0
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {
                'count': len(results),
                'succeeded': succeeded,
                'failed': failed,
                'results': results,
            },
            status=http_status,
        )


class AttendanceAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin read-only view of attendance status-change audit entries."""

    serializer_class = AttendanceAuditLogSerializer
    permission_classes = [IsSchoolAdmin]
    queryset = AttendanceAuditLog.objects.select_related(
        'student',
        'changed_by',
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        student = self.request.query_params.get('student')
        date = self.request.query_params.get('date')
        if student:
            qs = qs.filter(student_id=student)
        if date:
            qs = qs.filter(date=date)
        return qs


class StudentTermAttendanceSummaryView(APIView):
    """
    GET /api/attendance/summaries/student/?student=&term=

    Compute-on-read termly aggregate for one student.
    Access: admin (any), assigned class teacher, or linked parent
    (StudentGuardianLink — same as Phase 2 report cards).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = resolve_request_membership(request)
        if membership is None:
            return Response(
                {'detail': 'Active membership at this school is required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in (
            SchoolMembership.Role.ADMIN,
            SchoolMembership.Role.TEACHER,
            SchoolMembership.Role.PARENT,
        ):
            return Response(
                {'detail': 'You do not have permission to view attendance.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = StudentTermAttendanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        student_id = query.validated_data['student']
        term_id = query.validated_data['term']

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response(
                {'student': 'Student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            term = Term.objects.select_related('session').get(pk=term_id)
        except Term.DoesNotExist:
            return Response(
                {'term': 'Term not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            assert_actor_may_view_attendance(
                request=request,
                student=student,
                term_id=term.pk,
            )
        except DjangoValidationError as exc:
            _drf_from_django(exc)

        summary = compute_term_attendance_summary(student=student, term=term)
        return Response(summary.as_dict())


class ParentStudentDailyAttendanceView(APIView):
    """
    GET /api/attendance/parents/daily/?student=&term=

    Read-only daily attendance log for a linked child. Optional filters:
    term, date, or date_from/date_to.
    """

    permission_classes = [IsParent]

    def get(self, request):
        query = ParentDailyAttendanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        student = data['student_obj']

        try:
            assert_actor_may_view_attendance(request=request, student=student)
        except DjangoValidationError as exc:
            _drf_from_django(exc)

        qs = (
            DailyAttendance.objects.filter(student_id=student.pk)
            .select_related(
                'student',
                'class_level',
                'arm',
                'term',
                'term__session',
                'marked_by',
            )
            .order_by('-date')
        )
        if data.get('term_obj') is not None:
            qs = qs.filter(term_id=data['term_obj'].pk)
        if data.get('date') is not None:
            qs = qs.filter(date=data['date'])
        if data.get('date_from') is not None:
            qs = qs.filter(date__gte=data['date_from'], date__lte=data['date_to'])

        rows = list(qs)
        return Response(
            {
                'student': str(student.pk),
                'student_name': f'{student.last_name}, {student.first_name}',
                'count': len(rows),
                'results': DailyAttendanceSerializer(rows, many=True).data,
            }
        )


class AdminAttendanceOverviewView(APIView):
    """
    GET /api/attendance/admin/overview/?date=YYYY-MM-DD
    GET /api/attendance/admin/overview/?term=<uuid>

    School-wide mark-entry status for the admin dashboard (pending / partial /
    complete per class for a date, or term activity aggregates).
    """

    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        query = AdminAttendanceOverviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        try:
            if 'date' in data:
                payload = build_admin_attendance_overview(
                    overview_date=data['date'],
                )
            else:
                payload = build_admin_attendance_overview(
                    term=data['term_obj'],
                )
        except DjangoValidationError as exc:
            _drf_from_django(exc)
        return Response(payload)


class ClassAttendanceRegisterView(APIView):
    """
    GET /api/attendance/register/?class_level=&arm=&term=&month=YYYY-MM

    Student × date grid for teachers/admins. Optional date_from/date_to
    instead of month; default window is the full term.
    """

    permission_classes = [IsAdminOrTeacher]

    def get(self, request):
        query = ClassRegisterQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        try:
            assert_actor_may_view_attendance(
                request=request,
                class_level_id=data['class_level'],
                arm_id=data['arm'],
                term_id=data['term'],
            )
        except DjangoValidationError as exc:
            _drf_from_django(exc)

        try:
            register = build_class_register(
                class_level_id=data['class_level'],
                arm_id=data['arm'],
                term_id=data['term'],
                month=data.get('month'),
                date_from=data.get('date_from'),
                date_to=data.get('date_to'),
            )
        except DjangoValidationError as exc:
            _drf_from_django(exc)

        return Response(register)
