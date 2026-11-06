"""Serializers for academic CRUD and parent linking-code redemption."""

from django.db import transaction
from rest_framework import serializers

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
    StudentLinkingCode,
    Subject,
    Term,
)
from memberships.models import SchoolMembership


# ---------------------------------------------------------------------------
# Parent linking-code redemption (Prompt 4)
# ---------------------------------------------------------------------------


class LinkingCodeRedeemSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
    relationship_to_student = serializers.ChoiceField(
        choices=Guardian.Relationship.choices,
        required=False,
        default=Guardian.Relationship.GUARDIAN,
    )

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        code = attrs['code']
        try:
            linking_code = StudentLinkingCode.objects.select_related('student').get(
                code=code
            )
        except StudentLinkingCode.DoesNotExist:
            # Same message for missing/used — avoid confirming which codes exist.
            raise serializers.ValidationError(
                {'code': 'Invalid or already used linking code.'}
            )

        if linking_code.is_used:
            raise serializers.ValidationError(
                {'code': 'Invalid or already used linking code.'}
            )

        if linking_code.student_id is None:
            raise serializers.ValidationError(
                {'code': 'Invalid or already used linking code.'}
            )

        attrs['linking_code'] = linking_code
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        request = self.context['request']
        # Lock only the linking-code row. select_related('student') + FOR UPDATE
        # fails on Postgres when student is a nullable FK (outer join).
        linking_code = StudentLinkingCode.objects.select_for_update().get(
            pk=self.validated_data['linking_code'].pk
        )

        if linking_code.is_used or linking_code.student_id is None:
            raise serializers.ValidationError(
                {'code': 'Invalid or already used linking code.'}
            )

        linking_code.redeem_for_parent(
            request.user,
            relationship=self.validated_data.get(
                'relationship_to_student',
                Guardian.Relationship.GUARDIAN,
            ),
        )
        return linking_code


# ---------------------------------------------------------------------------
# Admin-facing academic structure CRUD (Prompt 6)
# ---------------------------------------------------------------------------


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ('id', 'name', 'start_date', 'end_date', 'is_active')
        read_only_fields = ('id',)

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': 'End date must be on or after start date.'}
            )
        return attrs


class TermSerializer(serializers.ModelSerializer):
    session_name = serializers.CharField(source='session.name', read_only=True)

    class Meta:
        model = Term
        fields = (
            'id',
            'session',
            'session_name',
            'name',
            'start_date',
            'end_date',
            'is_active',
            'total_school_days',
        )
        read_only_fields = ('id', 'session_name')

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': 'End date must be on or after start date.'}
            )
        return attrs


class ClassLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassLevel
        fields = ('id', 'name')
        read_only_fields = ('id',)


class ArmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arm
        fields = ('id', 'class_level', 'name')
        read_only_fields = ('id',)


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ('id', 'name', 'code')
        read_only_fields = ('id',)


class InitialGuardianSerializer(serializers.Serializer):
    """
    Optional nested payload when creating a Student.

    Creates a Guardian without a User so the admin can capture name/phone
    before the parent signs up and redeems the linking code.
    """

    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True, default=''
    )
    relationship_to_student = serializers.ChoiceField(
        choices=Guardian.Relationship.choices,
        required=False,
        default=Guardian.Relationship.GUARDIAN,
    )
    is_primary_contact = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        name = (attrs.get('full_name') or '').strip()
        phone = (attrs.get('phone_number') or '').strip()
        if not name and not phone:
            raise serializers.ValidationError(
                'Provide at least full_name or phone_number for the guardian.'
            )
        attrs['full_name'] = name
        attrs['phone_number'] = phone
        return attrs


class StudentSerializer(serializers.ModelSerializer):
    """
    Student CRUD. On create, uses ``Student.objects.create_with_linking_code``
    and optionally pre-creates a Guardian + StudentGuardianLink.
    """

    linking_code = serializers.SerializerMethodField(read_only=True)
    guardian = InitialGuardianSerializer(required=False, write_only=True)

    class Meta:
        model = Student
        fields = (
            'id',
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'admission_number',
            'admission_date',
            'linking_code',
            'guardian',
        )
        read_only_fields = ('id', 'linking_code')

    def get_linking_code(self, obj):
        code = (
            obj.linking_codes.filter(is_used=False)
            .order_by('-created_at')
            .values_list('code', flat=True)
            .first()
        )
        return code

    @transaction.atomic
    def create(self, validated_data):
        guardian_data = validated_data.pop('guardian', None)
        student = Student.objects.create_with_linking_code(**validated_data)

        if guardian_data is not None:
            guardian = Guardian.objects.create(
                full_name=guardian_data.get('full_name', ''),
                phone_number=guardian_data.get('phone_number', ''),
                relationship_to_student=guardian_data.get(
                    'relationship_to_student',
                    Guardian.Relationship.GUARDIAN,
                ),
                user=None,
            )
            StudentGuardianLink.objects.create(
                student=student,
                guardian=guardian,
                is_primary_contact=guardian_data.get('is_primary_contact', True),
            )

        return student


# ---------------------------------------------------------------------------
# Guardian + StudentGuardianLink (admin contact maintenance)
# ---------------------------------------------------------------------------


class GuardianSerializer(serializers.ModelSerializer):
    """
    Tenant-scoped guardian contact.

    ``Guardian`` has no email column — parent email lives on the linked
    ``User`` after signup/redeem, exposed here as read-only ``user_email``.
    """

    user_email = serializers.SerializerMethodField()

    class Meta:
        model = Guardian
        fields = (
            'id',
            'full_name',
            'phone_number',
            'relationship_to_student',
            'user',
            'user_email',
        )
        read_only_fields = ('id', 'user', 'user_email')

    def get_user_email(self, obj):
        user = getattr(obj, 'user', None)
        return user.email if user is not None else None

    def validate(self, attrs):
        name = (
            attrs.get('full_name', getattr(self.instance, 'full_name', None) or '')
            or ''
        ).strip()
        phone = (
            attrs.get(
                'phone_number', getattr(self.instance, 'phone_number', None) or ''
            )
            or ''
        ).strip()
        if 'full_name' in attrs:
            attrs['full_name'] = name
        if 'phone_number' in attrs:
            attrs['phone_number'] = phone
        if not name and not phone:
            raise serializers.ValidationError(
                'Provide at least full_name or phone_number for the guardian.'
            )
        return attrs


def _ensure_single_primary_contact(link):
    """At most one primary StudentGuardianLink per student."""
    if not link.is_primary_contact:
        return
    StudentGuardianLink.objects.filter(
        student_id=link.student_id,
        is_primary_contact=True,
    ).exclude(pk=link.pk).update(is_primary_contact=False)


class StudentGuardianLinkSerializer(serializers.ModelSerializer):
    """Admin link between an existing Guardian and a Student."""

    student_name = serializers.SerializerMethodField()
    guardian_full_name = serializers.CharField(
        source='guardian.full_name', read_only=True
    )
    guardian_phone_number = serializers.CharField(
        source='guardian.phone_number', read_only=True
    )
    relationship_to_student = serializers.CharField(
        source='guardian.relationship_to_student',
        read_only=True,
    )
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = StudentGuardianLink
        fields = (
            'id',
            'student',
            'student_name',
            'guardian',
            'guardian_full_name',
            'guardian_phone_number',
            'relationship_to_student',
            'user_email',
            'is_primary_contact',
        )
        read_only_fields = (
            'id',
            'student_name',
            'guardian_full_name',
            'guardian_phone_number',
            'relationship_to_student',
            'user_email',
        )
        # Custom validate() surfaces a clearer duplicate-link message than
        # DRF's auto UniqueTogetherValidator for uniq_student_guardian_link.
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields['student'].read_only = True
            self.fields['guardian'].read_only = True

    def get_student_name(self, obj):
        student = obj.student
        return f'{student.first_name} {student.last_name}'.strip()

    def get_user_email(self, obj):
        user = getattr(obj.guardian, 'user', None)
        return user.email if user is not None else None

    def validate(self, attrs):
        student = attrs.get('student', getattr(self.instance, 'student', None))
        guardian = attrs.get('guardian', getattr(self.instance, 'guardian', None))
        if student is not None and guardian is not None:
            qs = StudentGuardianLink.objects.filter(
                student=student, guardian=guardian
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'This guardian is already linked to this student.'
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        link = super().create(validated_data)
        _ensure_single_primary_contact(link)
        return link

    @transaction.atomic
    def update(self, instance, validated_data):
        link = super().update(instance, validated_data)
        _ensure_single_primary_contact(link)
        return link


class StudentGuardianLinkNestedSerializer(serializers.ModelSerializer):
    """Read-only guardian-link summary nested on student retrieve/create."""

    guardian_full_name = serializers.CharField(
        source='guardian.full_name', read_only=True
    )
    guardian_phone_number = serializers.CharField(
        source='guardian.phone_number', read_only=True
    )
    relationship_to_student = serializers.CharField(
        source='guardian.relationship_to_student',
        read_only=True,
    )
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = StudentGuardianLink
        fields = (
            'id',
            'guardian',
            'guardian_full_name',
            'guardian_phone_number',
            'relationship_to_student',
            'user_email',
            'is_primary_contact',
        )
        read_only_fields = fields

    def get_user_email(self, obj):
        user = getattr(obj.guardian, 'user', None)
        return user.email if user is not None else None


class StudentDetailSerializer(StudentSerializer):
    """Student retrieve/create: unused linking code plus linked guardians."""

    guardian_links = StudentGuardianLinkNestedSerializer(many=True, read_only=True)

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + ('guardian_links',)
        read_only_fields = StudentSerializer.Meta.read_only_fields + (
            'guardian_links',
        )


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(
        source='student.admission_number',
        read_only=True,
    )
    class_level_name = serializers.CharField(
        source='class_level.name',
        read_only=True,
    )
    arm_name = serializers.CharField(source='arm.name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Enrollment
        fields = (
            'id',
            'student',
            'student_name',
            'student_admission_number',
            'class_level',
            'class_level_name',
            'arm',
            'arm_name',
            'session',
            'session_name',
            'term',
            'term_name',
            'enrolled_at',
            'status',
        )
        read_only_fields = (
            'id',
            'student_name',
            'student_admission_number',
            'class_level_name',
            'arm_name',
            'session_name',
            'term_name',
            'enrolled_at',
        )
        # DRF auto-maps UniqueConstraint(student, session, term) without honouring
        # the ``status=active`` condition — that would block legitimate re-enrolls
        # after withdraw. Custom validate() + DB partial unique index enforce it.
        validators = []

    def get_student_name(self, obj):
        student = obj.student
        return f'{student.first_name} {student.last_name}'.strip()

    def validate(self, attrs):
        # Merge with instance on partial update so cross-field checks still work.
        student = attrs.get('student', getattr(self.instance, 'student', None))
        class_level = attrs.get(
            'class_level', getattr(self.instance, 'class_level', None)
        )
        arm = attrs.get('arm', getattr(self.instance, 'arm', None))
        session = attrs.get('session', getattr(self.instance, 'session', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))
        status = attrs.get(
            'status',
            getattr(self.instance, 'status', Enrollment.Status.ACTIVE),
        )

        if arm is not None and class_level is not None:
            if arm.class_level_id != class_level.id:
                raise serializers.ValidationError(
                    {'arm': 'Arm does not belong to the selected class level.'}
                )

        if term is not None and session is not None:
            if term.session_id != session.id:
                raise serializers.ValidationError(
                    {'term': 'Term does not belong to the selected session.'}
                )

        if (
            status == Enrollment.Status.ACTIVE
            and student is not None
            and session is not None
            and term is not None
        ):
            qs = Enrollment.objects.filter(
                student=student,
                session=session,
                term=term,
                status=Enrollment.Status.ACTIVE,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Student already has an active enrollment for this session/term.'
                )

        return attrs


# ---------------------------------------------------------------------------
# Class–subject–teacher assignment (Phase 2 Prompt 1)
# ---------------------------------------------------------------------------


class ClassSubjectAssignmentSerializer(serializers.ModelSerializer):
    """
    Admin CRUD for teacher ↔ subject/class/arm/term assignments.

    ``teacher`` must have an active SchoolMembership with role=teacher in
    this tenant. Arm must belong to the selected class_level.
    """

    teacher_email = serializers.EmailField(source='teacher.email', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    arm_name = serializers.CharField(source='arm.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = ClassSubjectAssignment
        fields = (
            'id',
            'teacher',
            'teacher_email',
            'subject',
            'subject_name',
            'subject_code',
            'class_level',
            'class_level_name',
            'arm',
            'arm_name',
            'term',
            'term_name',
            'created_at',
        )
        read_only_fields = (
            'id',
            'teacher_email',
            'subject_name',
            'subject_code',
            'class_level_name',
            'arm_name',
            'term_name',
            'created_at',
        )

    def validate_teacher(self, teacher):
        membership = SchoolMembership.objects.filter(
            user_id=teacher.pk,
            is_active=True,
            role=SchoolMembership.Role.TEACHER,
        ).first()
        if membership is None:
            raise serializers.ValidationError(
                'Teacher must have an active teacher SchoolMembership at this school.'
            )
        return teacher

    def validate(self, attrs):
        class_level = attrs.get(
            'class_level', getattr(self.instance, 'class_level', None)
        )
        arm = attrs.get('arm', getattr(self.instance, 'arm', None))
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))

        if arm is not None and class_level is not None:
            if arm.class_level_id != class_level.id:
                raise serializers.ValidationError(
                    {'arm': 'Arm does not belong to the selected class level.'}
                )

        # Surface a clear API error before the DB unique constraint fires.
        if (
            subject is not None
            and class_level is not None
            and arm is not None
            and term is not None
        ):
            qs = ClassSubjectAssignment.objects.filter(
                subject=subject,
                class_level=class_level,
                arm=arm,
                term=term,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'This subject is already assigned to a teacher for this '
                    'class/arm/term.'
                )

        return attrs


# ---------------------------------------------------------------------------
# Form / class teacher assignment (Phase 3 Prompt 1)
# ---------------------------------------------------------------------------


class ClassTeacherAssignmentSerializer(serializers.ModelSerializer):
    """
    Admin CRUD for teacher ↔ class/arm/term (form teacher) assignments.

    ``teacher`` must have an active SchoolMembership with role=teacher in
    this tenant. Arm must belong to the selected class_level.

    Independent of ``ClassSubjectAssignment`` — subject teaching and form-
    teacher duties are not auto-linked.
    """

    teacher_email = serializers.EmailField(source='teacher.email', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    arm_name = serializers.CharField(source='arm.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = ClassTeacherAssignment
        fields = (
            'id',
            'teacher',
            'teacher_email',
            'class_level',
            'class_level_name',
            'arm',
            'arm_name',
            'term',
            'term_name',
            'created_at',
        )
        read_only_fields = (
            'id',
            'teacher_email',
            'class_level_name',
            'arm_name',
            'term_name',
            'created_at',
        )

    def validate_teacher(self, teacher):
        membership = SchoolMembership.objects.filter(
            user_id=teacher.pk,
            is_active=True,
            role=SchoolMembership.Role.TEACHER,
        ).first()
        if membership is None:
            raise serializers.ValidationError(
                'Teacher must have an active teacher SchoolMembership at this school.'
            )
        return teacher

    def validate(self, attrs):
        class_level = attrs.get(
            'class_level', getattr(self.instance, 'class_level', None)
        )
        arm = attrs.get('arm', getattr(self.instance, 'arm', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))

        if arm is not None and class_level is not None:
            if arm.class_level_id != class_level.id:
                raise serializers.ValidationError(
                    {'arm': 'Arm does not belong to the selected class level.'}
                )

        # Surface a clear API error before the DB unique constraint fires.
        if class_level is not None and arm is not None and term is not None:
            qs = ClassTeacherAssignment.objects.filter(
                class_level=class_level,
                arm=arm,
                term=term,
            )
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'This class/arm/term already has a class teacher assigned.'
                )

        return attrs
