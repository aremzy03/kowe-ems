"""Academics API: admin CRUD + linking-code redemption + parent placeholders."""

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import (
    Arm,
    ClassLevel,
    ClassSubjectAssignment,
    Enrollment,
    Session,
    Student,
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
    EnrollmentSerializer,
    LinkingCodeRedeemSerializer,
    SessionSerializer,
    StudentSerializer,
    SubjectSerializer,
    TermSerializer,
)
from academics.teacher_assignments import assignments_for_teacher
from memberships.permissions import IsAdminOrTeacher, IsParent, IsSchoolAdmin, IsTeacher


# ---------------------------------------------------------------------------
# Admin-facing academic structure CRUD (Prompt 6)
# ---------------------------------------------------------------------------


class SessionViewSet(viewsets.ModelViewSet):
    """Full CRUD for academic sessions — school admin only."""

    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    permission_classes = [IsSchoolAdmin]


class TermViewSet(viewsets.ModelViewSet):
    """Full CRUD for terms — school admin only."""

    queryset = Term.objects.select_related('session').all()
    serializer_class = TermSerializer
    permission_classes = [IsSchoolAdmin]


class ClassLevelViewSet(viewsets.ModelViewSet):
    """
    Class levels: teachers may list/retrieve (for marks entry);
    writes are admin-only.
    """

    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacher()]
        return [IsSchoolAdmin()]


class ArmViewSet(viewsets.ModelViewSet):
    """
    Arms: teachers may list/retrieve; writes are admin-only.
    """

    queryset = Arm.objects.select_related('class_level').all()
    serializer_class = ArmSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacher()]
        return [IsSchoolAdmin()]


class SubjectViewSet(viewsets.ModelViewSet):
    """
    Subjects: teachers may list/retrieve; writes are admin-only.
    """

    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAdminOrTeacher()]
        return [IsSchoolAdmin()]


class StudentViewSet(viewsets.ModelViewSet):
    """
    Student CRUD — school admin only.

    Create uses ``create_with_linking_code`` (via StudentSerializer) and
    returns the generated unused linking code in the response body.
    """

    queryset = Student.objects.prefetch_related('linking_codes').all()
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolAdmin]


class EnrollmentViewSet(viewsets.ModelViewSet):
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


# ---------------------------------------------------------------------------
# Teacher-scoped assignment list (Phase 2 Prompt 1)
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
