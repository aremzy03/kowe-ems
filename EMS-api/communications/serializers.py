"""Read serializers for the school-admin notification log."""

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

from communications.models import NotificationLog

_FILTER_KEYS = (
    'status',
    'trigger_type',
    'channel',
    'created_from',
    'created_to',
)


class InclusiveDateTimeField(serializers.Field):
    """
    ISO date (YYYY-MM-DD) or datetime.

    A date-only ``end`` bound is the last instant of that calendar day
    in the active timezone, so the day is included. Naive datetimes are
    interpreted in the active timezone (Africa/Lagos).
    """

    def __init__(self, *args, end=False, **kwargs):
        self.end = end
        super().__init__(*args, **kwargs)

    def to_internal_value(self, value):
        if not isinstance(value, str):
            raise serializers.ValidationError(
                'Enter an ISO date (YYYY-MM-DD) or datetime.'
            )
        raw = value.strip()
        if not raw:
            raise serializers.ValidationError(
                'Enter an ISO date (YYYY-MM-DD) or datetime.'
            )
        # Python's fromisoformat accepts YYYY-MM-DD as midnight, so a
        # date-only end bound would stop at 00:00 and drop the rest of
        # the day. Treat strings with no time separator as calendar dates.
        date_only = 'T' not in raw and ' ' not in raw and ':' not in raw
        if date_only:
            day = parse_date(raw)
            if day is None:
                raise serializers.ValidationError(
                    'Enter an ISO date (YYYY-MM-DD) or datetime.'
                )
            clock = time.max if self.end else time.min
            parsed = datetime.combine(day, clock)
        else:
            parsed = parse_datetime(raw)
            if parsed is None:
                raise serializers.ValidationError(
                    'Enter an ISO date (YYYY-MM-DD) or datetime.'
                )
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed


class NotificationLogSerializer(serializers.ModelSerializer):
    """One delivery attempt. Every field is read-only."""

    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = NotificationLog
        fields = (
            'id',
            'recipient',
            'recipient_email',
            'recipient_name',
            'channel',
            'trigger_type',
            'status',
            'related_object_id',
            'error_message',
            'sent_at',
            'created_at',
        )
        read_only_fields = fields

    def get_recipient_name(self, obj):
        return obj.recipient.get_full_name()


class NotificationLogListQuerySerializer(serializers.Serializer):
    """
    Query params for the admin list.

    ``created_from`` / ``created_to`` bound ``created_at`` (when the
    attempt was recorded). Failed rows have no ``sent_at``, so a sent-at
    window would hide the deliveries an admin is looking for.
    ``channel`` is included so a WhatsApp template rejection can be
    separated from email.
    """

    status = serializers.ChoiceField(
        choices=NotificationLog.Status.choices,
        required=False,
    )
    trigger_type = serializers.ChoiceField(
        choices=NotificationLog.TriggerType.choices,
        required=False,
    )
    channel = serializers.ChoiceField(
        choices=NotificationLog.Channel.choices,
        required=False,
    )
    created_from = InclusiveDateTimeField(required=False, end=False)
    created_to = InclusiveDateTimeField(required=False, end=True)

    def to_internal_value(self, data):
        present = {}
        for key in _FILTER_KEYS:
            if key not in data:
                continue
            raw = data.get(key)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            present[key] = text
        return super().to_internal_value(present)

    def validate(self, attrs):
        start = attrs.get('created_from')
        end = attrs.get('created_to')
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError(
                {'created_to': 'Must be on or after created_from.'}
            )
        return attrs
