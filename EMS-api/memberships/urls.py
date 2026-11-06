from django.urls import path

from memberships.views import (
    ParentSignupView,
    StaffInviteAcceptView,
    StaffInviteCreateView,
)

urlpatterns = [
    path('invites/', StaffInviteCreateView.as_view(), name='staff-invite-create'),
    path(
        'invites/accept/',
        StaffInviteAcceptView.as_view(),
        name='staff-invite-accept',
    ),
    path(
        'parents/signup/',
        ParentSignupView.as_view(),
        name='parent-signup',
    ),
]
