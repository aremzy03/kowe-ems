from django.contrib import admin

from attendance.models import AttendanceAuditLog, DailyAttendance


@admin.register(DailyAttendance)
class DailyAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'student',
        'class_level',
        'arm',
        'term',
        'status',
        'marked_by',
        'updated_at',
    )
    list_filter = ('status', 'date', 'term', 'class_level')
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
        'remarks',
    )
    readonly_fields = ('id', 'updated_at')
    raw_id_fields = (
        'student',
        'class_level',
        'arm',
        'term',
        'marked_by',
    )


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'student',
        'date',
        'old_status',
        'new_status',
        'changed_by',
    )
    list_filter = ('timestamp', 'date', 'new_status')
    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__admission_number',
        'changed_by__email',
    )
    readonly_fields = (
        'id',
        'student',
        'date',
        'old_status',
        'new_status',
        'changed_by',
        'timestamp',
    )
