from django.urls import path

from accounts.views import (
    CookieTokenLogoutView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieTokenVerifyView,
    CsrfTokenView,
    CurrentUserView,
    TwoFactorEnrollConfirmView,
    TwoFactorEnrollView,
    TwoFactorVerifyView,
)

urlpatterns = [
    path('csrf/', CsrfTokenView.as_view(), name='auth-csrf'),
    path('me/', CurrentUserView.as_view(), name='auth-me'),
    path('login/', CookieTokenObtainPairView.as_view(), name='auth-login'),
    path('refresh/', CookieTokenRefreshView.as_view(), name='auth-refresh'),
    path('logout/', CookieTokenLogoutView.as_view(), name='auth-logout'),
    path('verify/', CookieTokenVerifyView.as_view(), name='auth-verify'),
    path('2fa/verify/', TwoFactorVerifyView.as_view(), name='auth-2fa-verify'),
    path('2fa/enroll/', TwoFactorEnrollView.as_view(), name='auth-2fa-enroll'),
    path(
        '2fa/enroll/confirm/',
        TwoFactorEnrollConfirmView.as_view(),
        name='auth-2fa-enroll-confirm',
    ),
]
