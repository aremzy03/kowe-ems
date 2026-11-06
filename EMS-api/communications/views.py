"""School-admin visibility into notification delivery."""

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from communications.models import NotificationLog
from communications.serializers import (
    NotificationLogListQuerySerializer,
    NotificationLogSerializer,
)
from communications.tasks import requeue_failed_notification
from memberships.permissions import IsSchoolAdmin


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Delivery log for the current school.

    GET  /api/communications/notifications/
    GET  /api/communications/notifications/{id}/
    POST /api/communications/notifications/{id}/resend/

    School admin with a confirmed TOTP device. The queryset is the
    tenant schema HeaderTenantMiddleware already selected — there is no
    Host lookup and no cross-school list.

    List filters (all optional, combined with AND):

    * ``status`` — queued, sent, failed
    * ``trigger_type`` — invoice_generated, payment_confirmed,
      result_published
    * ``channel`` — email, whatsapp
    * ``created_from`` / ``created_to`` — inclusive bounds on
      ``created_at``. A date (YYYY-MM-DD) covers that calendar day in
      Africa/Lagos. A datetime is an exact instant.

    Resend is only for ``failed`` rows. It re-queues that same log
    through Celery after the status write commits. It does not insert
    a new NotificationLog and it does not send inside the request.
    """

    serializer_class = NotificationLogSerializer
    permission_classes = [IsSchoolAdmin]
    queryset = NotificationLog.objects.select_related('recipient').all()

    def get_queryset(self):
        qs = super().get_queryset().order_by('-created_at')
        if getattr(self, 'action', None) != 'list':
            return qs
        query = NotificationLogListQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        if 'status' in data:
            qs = qs.filter(status=data['status'])
        if 'trigger_type' in data:
            qs = qs.filter(trigger_type=data['trigger_type'])
        if 'channel' in data:
            qs = qs.filter(channel=data['channel'])
        if 'created_from' in data:
            qs = qs.filter(created_at__gte=data['created_from'])
        if 'created_to' in data:
            qs = qs.filter(created_at__lte=data['created_to'])
        return qs

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_field)
        try:
            uuid.UUID(str(lookup))
        except (TypeError, ValueError, AttributeError):
            raise NotFound()
        return super().get_object()

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        log = self.get_object()
        try:
            log = requeue_failed_notification(log)
        except DjangoValidationError as exc:
            detail = exc.messages[0] if exc.messages else str(exc)
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotificationLog.DoesNotExist:
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(log).data)
