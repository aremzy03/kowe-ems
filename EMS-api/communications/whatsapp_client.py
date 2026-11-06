"""
WhatsApp Cloud API client (Graph API). No BSP SDK.

Sends one pre-approved template. Phone numbers are digits only, no
leading plus, which is what the messages endpoint expects.
"""

import logging

import requests
from django.conf import settings

from communications.exceptions import (
    PermanentNotificationError,
    TransientNotificationError,
)

logger = logging.getLogger(__name__)

# Rate limits and temporary Graph faults. Everything else in a 4xx body
# (bad template, bad parameter, undeliverable number) is permanent.
# 131056 is the pair-rate limit the queue is built to avoid.
TRANSIENT_ERROR_CODES = frozenset({
    1,
    2,
    4,
    80007,
    130429,
    131048,
    131049,
    131056,
    133004,
})


class WhatsAppCloudClient:
    """POST ``/{phone-number-id}/messages`` with a template payload."""

    def send_template(self, *, to_e164, template_name, language, body_parameters):
        token = (getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '') or '').strip()
        phone_number_id = (
            getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '') or ''
        ).strip()
        if not token or not phone_number_id:
            raise PermanentNotificationError(
                'WhatsApp Cloud API is not configured '
                '(set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID).'
            )
        to_digits = str(to_e164).lstrip('+')
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to_digits,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language},
                'components': [
                    {
                        'type': 'body',
                        'parameters': [
                            {'type': 'text', 'text': value}
                            for value in body_parameters
                        ],
                    },
                ],
            },
        }
        try:
            response = requests.post(
                _messages_url(phone_number_id),
                headers={
                    'Authorization': 'Bearer %s' % token,
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=getattr(settings, 'WHATSAPP_TIMEOUT', 30),
            )
        except requests.RequestException as exc:
            raise TransientNotificationError(
                'WhatsApp could not be reached: %s' % exc
            ) from exc
        return _raise_for_response(response, to_digits, template_name)


def _messages_url(phone_number_id):
    base = (
        getattr(settings, 'WHATSAPP_API_BASE_URL', 'https://graph.facebook.com')
        or 'https://graph.facebook.com'
    ).rstrip('/')
    version = (getattr(settings, 'WHATSAPP_API_VERSION', 'v21.0') or 'v21.0').strip()
    if version and not version.startswith('v'):
        version = 'v' + version
    return '%s/%s/%s/messages' % (base, version, phone_number_id)


def _raise_for_response(response, to_digits, template_name):
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    error = body.get('error') if isinstance(body.get('error'), dict) else None
    if response.ok and error is None:
        logger.info(
            'WhatsApp template %s accepted (…%s)',
            template_name,
            to_digits[-4:],
        )
        return body

    code = _error_code(error)
    message = _error_message(error) or 'HTTP %s' % response.status_code
    summary = (
        'WhatsApp error %s: %s' % (code, message)
        if code is not None
        else 'WhatsApp error: %s' % message
    )
    transient = (
        response.status_code in (408, 429)
        or response.status_code >= 500
        or code in TRANSIENT_ERROR_CODES
    )
    if transient:
        raise TransientNotificationError(summary)
    raise PermanentNotificationError(summary)


def _error_code(error):
    if not error:
        return None
    try:
        return int(error.get('code'))
    except (TypeError, ValueError):
        return None


def _error_message(error):
    if not error:
        return ''
    return str(error.get('message') or '').strip()
