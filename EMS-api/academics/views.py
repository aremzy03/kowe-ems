"""Academics API: admin CRUD + linking-code redemption + parent placeholders."""

import uuid

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.class_teacher_assignments import class_teacher_assignments_for_teacher
from academics.models import (
    Arm,
    ClassLevel,
    ClassSubjectAssignment,
    ClassTeacherAssignment,
    Enrollment,
    Guardian,
    Session,
    Student,
    StudentGuardianLink,
    Subject,
    Term,
)
from academics.parent_access import (
    HasLinkedStudentAccess,
    filter_queryset_for_parent_student_access,
    linked_student_ids_for_parent,
)
from academics.serializers import (
    ArmSerializer,
    ClassLevelSerializer,
    ClassSubjectAssignmentSerializer,
    ClassTeacherAssignmentSerializer,
    EnrollmentSerializer,
    GuardianSerializer,
    LinkingCodeRedeemSerializer,
    SessionSerializer,
    StudentDetailSerializer,
    StudentGuardianLinkSerializer,
    StudentSerializer,
    SubjectSerializer,
    TermSerializer,
)
from academics.teacher_assignments import assignments_for_teacher
from memberships.permissions import (
    IsAdminOrTeacher,
    IsAdminOrTeacherOrBursar,
    IsParent,
    IsSchoolAdmin,
    IsSchoolMember,
    IsTeacher,
)


# ---------------------------------------------------------------------------
# Admin-facing academic structure CRUD (Prompt 6)
# ---------------------------------------------------------------------------


class ProtectedDestroyMixin:
    """Map Django ProtectedError (PROTECT FKs) to 409 instead of a 500."""

    protected_delete_detail = (
        'This record is still referenced by other data and cannot be deleted.'
    )

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': self.protected_delete_detail},
                status=status.HTTP_409_CONFLICT,
            )


class SessionViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Sessions: any school member may list/retrieve (term pickers need labels).
    Writes stay admin-only.
    """

    queryset = Session.objects.all()
    serializer_class = SessionSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsSchoolMember()]
        return [IsSchoolAdmin()]


class TermViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Terms: any school member may list/retrieve (parent results and attendance
    need the term id). Writes stay admin-only.
    """

    queryset = Term.objects.select_related('session').all()
    serializer_class = TermSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsSchoolMember()]
        return [IsSchoolAdmin()]


class ClassLevelViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Class levels: teachers and bursars may list/retrieve (marks / invoicing);
    writes are admin-only.
    """

    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacherOrBursar()]
        return [IsSchoolAdmin()]


class ArmViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Arms: teachers and bursars may list/retrieve; writes are admin-only.
    """

    queryset = Arm.objects.select_related('class_level').all()
    serializer_class = ArmSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacherOrBursar()]
        return [IsSchoolAdmin()]


class SubjectViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Subjects: teachers and bursars may list/retrieve; writes are admin-only.
    """

    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacherOrBursar()]
        return [IsSchoolAdmin()]


class StudentViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """
    Student CRUD — school admin only.

    Create uses ``create_with_linking_code`` (via StudentSerializer) and
    returns the generated unused linking code in the response body.

    ``POST …/students/{id}/regenerate-linking-code/`` invalidates unused
    codes for that student (``is_used=True``, ``used_by`` left null so it
    is distinguishable from a parent redeem) and issues a new unused code
    via ``Student.generate_unused_linking_code``.
    """

    queryset = Student.objects.prefetch_related('linking_codes').all()
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolAdmin]
    protected_delete_detail = (
        'This student has invoices or other protected records and cannot be deleted.'
    )

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'regenerate_linking_code'):
            return StudentDetailSerializer
        return StudentSerializer

    def get_queryset(self):
        qs = Student.objects.prefetch_related('linking_codes')
        if self.action in ('retrieve', 'create', 'regenerate_linking_code'):
            qs = qs.prefetch_related('guardian_links__guardian__user')
        return qs

    @action(detail=True, methods=['post'], url_path='regenerate-linking-code')
    def regenerate_linking_code(self, request, pk=None):
        student = self.get_object()
        with transaction.atomic():
            locked = Student.objects.select_for_update().get(pk=student.pk)
            locked.linking_codes.filter(is_used=False).update(
                is_used=True,
                used_at=timezone.now(),
            )
            locked.generate_unused_linking_code()
        refreshed = self.get_queryset().get(pk=student.pk)
        serializer = self.get_serializer(refreshed)
        return Response(serializer.data)


def _uuid_query_param(value):
    """Return a UUID string, or None if missing/blank. False if invalid."""
    if value is None or str(value).strip() == '':
        return None
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return False


class GuardianViewSet(viewsets.ModelViewSet):
    """
    Guardian contact CRUD — school admin only.

    Destroy is refused with 409 while any ``StudentGuardianLink`` exists.
    The model FK is ``CASCADE``, so unlinking first is required to avoid
    silently dropping parent↔student relationships. Unlinked rows may be
    deleted; the parent ``User`` (if any) is left in the public schema.
    """

    queryset = Guardian.objects.select_related('user').all()
    serializer_class = GuardianSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.student_links.exists():
            return Response(
                {
                    'detail': (
                        'This guardian is still linked to one or more students. '
                        'Unlink them first, then delete.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class StudentGuardianLinkViewSet(viewsets.ModelViewSet):
    """
    Link / unlink guardians and students — school admin only.

    List accepts ``?student=<uuid>`` and ``?guardian=<uuid>``. PATCH may
    set ``is_primary_contact``; promoting one link demotes the others for
    that student.
    """

    queryset = StudentGuardianLink.objects.select_related(
        'student',
        'guardian',
        'guardian__user',
    ).all()
    serializer_class = StudentGuardianLinkSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = StudentGuardianLink.objects.select_related(
            'student',
            'guardian',
            'guardian__user',
        )
        student_id = _uuid_query_param(self.request.query_params.get('student'))
        if student_id is False:
            return qs.none()
        if student_id:
            qs = qs.filter(student_id=student_id)

        guardian_id = _uuid_query_param(self.request.query_params.get('guardian'))
        if guardian_id is False:
            return qs.none()
        if guardian_id:
            qs = qs.filter(guardian_id=guardian_id)
        return qs


class EnrollmentViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    """Enrollment CRUD — school admin only. Blocks duplicate active placements."""

    queryset = Enrollment.objects.select_related(
        'student',
        'class_level',
        'arm',
        'session',
        'term',
    ).all()
    serializer_class = EnrollmentSerializer
    permission_classes = [IsSchoolAdmin]


class ClassSubjectAssignmentViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for which teacher teaches which subject to which class/arm/term.

    Teachers use ``MyClassSubjectAssignmentsView`` (read-only, own rows only).
    """

    queryset = ClassSubjectAssignment.objects.select_related(
        'teacher',
        'subject',
        'class_level',
        'arm',
        'term',
        'term__session',
    ).all()
    serializer_class = ClassSubjectAssignmentSerializer
    permission_classes = [IsSchoolAdmin]


class ClassTeacherAssignmentViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for which teacher is form/class teacher for a class/arm/term.

    Teachers use ``MyClassTeacherAssignmentsView`` (read-only, own rows only).
    Independent of subject-teacher assignments.
    """

    queryset = ClassTeacherAssignment.objects.select_related(
        'teacher',
        'class_level',
        'arm',
        'term',
        'term__session',
    ).all()
    serializer_class = ClassTeacherAssignmentSerializer
    permission_classes = [IsSchoolAdmin]


# ---------------------------------------------------------------------------
# Teacher-scoped assignment lists (Phase 2 Prompt 1 / Phase 3 Prompt 1)
# ---------------------------------------------------------------------------


class MyClassSubjectAssignmentsView(APIView):
    """
    GET /api/academics/my-assignments/

    Read-only list of ClassSubjectAssignment rows for the authenticated
    teacher. Foundation for scoping later teacher-facing assessment endpoints.
    """

    permission_classes = [IsTeacher]

    def get(self, request, *args, **kwargs):
        qs = assignments_for_teacher(request.user).order_by(
            'term__start_date',
            'class_level__name',
            'arm__name',
            'subject__name',
        )
        data = ClassSubjectAssignmentSerializer(qs, many=True).data
        return Response({'count': len(data), 'results': data})


class MyClassTeacherAssignmentsView(APIView):
    """
    GET /api/academics/my-classes/

    Read-only list of ClassTeacherAssignment rows for the authenticated
    teacher — the class/arm/term combos where they are the form teacher.
    Distinct from ``my-assignments/`` (subject teaching).
    """

    permission_classes = [IsTeacher]

    def get(self, request, *args, **kwargs):
        qs = class_teacher_assignments_for_teacher(request.user).order_by(
            'term__start_date',
            'class_level__name',
            'arm__name',
        )
        data = ClassTeacherAssignmentSerializer(qs, many=True).data
        return Response({'count': len(data), 'results': data})


# ---------------------------------------------------------------------------
# Parent linking + placeholders (Prompt 4) — unchanged behaviour
# ---------------------------------------------------------------------------


class LinkingCodeRedeemView(APIView):
    """
    POST /api/academics/linking-codes/redeem/

    Authenticated parent submits a school-issued code. Marks it used and
    creates/attaches Guardian + StudentGuardianLink for the bound student.
    """

    permission_classes = [IsParent]

    def post(self, request, *args, **kwargs):
        serializer = LinkingCodeRedeemSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        linking_code = serializer.save()
        return Response(
            {
                'detail': 'Linking code redeemed.',
                'code': linking_code.code,
                'student_id': (
                    str(linking_code.student_id) if linking_code.student_id else None
                ),
                'linked_student_count': len(linked_student_ids_for_parent(request.user)),
            },
            status=status.HTTP_200_OK,
        )


class MyStudentsPlaceholderView(APIView):
    """
    GET /api/academics/my-students/

    Placeholder student-data shaped endpoint for parents. Returns only
    students with a StudentGuardianLink. Before any redemption, the list is
    empty — no leakage of which students exist.
    """

    permission_classes = [IsParent]

    def get(self, request, *args, **kwargs):
        qs = filter_queryset_for_parent_student_access(
            Student.objects.all(),
            request.user,
        ).order_by('last_name', 'first_name')
        students = [
            {
                'id': str(s.id),
                'first_name': s.first_name,
                'last_name': s.last_name,
                'admission_number': s.admission_number,
            }
            for s in qs
        ]
        return Response({'count': len(students), 'results': students})


class ParentStudentAccessExampleView(APIView):
    """
    GET /api/academics/my-students/<uuid:student_id>/

    Demonstrates HasLinkedStudentAccess object-level gating. Unlinked student
    IDs return 403 — no PII leak for students the parent is not linked to.

    Path moved under ``my-students/`` so admin StudentViewSet can own
    ``/api/academics/students/``.
    """

    permission_classes = [HasLinkedStudentAccess]

    def get(self, request, student_id, *args, **kwargs):
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            # Same denial as unlinked — do not reveal whether the UUID exists.
            self.permission_denied(request, message=HasLinkedStudentAccess.message)
            return  # pragma: no cover

        self.check_object_permissions(request, student)
        return Response(
            {
                'id': str(student.id),
                'first_name': student.first_name,
                'last_name': student.last_name,
                'admission_number': student.admission_number,
            }
        )
