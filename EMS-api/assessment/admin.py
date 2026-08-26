from django.contrib import admin

from assessment.models import (
    AssessmentComponent,
    AuditLog,
    Score,
    TermResult,
    TermResultSummary,
)


@admin.register(AssessmentComponent)
class AssessmentComponentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'subject',
        'class_level',
        'term',
        'weight_percentage',
        'max_score',
        'created_at',
    )
    list_filter = ('term', 'class_level', 'subject')
    search_fields = ('name', 'subject__name', 'subject__code')
    readonly_fields = ('id', 'created_at')


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'assessment_component',
        'score',
        'entered_by',
        'updated_at',
    )
    list_filter = (
        'assessment_component__term',
        'assessment_component__subject',
        'assessment_component__class_level',
    )
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
        'assessment_component__name',
    )
    readonly_fields = ('id', 'updated_at')
    raw_id_fields = ('student', 'assessment_component', 'entered_by')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'student',
        'assessment_component',
        'old_value',
        'new_value',
        'changed_by',
    )
    list_filter = ('timestamp', 'assessment_component__subject')
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
        'changed_by__email',
    )
    readonly_fields = (
        'id',
        'student',
        'assessment_component',
        'old_value',
        'new_value',
        'changed_by',
        'timestamp',
    )


@admin.register(TermResult)
class TermResultAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'subject',
        'term',
        'computed_score',
        'computed_at',
    )
    list_filter = ('term', 'subject')
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
        'subject__name',
        'subject__code',
    )
    readonly_fields = ('id', 'computed_at')
    raw_id_fields = ('student', 'subject', 'term')


@admin.register(TermResultSummary)
class TermResultSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'term',
        'overall_average',
        'class_position',
        'computed_at',
    )
    list_filter = ('term',)
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
    )
    readonly_fields = ('id', 'computed_at')
    raw_id_fields = ('student', 'term')
