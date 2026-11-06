import secrets
import string
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def _generate_linking_code(length=8):
    """8-char alphanumeric code (uppercase letters + digits), excluding ambiguous chars."""
    alphabet = string.ascii_uppercase + string.digits
    # Drop 0/O/1/I to reduce handoff confusion when admins dictate codes to parents.
    alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Session(models.Model):
    """Academic year / session (e.g. 2026/2027). Tenant-scoped."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uniq_session_name'),
        ]

    def __str__(self):
        return self.name


class Term(models.Model):
    """Term within a session (1st / 2nd / 3rd)."""

    class Name(models.TextChoices):
        FIRST = '1st', '1st'
        SECOND = '2nd', '2nd'
        THIRD = '3rd', '3rd'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='terms',
    )
    name = models.CharField(max_length=10, choices=Name.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False, db_index=True)
    # MVP denominator for attendance % — no academic calendar module yet.
    # Admin sets instructional-day count manually; national/calendar sync is out of scope.
    total_school_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            'Admin-set count of instructional days in this term. '
            'Denominator for attendance percentage. Set manually — there is '
            'no school calendar / holiday module in MVP.'
        ),
    )

    class Meta:
        ordering = ['session', 'start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'name'],
                name='uniq_term_session_name',
            ),
        ]

    def __str__(self):
        return f'{self.session.name} — {self.name}'


class ClassLevel(models.Model):
    """Year group / class level (e.g. JSS1, SS2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uniq_classlevel_name'),
        ]

    def __str__(self):
        return self.name


class Arm(models.Model):
    """Stream / arm within a class level (e.g. A, B)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name='arms',
    )
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ['class_level', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['class_level', 'name'],
                name='uniq_arm_classlevel_name',
            ),
        ]

    def __str__(self):
        return f'{self.class_level.name}{self.name}'


class Subject(models.Model):
    """Subject offered by the school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='uniq_subject_code'),
        ]

    def __str__(self):
        return f'{self.code} — {self.name}'


class ClassSubjectAssignment(models.Model):
    """
    Which teacher teaches which subject to which class arm for a term.

    Tenant-scoped. Foundation for scoping every teacher-facing assessment
    endpoint: a teacher may only enter/view marks for combinations they are
    assigned to here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='class_subject_assignments',
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='class_subject_assignments',
    )
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.PROTECT,
        related_name='class_subject_assignments',
    )
    arm = models.ForeignKey(
        Arm,
        on_delete=models.PROTECT,
        related_name='class_subject_assignments',
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        related_name='class_subject_assignments',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['term', 'class_level', 'arm', 'subject']
        constraints = [
            # One teacher owns a subject for a given arm+term (no double-booking).
            models.UniqueConstraint(
                fields=['subject', 'class_level', 'arm', 'term'],
                name='uniq_csa_subject_class_arm_term',
            ),
        ]

    def __str__(self):
        return (
            f'{self.teacher} → {self.subject} / {self.class_level}{self.arm} '
            f'({self.term})'
        )


class ClassTeacherAssignment(models.Model):
    """
    Which teacher is the form/class teacher for a class arm in a term.

    Tenant-scoped. Distinct from ``ClassSubjectAssignment``: attendance is
    taken once per class/arm/day by the form teacher, who may or may not
    teach any subject in that class. Source of truth for attendance-marking
    authority (Phase 3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='class_teacher_assignments',
    )
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.PROTECT,
        related_name='class_teacher_assignments',
    )
    arm = models.ForeignKey(
        Arm,
        on_delete=models.PROTECT,
        related_name='class_teacher_assignments',
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        related_name='class_teacher_assignments',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['term', 'class_level', 'arm']
        constraints = [
            # One form/class teacher per arm+term (no double-booking).
            models.UniqueConstraint(
                fields=['class_level', 'arm', 'term'],
                name='uniq_cta_class_arm_term',
            ),
        ]

    def __str__(self):
        return (
            f'{self.teacher} → form teacher / {self.class_level}{self.arm} '
            f'({self.term})'
        )


class StudentManager(models.Manager):
    """Manager with helpers for student + linking-code creation."""

    @transaction.atomic
    def create_with_linking_code(self, **kwargs):
        """
        Create a Student and immediately generate an unused linking code.

        Prompt 6 admin Student create should use this (or call
        ``student.generate_unused_linking_code()`` after create).
        """
        student = self.create(**kwargs)
        student.generate_unused_linking_code()
        return student


class Student(models.Model):
    """Learner profile. Tenant-scoped; admission_number unique per school."""

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    admission_number = models.CharField(max_length=50, db_index=True)
    admission_date = models.DateField()

    objects = StudentManager()

    class Meta:
        ordering = ['last_name', 'first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['admission_number'],
                name='uniq_student_admission_number',
            ),
        ]

    def __str__(self):
        return f'{self.last_name}, {self.first_name} ({self.admission_number})'

    def generate_unused_linking_code(self, max_attempts=20):
        """
        Create a new unused ``StudentLinkingCode`` bound to this student.

        Called automatically from ``StudentManager.create_with_linking_code``;
        Prompt 6 Student create / enrollment flows should use that path.
        """
        return StudentLinkingCode.generate_unused(student=self, max_attempts=max_attempts)


class Guardian(models.Model):
    """
    Guardian / parent contact for students in this school.

    ``user`` is the parent account once they have signed up and redeemed a
    linking code. It is nullable so an admin can pre-create a guardian record
    (name/phone) before the parent User exists (Prompt 6).
    """

    class Relationship(models.TextChoices):
        MOTHER = 'mother', 'Mother'
        FATHER = 'father', 'Father'
        GUARDIAN = 'guardian', 'Guardian'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guardians',
    )
    # Set by admin when pre-creating a guardian before the parent User exists.
    full_name = models.CharField(max_length=255, blank=True, default='')
    relationship_to_student = models.CharField(
        max_length=20,
        choices=Relationship.choices,
        default=Relationship.GUARDIAN,
    )
    phone_number = models.CharField(max_length=30, blank=True, default='')

    class Meta:
        ordering = ['full_name', 'phone_number', 'id']
        constraints = [
            # One guardian profile per parent User within a tenant (when linked).
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='uniq_guardian_user_when_set',
            ),
        ]

    def __str__(self):
        if self.user_id:
            who = self.user.email
        else:
            who = self.full_name or self.phone_number or str(self.id)
        return f'{who} ({self.relationship_to_student})'


class StudentGuardianLink(models.Model):
    """
    Actual parent↔student relationship created when a linking code is redeemed
    (or when an admin pre-associates a guardian with a student).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='guardian_links',
    )
    guardian = models.ForeignKey(
        Guardian,
        on_delete=models.CASCADE,
        related_name='student_links',
    )
    is_primary_contact = models.BooleanField(default=False)

    class Meta:
        ordering = ['student', '-is_primary_contact']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'guardian'],
                name='uniq_student_guardian_link',
            ),
        ]

    def __str__(self):
        return f'{self.guardian} ↔ {self.student}'


class Enrollment(models.Model):
    """Student placement in a class arm for a session/term."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        WITHDRAWN = 'withdrawn', 'Withdrawn'
        GRADUATED = 'graduated', 'Graduated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    arm = models.ForeignKey(
        Arm,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    enrolled_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    class Meta:
        ordering = ['-enrolled_at']
        constraints = [
            # At most one active enrollment per student per session+term.
            models.UniqueConstraint(
                fields=['student', 'session', 'term'],
                condition=models.Q(status='active'),
                name='uniq_active_enrollment_student_session_term',
            ),
        ]

    def __str__(self):
        return (
            f'{self.student} → {self.class_level}/{self.arm} '
            f'({self.session} {self.term}) [{self.status}]'
        )


class StudentLinkingCode(models.Model):
    """
    School-issued single-use code that links a parent User to a student.

    Tenant-scoped. Redeeming a code creates/attaches Guardian + StudentGuardianLink.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=8, unique=True, db_index=True)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='linking_codes',
    )
    is_used = models.BooleanField(default=False, db_index=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='redeemed_linking_codes',
    )
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'used' if self.is_used else 'unused'
        return f'{self.code} ({status})'

    @classmethod
    def generate_unused(cls, student=None, max_attempts=20):
        """
        Create a new unused linking code, optionally pre-bound to a Student.

        Prefer ``Student.generate_unused_linking_code()`` /
        ``Student.objects.create_with_linking_code(...)`` from call sites.
        """
        for _ in range(max_attempts):
            code = _generate_linking_code()
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(code=code, student=student)
        raise RuntimeError('Could not generate a unique student linking code.')

    def mark_redeemed(self, user):
        """Mark this code used by ``user``. Caller must hold a row lock."""
        self.is_used = True
        self.used_by = user
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_by', 'used_at'])

    @transaction.atomic
    def redeem_for_parent(self, user, *, relationship=None, is_primary_contact=True):
        """
        Mark code used and establish Guardian + StudentGuardianLink for ``user``.

        Requires ``self.student`` to be set. Caller should ``select_for_update``.
        """
        if self.student_id is None:
            raise ValueError('Linking code is not bound to a student.')
        if self.is_used:
            raise ValueError('Linking code already used.')

        rel = relationship or Guardian.Relationship.GUARDIAN
        guardian, _created = Guardian.objects.get_or_create(
            user=user,
            defaults={
                'relationship_to_student': rel,
            },
        )
        StudentGuardianLink.objects.get_or_create(
            student=self.student,
            guardian=guardian,
            defaults={'is_primary_contact': is_primary_contact},
        )
        self.mark_redeemed(user)
        return guardian
