"""Failures raised by channel senders (email, WhatsApp).

Prompt 1 only defines the types. Prompts 2–3 raise them from the real
senders. The Celery task decides retry vs. fail from the type — it does
not inspect HTTP status codes itself.
"""


class NotificationSendError(Exception):
    """A channel could not deliver this notification."""


class TransientNotificationError(NotificationSendError):
    """Network error or rate limit. Safe to retry with backoff."""


class PermanentNotificationError(NotificationSendError):
    """Invalid destination or rejected template. Do not retry."""
