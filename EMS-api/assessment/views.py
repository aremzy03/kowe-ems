"""Assessment API: CA components, scores, term results, broadsheet, report cards."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Enrollment
from academics.teacher_assignments import (
    IsAssignedTeacherOrAdmin,
    assignments_for_teacher,
)
from assessment.models import (
    WEIGHT_TOTAL_REQUIRED,
    AssessmentComponent,
    AuditLog,
    Score,
    TermResult,
    TermResultSummary,
    scheme_weight_sum,
)
from assessment.report_cards import render_report_card_pdf
from assessment.serializers import (
    AssessmentComponentSerializer,
    AuditLogSerializer,
    BroadsheetQuerySerializer,
    BulkScoreUpsertSerializer,
    CloneSchemeSerializer,
    PublishClassResultsSerializer,
    RecomputeClassResultsSerializer,
    ReportCardQuerySerializer,
    ScoreSerializer,
    SetSchemeSerializer,
    StudentTermResultsQuerySerializer,
    TermResultRemarksSerializer,
    TermResultSerializer,
    TermResultSummarySerializer,
)
from assessment.services import assignment_scope_for_score
from memberships.models import SchoolMembership
from memberships.permissions import (
    IsAdminOrTeacher,
    IsSchoolAdmin,
    IsTeacher,
    resolve_request_membership,
)

RESULTS_NOT_PUBLISHED_DETAIL = (
    'Results for this term have not been published yet.'
)


def _unpublished_parent_results_payload(student, term):
    """Parent read with no averages, positions, remarks, or subject scores."""
    return {
        'student': str(student.pk),
        'student_name': f'{student.last_name}, {student.first_name}',
        'term': str(term.pk),
        'term_name': term.name,
        'summary': None,
        'subject_results': [],
        'is_published': False,
        'detail': RESULTS_NOT_PUBLISHED_DETAIL,
    }


def filter_components_for_teacher(queryset, user):
    """
    Restrict AssessmentComponent rows to schemes the teacher is assigned to.

    Components are keyed by subject + class_level + term (no arm). Any
    ClassSubjectAssignment for that triple grants access, regardless of arm.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return queryset.none()

    combos = (
        assignments_for_teacher(user)
        .values_list('subject_id', 'class_level_id', 'term_id')
        .distinct()
    )
    q = Q()
    has_any = False
    for subject_id, class_level_id, term_id in combos:
        has_any = True
        q |= Q(
            subject_id=subject_id,
            class_level_id=class_level_id,
            term_id=term_id,
        )
    if not has_any:
        return queryset.none()
    return queryset.filter(q)


def filter_scores_for_teacher(queryset, user):
    """
    Restrict Score rows to the teacher's ClassSubjectAssignments.

    Matches component subject/class/term plus the student's active enrollment
    arm (assignments are per-arm).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return queryset.none()

    combos = assignments_for_teacher(user).values_list(
        'subject_id',
        'class_level_id',
        'arm_id',
        'term_id',
    )
    q = Q()
    has_any = False
    for subject_id, class_level_id, arm_id, term_id in combos:
        has_any = True
        student_ids = Enrollment.objects.filter(
            class_level_id=class_level_id,
            arm_id=arm_id,
            term_id=term_id,
            status=Enrollment.Status.ACTIVE,
        ).values('student_id')
        q |= Q(
            assessment_component__subject_id=subject_id,
            assessment_component__class_level_id=class_level_id,
            assessment_component__term_id=term_id,
            student_id__in=student_ids,
        )
    if not has_any:
        return queryset.none()
    return queryset.filter(q)


class AssessmentComponentViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for weighted assessment components.

    Extra actions:
    - POST /set-scheme/ — atomically replace a subject/class/term scheme
    - POST /clone-scheme/ — copy a scheme onto another subject/class/term
    """

    queryset = AssessmentComponent.objects.select_related(
        'subject',
        'class_level',
        'term',
        'term__session',
    ).all()
    serializer_class = AssessmentComponentSerializer
    permission_classes = [IsSchoolAdmin]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        remaining = scheme_weight_sum(
            subject_id=instance.subject_id,
            class_level_id=instance.class_level_id,
            term_id=instance.term_id,
            exclude_pk=instance.pk,
        )
        # Empty scheme is allowed; a non-empty remainder must still total 100.
        if remaining != 0 and remaining != WEIGHT_TOTAL_REQUIRED:
            raise ValidationError(
                f'Cannot delete this component: remaining weights would sum to '
                f'{remaining}%, but must equal {WEIGHT_TOTAL_REQUIRED}% '
                f'(or remove the whole scheme via set-scheme).'
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='set-scheme')
    def set_scheme(self, request):
        """
        Atomically set (replace) all components for one subject/class/term.

        Preferred way to create a multi-component 1st CA / 2nd CA / Exam
        scheme in one request so the 100% rule always holds.
        """
        serializer = SetSchemeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        data = AssessmentComponentSerializer(created, many=True).data
        return Response(
            {
                'count': len(data),
                'results': data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], url_path='clone-scheme')
    def clone_scheme(self, request):
        """
        Clone components from one subject/class/term onto another
        (e.g. Maths JSS1 Term 1 → English JSS1 Term 1, or Term 1 → Term 2).
        """
        serializer = CloneSchemeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        data = AssessmentComponentSerializer(created, many=True).data
        return Response(
            {
                'detail': 'Scheme cloned.',
                'count': len(data),
                'results': data,
            },
            status=status.HTTP_201_CREATED,
        )


class MyAssessmentComponentsView(APIView):
    """
    GET /api/assessment/my-components/

    Teacher-scoped read: components for subject/class/term combos covered by
    the caller's ClassSubjectAssignment rows.
    """

    permission_classes = [IsTeacher]

    def get(self, request, *args, **kwargs):
        qs = filter_components_for_teacher(
            AssessmentComponent.objects.select_related(
                'subject',
                'class_level',
                'term',
                'term__session',
            ),
            request.user,
        )

        # Optional narrowing filters (must still be within assignment scope).
        subject = request.query_params.get('subject')
        class_level = request.query_params.get('class_level')
        term = request.query_params.get('term')
        if subject:
            qs = qs.filter(subject_id=subject)
        if class_level:
            qs = qs.filter(class_level_id=class_level)
        if term:
            qs = qs.filter(term_id=term)

        qs = qs.order_by(
            'term__start_date',
            'class_level__name',
            'subject__name',
            'name',
        )
        data = AssessmentComponentSerializer(qs, many=True).data
        return Response({'count': len(data), 'results': data})


class ScoreViewSet(viewsets.ModelViewSet):
    """
    Score entry for assigned teachers (and admin override).

    POST /bulk-upsert/ — idempotent batch upsert with per-entry results.
    """

    serializer_class = ScoreSerializer
    permission_classes = [IsAssignedTeacherOrAdmin]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Score.objects.select_related(
            'student',
            'assessment_component',
            'assessment_component__subject',
            'assessment_component__class_level',
            'assessment_component__term',
            'entered_by',
        ).all()
        membership = resolve_request_membership(self.request)
        if membership is None:
            return qs.none()
        if membership.role == SchoolMembership.Role.ADMIN:
            return qs
        if membership.role == SchoolMembership.Role.TEACHER:
            return filter_scores_for_teacher(qs, self.request.user)
        return qs.none()

    def get_assignment_scope(self, obj):
        """Resolve ClassSubjectAssignment scope for IsAssignedTeacherOrAdmin."""
        return assignment_scope_for_score(
            student=obj.student,
            assessment_component=obj.assessment_component,
        )

    @action(detail=False, methods=['post'], url_path='bulk-upsert')
    def bulk_upsert(self, request):
        """
        Upsert an array of {student_id, assessment_component_id, score}.

        Each entry succeeds or fails independently. Re-submitting the same
        payload is safe (unique student+component; no-op scores skip AuditLog).
        """
        serializer = BulkScoreUpsertSerializer(
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


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin read-only view of grade-change audit entries."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsSchoolAdmin]
    queryset = AuditLog.objects.select_related(
        'student',
        'assessment_component',
        'assessment_component__subject',
        'changed_by',
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        student = self.request.query_params.get('student')
        component = self.request.query_params.get('assessment_component')
        if student:
            qs = qs.filter(student_id=student)
        if component:
            qs = qs.filter(assessment_component_id=component)
        return qs


class RecomputeClassResultsView(APIView):
    """
    POST /api/assessment/results/recompute/

    Explicit trigger: recompute TermResult for every enrolled student ×
    scheme subject, then TermResultSummary averages + class ranks for the
    given class_level + arm + term.

    Not automatic on Score save or bulk-upsert — teachers finish mark entry,
    then click recompute so ranks stay stable mid-entry.
    """

    permission_classes = [IsAdminOrTeacher]

    def post(self, request, *args, **kwargs):
        serializer = RecomputeClassResultsSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        summary_data = TermResultSummarySerializer(
            result['summaries'],
            many=True,
        ).data
        return Response(
            {
                'detail': 'Class results recomputed.',
                'class_level': str(result['class_level_id']),
                'arm': str(result['arm_id']),
                'term': str(result['term_id']),
                'students': result['students'],
                'subjects': result['subjects'],
                'term_results_upserted': result['term_results_upserted'],
                'computed_at': result['computed_at'].isoformat(),
                'summaries': summary_data,
            },
            status=status.HTTP_200_OK,
        )


class PublishClassResultsView(APIView):
    """
    POST /api/assessment/results/publish/

    Admin-only release for one class_level + arm + term. Sets
    ``is_published`` and ``published_at`` on every TermResultSummary in
    that group. Email and WhatsApp ``result_published`` notifications are
    queued on commit, and only for summaries that were not already
    published. Teachers and parents cannot call this.
    """

    permission_classes = [IsSchoolAdmin]

    def post(self, request, *args, **kwargs):
        serializer = PublishClassResultsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        if result['newly_published_count']:
            detail = 'Results published.'
        else:
            detail = 'Results were already published.'
        return Response(
            {
                'detail': detail,
                'class_level': str(result['class_level_id']),
                'arm': str(result['arm_id']),
                'term': str(result['term_id']),
                'published_count': result['published_count'],
                'newly_published_count': result['newly_published_count'],
                'students_without_summary': result['students_without_summary'],
                'published_at': result['published_at'].isoformat(),
                'summaries': TermResultSummarySerializer(
                    result['summaries'],
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class StudentTermResultsView(APIView):
    """
    GET /api/assessment/results/student/?student=<uuid>&term=<uuid>

    Returns TermResultSummary + per-subject TermResult breakdown for
    broadsheet / report-card consumption.

    Access: admin (any), teacher (assigned class), parent (linked student).
    Parents receive scores only when the summary ``is_published`` is true.
    Until then the payload has an empty summary and no subject rows.
    Admin and teacher reads include unpublished results.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        membership = resolve_request_membership(request)
        if membership is None:
            raise ValidationError('Active membership at this school is required.')
        if membership.role not in (
            SchoolMembership.Role.ADMIN,
            SchoolMembership.Role.TEACHER,
            SchoolMembership.Role.PARENT,
        ):
            raise ValidationError('You do not have permission to view these results.')

        query = StudentTermResultsQuerySerializer(
            data={
                'student': request.query_params.get('student'),
                'term': request.query_params.get('term'),
            },
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        student = query.validated_data['student']
        term = query.validated_data['term']

        summary = (
            TermResultSummary.objects.select_related('student', 'term')
            .filter(student=student, term=term)
            .first()
        )
        if membership.role == SchoolMembership.Role.PARENT and (
            summary is None or not summary.is_published
        ):
            return Response(_unpublished_parent_results_payload(student, term))

        subject_results = (
            TermResult.objects.select_related('subject', 'term', 'student')
            .filter(student=student, term=term)
            .order_by('subject__name')
        )

        return Response(
            {
                'student': str(student.pk),
                'student_name': f'{student.last_name}, {student.first_name}',
                'term': str(term.pk),
                'term_name': term.name,
                'summary': (
                    TermResultSummarySerializer(summary).data
                    if summary is not None
                    else None
                ),
                'subject_results': TermResultSerializer(
                    subject_results,
                    many=True,
                ).data,
                'stale_hint': (
                    'Ranks and averages reflect the last explicit recompute '
                    '(summary.computed_at / subject_results[].computed_at). '
                    'They do not update automatically when scores change — '
                    'POST /api/assessment/results/recompute/ after mark entry.'
                    if summary is not None
                    else (
                        'No TermResultSummary yet for this student/term. '
                        'Run POST /api/assessment/results/recompute/ for their class.'
                    )
                ),
            }
        )


class BroadsheetView(APIView):
    """
    GET /api/assessment/broadsheet/?class_level=&arm=&term=&subject=

    Read-only score grid for one class arm + term:
    - Teacher: only subjects covered by their ClassSubjectAssignment
    - Admin: all subjects with an AssessmentComponent scheme (optional subject)

    Response is table-ready: ``columns`` (components + subject totals) and
    ``rows`` (students) with ``cells[column.key]`` values — no client-side
    weighted-total math required.
    """

    permission_classes = [IsAdminOrTeacher]

    def get(self, request, *args, **kwargs):
        query = BroadsheetQuerySerializer(
            data={
                'class_level': request.query_params.get('class_level'),
                'arm': request.query_params.get('arm'),
                'term': request.query_params.get('term'),
                'subject': request.query_params.get('subject') or None,
            },
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        payload = query.build()
        membership = query.validated_data['_membership']
        payload['scope'] = membership.role
        return Response(payload)


class TermResultRemarksView(APIView):
    """
    PATCH /api/assessment/results/remarks/

    Edit remarks on an existing TermResultSummary:
    - Teacher: ``teacher_remark`` for students in an assigned class/arm/term
    - Admin: ``admin_remark`` and/or ``teacher_remark`` for any student

    Summary must already exist (from class recompute).
    """

    permission_classes = [IsAdminOrTeacher]

    def patch(self, request, *args, **kwargs):
        serializer = TermResultRemarksSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        summary = serializer.save()
        return Response(
            TermResultSummarySerializer(summary).data,
            status=status.HTTP_200_OK,
        )


class ReportCardPDFView(APIView):
    """
    GET /api/assessment/report-cards/?student=<uuid>&term=<uuid>

    Downloadable WeasyPrint PDF (``Content-Disposition: attachment``).

    Access: admin (any), teacher (assigned class), parent (linked student).
    Parents receive the PDF only when the summary is published. Admin and
    teacher downloads are available before publication.

    Uses materialized TermResult / TermResultSummary — run recompute for the
    class first or the endpoint returns 404 with a clear message. Attendance
    is compute-on-read; when no daily marks exist the PDF shows
    "Attendance data not available" rather than zeros.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        membership = resolve_request_membership(request)
        if membership is None:
            raise ValidationError('Active membership at this school is required.')
        if membership.role not in (
            SchoolMembership.Role.ADMIN,
            SchoolMembership.Role.TEACHER,
            SchoolMembership.Role.PARENT,
        ):
            raise ValidationError(
                'You do not have permission to generate this report card.'
            )

        query = ReportCardQuerySerializer(
            data={
                'student': request.query_params.get('student'),
                'term': request.query_params.get('term'),
            },
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        student = query.validated_data['student']
        term = query.validated_data['term']

        if membership.role == SchoolMembership.Role.PARENT:
            released = TermResultSummary.objects.filter(
                student=student,
                term=term,
                is_published=True,
            ).exists()
            if not released:
                raise NotFound(detail=RESULTS_NOT_PUBLISHED_DETAIL)

        try:
            pdf_bytes = render_report_card_pdf(student=student, term=term)
        except DjangoValidationError as exc:
            messages = getattr(exc, 'messages', None) or [str(exc)]
            raise NotFound(detail=messages[0] if len(messages) == 1 else messages)

        filename = (
            f'report-card-{student.admission_number}-'
            f'{term.name.replace(" ", "")}.pdf'
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = str(len(pdf_bytes))
        return response
