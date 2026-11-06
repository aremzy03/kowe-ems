from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'
    verbose_name = 'Finance'

    def ready(self):
        # Invoice creation and payment success → notification receivers.
        import finance.signals  # noqa: F401
