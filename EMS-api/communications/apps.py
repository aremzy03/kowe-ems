from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'
    verbose_name = 'Communications'

    def ready(self):
        # The worker never imports a view. Register both channel senders
        # at startup so send_notification can deliver.
        from communications.email_service import register_email_sender
        from communications.whatsapp_service import register_whatsapp_sender

        register_email_sender()
        register_whatsapp_sender()
