"""Helpers for the httpOnly refresh-token cookie.

Cookie name: ``refresh_token`` (see ``AUTH_REFRESH_COOKIE_NAME``).
Path is ``/api/auth/`` so the cookie is only sent to login/refresh/logout.
Optional ``AUTH_COOKIE_DOMAIN`` shares the cookie across a parent domain;
empty keeps it host-only on the API host.
"""

from django.conf import settings


def set_refresh_cookie(response, refresh_token: str) -> None:
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    kwargs = {
        'key': settings.AUTH_REFRESH_COOKIE_NAME,
        'value': refresh_token,
        'max_age': max_age,
        'httponly': True,
        'secure': settings.AUTH_COOKIE_SECURE,
        'samesite': settings.AUTH_REFRESH_COOKIE_SAMESITE,
        'path': settings.AUTH_REFRESH_COOKIE_PATH,
    }
    domain = getattr(settings, 'AUTH_COOKIE_DOMAIN', None)
    if domain:
        kwargs['domain'] = domain
    response.set_cookie(**kwargs)


def clear_refresh_cookie(response) -> None:
    # Match the original cookie's path / SameSite / Secure so browsers drop it.
    # Django's delete_cookie() does not pass Secure unless the name is __Secure-.
    kwargs = {
        'key': settings.AUTH_REFRESH_COOKIE_NAME,
        'value': '',
        'max_age': 0,
        'expires': 'Thu, 01 Jan 1970 00:00:00 GMT',
        'httponly': True,
        'secure': settings.AUTH_COOKIE_SECURE,
        'samesite': settings.AUTH_REFRESH_COOKIE_SAMESITE,
        'path': settings.AUTH_REFRESH_COOKIE_PATH,
    }
    domain = getattr(settings, 'AUTH_COOKIE_DOMAIN', None)
    if domain:
        kwargs['domain'] = domain
    response.set_cookie(**kwargs)
