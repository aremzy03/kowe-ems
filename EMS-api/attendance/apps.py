from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'
    label = 'attendance'
    verbose_name = 'Attendance'

    def ready(self):
        # Register DailyAttendance → AttendanceAuditLog signals.
        import attendance.signals  # noqa: F401
