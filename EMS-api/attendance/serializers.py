from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from academics.models import Arm, ClassLevel, Student, Term
from attendance.models import AttendanceAuditLog, DailyAttendance
from attendance.services import assert_actor_may_mark_attendance, upsert_daily_attendance


def _drf_validation_error(exc):
    """Map Django ValidationError messages into DRF ValidationError."""
    if hasattr(exc, 'message_dict'):
        return serializers.ValidationError(exc.message_dict)
    if hasattr(exc, 'messages'):
        return serializers.ValidationError(list(exc.messages))
    return serializers.ValidationError(str(exc))


class DailyAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_level_name = serializers.CharField(
        source='class_level.name',
        read_only=True,
    )
    arm_name = serializers.CharField(source='arm.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    marked_by_email = serializers.EmailField(
        source='marked_by.email',
        read_only=True,
    )

    class Meta:
        model = DailyAttendance
        fields = (
            'id',
            'student',
            'student_name',
            'class_level',
            'class_level_name',
            'arm',
            'arm_name',
            'term',
            'term_name',
            'date',
            'status',
            'remarks',
            'marked_by',
            'marked_by_email',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'marked_by',
            'updated_at',
            'student_name',
            'class_level_name',
            'arm_name',
            'term_name',
            'marked_by_email',
        )

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'


class BulkAttendanceEntrySerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=DailyAttendance.Status.choices)
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )


class BulkAttendanceUpsertSerializer(serializers.Serializer):
    """
    Bulk idempotent upsert for one class/arm/term/date register.

    Each entry succeeds or fails independently. Re-submitting the same
    payload is safe (unique student+date; no-op rows skip audit).
    """

    class_level_id = serializers.UUIDField()
    arm_id = serializers.UUIDField()
    term_id = serializers.UUIDField()
    date = serializers.DateField()
    entries = BulkAttendanceEntrySerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        try:
            class_level = ClassLevel.objects.get(pk=attrs['class_level_id'])
        except ClassLevel.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'class_level_id': 'Class level not found.'}
            ) from exc
        try:
            arm = Arm.objects.select_related('class_level').get(pk=attrs['arm_id'])
        except Arm.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'arm_id': 'Arm not found.'}
            ) from exc
        try:
            term = Term.objects.select_related('session').get(pk=attrs['term_id'])
        except Term.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'term_id': 'Term not found.'}
            ) from exc

        if arm.class_level_id != class_level.pk:
            raise serializers.ValidationError(
                {'arm_id': 'Arm does not belong to the given class level.'}
            )

        attrs['class_level'] = class_level
        attrs['arm'] = arm
        attrs['term'] = term
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        class_level = validated_data['class_level']
        arm = validated_data['arm']
        term = validated_data['term']
        attendance_date = validated_data['date']
        results = []

        for entry in validated_data['entries']:
            student_id = entry['student_id']
            status_value = entry['status']
            remarks = entry.get('remarks', '')
            base = {
                'student_id': str(student_id),
                'status': status_value,
                'remarks': remarks,
                'date': attendance_date.isoformat(),
            }
            try:
                try:
                    student = Student.objects.get(pk=student_id)
                except Student.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {'student_id': 'Student not found.'}
                    ) from exc

                assert_actor_may_mark_attendance(
                    request=request,
                    student=student,
                    class_level_id=class_level.pk,
                    arm_id=arm.pk,
                    term_id=term.pk,
                    attendance_date=attendance_date,
                )
                obj, created, changed = upsert_daily_attendance(
                    student=student,
                    class_level=class_level,
                    arm=arm,
                    term=term,
                    attendance_date=attendance_date,
                    status=status_value,
                    marked_by=request.user,
                    remarks=remarks,
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


class AttendanceAuditLogSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    changed_by_email = serializers.EmailField(
        source='changed_by.email',
        read_only=True,
    )

    class Meta:
        model = AttendanceAuditLog
        fields = (
            'id',
            'student',
            'student_name',
            'date',
            'old_status',
            'new_status',
            'changed_by',
            'changed_by_email',
            'timestamp',
        )
        read_only_fields = fields

    def get_student_name(self, obj):
        return f'{obj.student.last_name}, {obj.student.first_name}'


class StudentTermAttendanceQuerySerializer(serializers.Serializer):
    """Query params for GET student termly attendance summary."""

    student = serializers.UUIDField()
    term = serializers.UUIDField()


class ParentDailyAttendanceQuerySerializer(serializers.Serializer):
    """
    Query params for parent daily attendance log.

    ``student`` is required. Optionally filter by ``term``, a single ``date``,
    or ``date_from``/``date_to``.
    """

    student = serializers.UUIDField()
    term = serializers.UUIDField(required=False)
    date = serializers.DateField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        has_range = 'date_from' in attrs or 'date_to' in attrs
        if has_range and ('date_from' not in attrs or 'date_to' not in attrs):
            raise serializers.ValidationError(
                'Provide both date_from and date_to, or neither.'
            )
        if has_range and attrs.get('date'):
            raise serializers.ValidationError(
                'Use either date or date_from/date_to, not both.'
            )
        if has_range and attrs['date_to'] < attrs['date_from']:
            raise serializers.ValidationError(
                {'date_to': 'Must be on or after date_from.'}
            )
        if attrs.get('term'):
            try:
                attrs['term_obj'] = Term.objects.select_related('session').get(
                    pk=attrs['term']
                )
            except Term.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {'term': 'Term not found.'}
                ) from exc
        try:
            attrs['student_obj'] = Student.objects.get(pk=attrs['student'])
        except Student.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'student': 'Student not found.'}
            ) from exc
        return attrs


class AdminAttendanceOverviewQuerySerializer(serializers.Serializer):
    """Query params for admin school-wide attendance overview."""

    date = serializers.DateField(required=False)
    term = serializers.UUIDField(required=False)

    def validate(self, attrs):
        has_date = 'date' in attrs
        has_term = 'term' in attrs
        if has_date == has_term:
            raise serializers.ValidationError(
                'Provide exactly one of date or term.'
            )
        if has_term:
            try:
                attrs['term_obj'] = Term.objects.select_related('session').get(
                    pk=attrs['term']
                )
            except Term.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {'term': 'Term not found.'}
                ) from exc
        return attrs


class ClassRegisterQuerySerializer(serializers.Serializer):
    """Query params for GET class-wide attendance register grid."""

    class_level = serializers.UUIDField()
    arm = serializers.UUIDField()
    term = serializers.UUIDField()
    month = serializers.CharField(required=False, allow_blank=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        has_range = 'date_from' in attrs or 'date_to' in attrs
        if has_range and ('date_from' not in attrs or 'date_to' not in attrs):
            raise serializers.ValidationError(
                'Provide both date_from and date_to, or neither.'
            )
        if has_range and attrs.get('month'):
            raise serializers.ValidationError(
                'Use either month=YYYY-MM or date_from/date_to, not both.'
            )
        try:
            class_level = ClassLevel.objects.get(pk=attrs['class_level'])
        except ClassLevel.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'class_level': 'Class level not found.'}
            ) from exc
        try:
            arm = Arm.objects.select_related('class_level').get(pk=attrs['arm'])
        except Arm.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'arm': 'Arm not found.'}
            ) from exc
        try:
            term = Term.objects.select_related('session').get(pk=attrs['term'])
        except Term.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'term': 'Term not found.'}
            ) from exc
        if arm.class_level_id != class_level.pk:
            raise serializers.ValidationError(
                {'arm': 'Arm does not belong to the given class level.'}
            )
        attrs['class_level_obj'] = class_level
        attrs['arm_obj'] = arm
        attrs['term_obj'] = term
        return attrs
