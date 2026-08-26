from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assessment'
    label = 'assessment'
    verbose_name = 'Assessment'

    def ready(self):
        # Register Score → AuditLog signals.
        import assessment.signals  # noqa: F401
