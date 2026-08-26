"""Staff invite email helpers (Django email backend; console in local)."""

from django.conf import settings
from django.core.mail import send_mail


def build_staff_invite_accept_url(request, token: str) -> str:
    """
    Link on the current tenant host so the invitee lands in the right school.

    Frontend path is configurable; the API only embeds the token query param.
    """
    path = getattr(settings, 'STAFF_INVITE_ACCEPT_PATH', '/accept-invite')
    if not path.startswith('/'):
        path = f'/{path}'
    base = request.build_absolute_uri('/').rstrip('/')
    return f'{base}{path}?token={token}'


def send_staff_invite_email(*, request, invite, school_name: str) -> str:
    """
    Send the invite email and return the accept URL (useful for tests / logs).

    Locally ``EMAIL_BACKEND`` is the console backend, so the message appears
    in the runserver / manage.py stdout.
    """
    accept_url = build_staff_invite_accept_url(request, invite.token)
    role_label = invite.get_role_display()
    subject = f'You are invited to join {school_name} as {role_label}'
    body = (
        f'You have been invited to join {school_name} as a {role_label}.\n\n'
        f'Accept this invitation by opening the link below '
        f'(expires {invite.expires_at.isoformat()}):\n\n'
        f'{accept_url}\n\n'
        f'If you did not expect this email, you can ignore it.\n'
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[invite.email],
        fail_silently=False,
    )
    return accept_url
