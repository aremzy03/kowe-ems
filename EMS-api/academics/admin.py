from django.contrib import admin

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


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('id',)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'session',
        'start_date',
        'end_date',
        'total_school_days',
        'is_active',
    )
    list_filter = ('is_active', 'name', 'session')
    search_fields = ('session__name',)
    readonly_fields = ('id',)
    raw_id_fields = ('session',)


@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    readonly_fields = ('id',)


@admin.register(Arm)
class ArmAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_level')
    list_filter = ('class_level',)
    search_fields = ('name', 'class_level__name')
    readonly_fields = ('id',)
    raw_id_fields = ('class_level',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')
    readonly_fields = ('id',)


@admin.register(ClassSubjectAssignment)
class ClassSubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'teacher',
        'subject',
        'class_level',
        'arm',
        'term',
        'created_at',
    )
    list_filter = ('term', 'class_level', 'subject')
    search_fields = (
        'teacher__email',
        'subject__code',
        'subject__name',
        'class_level__name',
        'arm__name',
    )
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('teacher', 'subject', 'class_level', 'arm', 'term')


@admin.register(ClassTeacherAssignment)
class ClassTeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'teacher',
        'class_level',
        'arm',
        'term',
        'created_at',
    )
    list_filter = ('term', 'class_level')
    search_fields = (
        'teacher__email',
        'class_level__name',
        'arm__name',
    )
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('teacher', 'class_level', 'arm', 'term')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'admission_number',
        'last_name',
        'first_name',
        'gender',
        'admission_date',
    )
    list_filter = ('gender',)
    search_fields = ('admission_number', 'first_name', 'last_name')
    readonly_fields = ('id',)


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'relationship_to_student', 'phone_number')
    list_filter = ('relationship_to_student',)
    search_fields = ('full_name', 'phone_number', 'user__email')
    readonly_fields = ('id',)
    raw_id_fields = ('user',)


@admin.register(StudentGuardianLink)
class StudentGuardianLinkAdmin(admin.ModelAdmin):
    list_display = ('student', 'guardian', 'is_primary_contact')
    list_filter = ('is_primary_contact',)
    search_fields = (
        'student__admission_number',
        'student__last_name',
        'guardian__phone_number',
    )
    readonly_fields = ('id',)
    raw_id_fields = ('student', 'guardian')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'class_level',
        'arm',
        'session',
        'term',
        'status',
        'enrolled_at',
    )
    list_filter = ('status', 'session', 'term', 'class_level')
    search_fields = ('student__admission_number', 'student__last_name')
    readonly_fields = ('id', 'enrolled_at')
    raw_id_fields = ('student', 'class_level', 'arm', 'session', 'term')


@admin.register(StudentLinkingCode)
class StudentLinkingCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'student', 'is_used', 'used_by', 'used_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('code', 'student__admission_number')
    readonly_fields = ('id', 'created_at', 'used_at')
    raw_id_fields = ('student', 'used_by')
