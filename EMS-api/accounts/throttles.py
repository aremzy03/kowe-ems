"""
Auth-endpoint rate limits.

Starting rate is 5/min per IP (AUTH_THROTTLE_RATE). Tunable, not a final
security policy. Applied only on login and token refresh — not globally.
"""

from rest_framework.throttling import SimpleRateThrottle


class AuthEndpointThrottle(SimpleRateThrottle):
    """
    IP-based throttle for brute-force-prone auth views.

    Always keys on client IP (not user id) so refresh stays limited even
    when a Bearer token is present. Rate: REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth'].
    """

    scope = 'auth'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }
