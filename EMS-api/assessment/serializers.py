from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from academics.models import Arm, ClassLevel, Student, Subject, Term
from assessment.models import (
    WEIGHT_TOTAL_REQUIRED,
    AssessmentComponent,
    AuditLog,
    Score,
    TermResult,
    TermResultSummary,
    validate_scheme_weights_equal_100,
)
from assessment.services import (
    assert_actor_may_enter_score,
    assert_actor_may_recompute_class,
    assert_actor_may_view_broadsheet,
    assert_actor_may_view_student_term_results,
    build_broadsheet,
    clone_scheme,
    publish_class_term_results,
    recompute_class_term_summaries,
    replace_scheme,
    upsert_score,
)
from assessment.report_cards import (
    assert_actor_may_edit_remarks,
    update_term_result_remarks,
)


def _drf_validation_error(exc):
    """Map Django ValidationError messages into DRF ValidationError."""
    if hasattr(exc, 'message_dict'):
        return serializers.ValidationError(exc.message_dict)
    if hasattr(exc, 'messages'):
        return serializers.ValidationError(list(exc.messages))
    return serializers.ValidationError(str(exc))


class AssessmentComponentSerializer(serializers.ModelSerializer):
    """Admin CRUD serializer with scheme weight-sum enforcement."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = AssessmentComponent
        fields = (
            'id',
            'subject',
            'subject_name',
            'subject_code',
            'class_level',
            'class_level_name',
            'term',
            'term_name',
            'name',
            'weight_percentage',
            'max_score',
            'created_at',
        )
        read_only_fields = (
            'id',
            'subject_name',
            'subject_code',
            'class_level_name',
            'term_name',
            'created_at',
        )

    def validate_weight_percentage(self, value):
        if value <= 0:
            raise serializers.ValidationError('Weight must be greater than 0.')
        if value > WEIGHT_TOTAL_REQUIRED:
            raise serializers.ValidationError(
                f'Weight cannot exceed {WEIGHT_TOTAL_REQUIRED}%.'
            )
        return value

    def validate_max_score(self, value):
        if value <= 0:
            raise serializers.ValidationError('Max score must be greater than 0.')
        return value

    def validate(self, attrs):
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        class_level = attrs.get(
            'class_level', getattr(self.instance, 'class_level', None)
        )
        term = attrs.get('term', getattr(self.instance, 'term', None))
        name = attrs.get('name', getattr(self.instance, 'name', None))
        weight = attrs.get(
            'weight_percentage',
            getattr(self.instance, 'weight_percentage', None),
        )

        if subject is None or class_level is None or term is None or weight is None:
            return attrs

        # Unique name within scheme (clearer than IntegrityError).
        if name is not None:
            qs = AssessmentComponent.objects.filter(
                subject=subject,
                class_level=class_level,
                term=term,
                name=name,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        'name': (
                            'A component with this name already exists for this '
                            'subject, class level, and term.'
                        )
                    }
                )

        try:
            validate_scheme_weights_equal_100(
                subject_id=subject.pk,
                class_level_id=class_level.pk,
                term_id=term.pk,
                exclude_pk=self.instance.pk if self.instance is not None else None,
                proposed_weight=weight,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {'weight_percentage': list(exc.messages)}
            ) from exc

        return attrs


class SchemeComponentInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    weight_percentage = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )
    max_score = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )


class SetSchemeSerializer(serializers.Serializer):
    """Atomically replace all components for a subject/class/term scheme."""

    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    class_level = serializers.PrimaryKeyRelatedField(queryset=ClassLevel.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    components = SchemeComponentInputSerializer(many=True, allow_empty=True)

    def validate_components(self, components):
        if not components:
            return components
        total = sum(
            (Decimal(str(c['weight_percentage'])) for c in components),
            Decimal('0'),
        )
        if total != WEIGHT_TOTAL_REQUIRED:
            raise serializers.ValidationError(
                f'Assessment component weights for this subject, class level, and '
                f'term must sum to {WEIGHT_TOTAL_REQUIRED}%. '
                f'Current total would be {total}%.'
            )
        names = [c['name'].strip() for c in components]
        if len(names) != len(set(names)):
            raise serializers.ValidationError(
                'Component names must be unique within a subject/class/term scheme.'
            )
        return components

    def create(self, validated_data):
        try:
            return replace_scheme(
                subject=validated_data['subject'],
                class_level=validated_data['class_level'],
                term=validated_data['term'],
                components=validated_data['components'],
            )
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc


class CloneSchemeSerializer(serializers.Serializer):
    """
    Clone a component scheme from one subject/class/term onto another
    (or from a previous term onto the current one).
    """

    source_subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    source_class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all()
    )
    source_term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    target_subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    target_class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all()
    )
    target_term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    overwrite = serializers.BooleanField(default=False)

    def validate(self, attrs):
        same_target = (
            attrs['source_subject'].pk == attrs['target_subject'].pk
            and attrs['source_class_level'].pk == attrs['target_class_level'].pk
            and attrs['source_term'].pk == attrs['target_term'].pk
        )
        if same_target:
            raise serializers.ValidationError(
                'Source and target scheme must be different.'
            )
        return attrs

    def create(self, validated_data):
        try:
            return clone_scheme(**validated_data)
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc


class ScoreSerializer(serializers.ModelSerializer):
    """Single-score create/update with max_score + assignment checks."""

    student_name = serializers.SerializerMethodField()
    assessment_component_name = serializers.CharField(
        source='assessment_component.name',
        read_only=True,
    )
    entered_by_email = serializers.EmailField(
        source='entered_by.email',
        read_only=True,
    )

    class Meta:
        model = Score
        fields = (
            'id',
            'student',
            'student_name',
            'assessment_component',
            'assessment_component_name',
            'score',
            'entered_by',
            'entered_by_email',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'student_name',
            'assessment_component_name',
            'entered_by',
            'entered_by_email',
            'updated_at',
        )

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'

    def validate_score(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Score cannot be negative.')
        return value

    def validate(self, attrs):
        student = attrs.get('student', getattr(self.instance, 'student', None))
        component = attrs.get(
            'assessment_component',
            getattr(self.instance, 'assessment_component', None),
        )
        score = attrs.get('score', getattr(self.instance, 'score', None))

        if component is not None and score is not None and score > component.max_score:
            raise serializers.ValidationError(
                {
                    'score': (
                        f'Score {score} exceeds max score {component.max_score} '
                        f'for {component.name}.'
                    )
                }
            )

        request = self.context.get('request')
        if request is not None and student is not None and component is not None:
            try:
                assert_actor_may_enter_score(
                    request=request,
                    student=student,
                    assessment_component=component,
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc

        return attrs

    def create(self, validated_data):
        request = self.context['request']
        obj, _created, _changed = upsert_score(
            student=validated_data['student'],
            assessment_component=validated_data['assessment_component'],
            score=validated_data['score'],
            entered_by=request.user,
        )
        return obj

    def update(self, instance, validated_data):
        request = self.context['request']
        student = validated_data.get('student', instance.student)
        component = validated_data.get(
            'assessment_component',
            instance.assessment_component,
        )
        score = validated_data.get('score', instance.score)
        obj, _created, _changed = upsert_score(
            student=student,
            assessment_component=component,
            score=score,
            entered_by=request.user,
        )
        return obj


class BulkScoreEntrySerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    assessment_component_id = serializers.UUIDField()
    score = serializers.DecimalField(max_digits=8, decimal_places=2)


class BulkScoreUpsertSerializer(serializers.Serializer):
    """
    Bulk idempotent upsert: each entry is independent.

    Partial failures return per-entry errors without discarding successes.
    """

    entries = BulkScoreEntrySerializer(many=True, allow_empty=False)

    def create(self, validated_data):
        request = self.context['request']
        results = []

        for entry in validated_data['entries']:
            student_id = entry['student_id']
            component_id = entry['assessment_component_id']
            raw_score = entry['score']
            base = {
                'student_id': str(student_id),
                'assessment_component_id': str(component_id),
                'score': str(raw_score),
            }
            try:
                try:
                    student = Student.objects.get(pk=student_id)
                except Student.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {'student_id': 'Student not found.'}
                    ) from exc
                try:
                    component = AssessmentComponent.objects.select_related(
                        'subject',
                        'class_level',
                        'term',
                    ).get(pk=component_id)
                except AssessmentComponent.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {'assessment_component_id': 'Assessment component not found.'}
                    ) from exc

                assert_actor_may_enter_score(
                    request=request,
                    student=student,
                    assessment_component=component,
                )
                obj, created, changed = upsert_score(
                    student=student,
                    assessment_component=component,
                    score=raw_score,
                    entered_by=request.user,
                )
                results.append(
                    {
                        **base,
                        'success': True,
                        'created': created,
                        'changed': changed,
                        'id': str(obj.id),
                        'updated_at': obj.updated_at.isoformat(),
                    }
                )
            except DjangoValidationError as exc:
                err = _drf_validation_error(exc)
                results.append({**base, 'success': False, 'errors': err.detail})
            except serializers.ValidationError as exc:
                results.append({**base, 'success': False, 'errors': exc.detail})

        return results


class AuditLogSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    assessment_component_name = serializers.CharField(
        source='assessment_component.name',
        read_only=True,
    )
    changed_by_email = serializers.EmailField(
        source='changed_by.email',
        read_only=True,
    )

    class Meta:
        model = AuditLog
        fields = (
            'id',
            'student',
            'student_name',
            'assessment_component',
            'assessment_component_name',
            'old_value',
            'new_value',
            'changed_by',
            'changed_by_email',
            'timestamp',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'


class TermResultSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)

    class Meta:
        model = TermResult
        fields = (
            'id',
            'student',
            'subject',
            'subject_name',
            'subject_code',
            'term',
            'computed_score',
            'computed_at',
        )
        read_only_fields = fields


class TermResultSummarySerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = TermResultSummary
        fields = (
            'id',
            'student',
            'student_name',
            'term',
            'term_name',
            'overall_average',
            'class_position',
            'teacher_remark',
            'admin_remark',
            'computed_at',
            'is_published',
            'published_at',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'


class RecomputeClassResultsSerializer(serializers.Serializer):
    """
    Explicit trigger to recompute TermResult + TermResultSummary for a class.

    Intentionally not automatic on Score save / bulk-upsert — see service docs.
    """

    class_level = serializers.PrimaryKeyRelatedField(queryset=ClassLevel.objects.all())
    arm = serializers.PrimaryKeyRelatedField(queryset=Arm.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())

    def validate(self, attrs):
        arm = attrs['arm']
        class_level = attrs['class_level']
        if arm.class_level_id != class_level.pk:
            raise serializers.ValidationError(
                {'arm': 'Arm does not belong to the given class level.'}
            )

        request = self.context.get('request')
        if request is not None:
            try:
                assert_actor_may_recompute_class(
                    request=request,
                    class_level=class_level,
                    arm=arm,
                    term=attrs['term'],
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc
        return attrs

    def create(self, validated_data):
        try:
            return recompute_class_term_summaries(
                class_level=validated_data['class_level'],
                arm=validated_data['arm'],
                term=validated_data['term'],
            )
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc


class PublishClassResultsSerializer(serializers.Serializer):
    """
    Admin release of one class arm's term results.

    Does not recompute. Summaries must already exist from
    ``POST /api/assessment/results/recompute/``.
    """

    class_level = serializers.PrimaryKeyRelatedField(queryset=ClassLevel.objects.all())
    arm = serializers.PrimaryKeyRelatedField(queryset=Arm.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())

    def validate(self, attrs):
        if attrs['arm'].class_level_id != attrs['class_level'].pk:
            raise serializers.ValidationError(
                {'arm': 'Arm does not belong to the given class level.'}
            )
        return attrs

    def create(self, validated_data):
        try:
            return publish_class_term_results(
                class_level=validated_data['class_level'],
                arm=validated_data['arm'],
                term=validated_data['term'],
            )
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc


class StudentTermResultsQuerySerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())

    def validate(self, attrs):
        request = self.context.get('request')
        if request is not None:
            try:
                assert_actor_may_view_student_term_results(
                    request=request,
                    student=attrs['student'],
                    term=attrs['term'],
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc
        return attrs


class BroadsheetQuerySerializer(serializers.Serializer):
    """
    GET query params for the teacher/admin broadsheet grid.

    Optional ``subject`` narrows columns; teachers may only request subjects
    covered by their ClassSubjectAssignment for this class/arm/term.
    """

    class_level = serializers.PrimaryKeyRelatedField(queryset=ClassLevel.objects.all())
    arm = serializers.PrimaryKeyRelatedField(queryset=Arm.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        arm = attrs['arm']
        class_level = attrs['class_level']
        if arm.class_level_id != class_level.pk:
            raise serializers.ValidationError(
                {'arm': 'Arm does not belong to the given class level.'}
            )

        request = self.context.get('request')
        if request is not None:
            try:
                membership, allowed_subject_ids = assert_actor_may_view_broadsheet(
                    request=request,
                    class_level=class_level,
                    arm=arm,
                    term=attrs['term'],
                    subject=attrs.get('subject'),
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc
            attrs['_membership'] = membership
            attrs['_allowed_subject_ids'] = allowed_subject_ids
        return attrs

    def build(self):
        """Produce the table-ready broadsheet payload after ``is_valid``."""
        data = self.validated_data
        return build_broadsheet(
            class_level=data['class_level'],
            arm=data['arm'],
            term=data['term'],
            subject_ids=data.get('_allowed_subject_ids'),
            subject=data.get('subject'),
        )


class ReportCardQuerySerializer(serializers.Serializer):
    """
    Query params for PDF report card download.

    Access mirrors student term results (admin / assigned teacher / linked parent).
    PDF content uses materialized TermResult + TermResultSummary — recompute
    must already have been run for the student's class.
    """

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())

    def validate(self, attrs):
        request = self.context.get('request')
        if request is not None:
            try:
                assert_actor_may_view_student_term_results(
                    request=request,
                    student=attrs['student'],
                    term=attrs['term'],
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc
        return attrs


class TermResultRemarksSerializer(serializers.Serializer):
    """
    PATCH remarks on an existing TermResultSummary.

    Teacher: ``teacher_remark`` only (assigned class).
    Admin: ``admin_remark`` and/or ``teacher_remark``.
    """

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    teacher_remark = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )
    admin_remark = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )

    def validate(self, attrs):
        fields = set()
        if 'teacher_remark' in self.initial_data:
            fields.add('teacher_remark')
        if 'admin_remark' in self.initial_data:
            fields.add('admin_remark')

        request = self.context.get('request')
        if request is not None:
            try:
                assert_actor_may_edit_remarks(
                    request=request,
                    student=attrs['student'],
                    term=attrs['term'],
                    fields=fields,
                )
            except DjangoValidationError as exc:
                raise _drf_validation_error(exc) from exc
        attrs['_remark_fields'] = fields
        return attrs

    def save(self, **kwargs):
        data = self.validated_data
        fields = data['_remark_fields']
        try:
            return update_term_result_remarks(
                student=data['student'],
                term=data['term'],
                teacher_remark=(
                    data['teacher_remark'] if 'teacher_remark' in fields else None
                ),
                admin_remark=(
                    data['admin_remark'] if 'admin_remark' in fields else None
                ),
            )
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc
