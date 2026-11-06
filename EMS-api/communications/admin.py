from django.contrib import admin

from communications.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'trigger_type',
        'channel',
        'status',
        'recipient',
        'related_object_id',
        'sent_at',
    )
    list_filter = ('status', 'channel', 'trigger_type')
    search_fields = ('recipient__email', 'error_message')
    raw_id_fields = ('recipient',)
    readonly_fields = ('id', 'created_at', 'sent_at')
