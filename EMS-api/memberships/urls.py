from django.urls import include, path
from rest_framework.routers import DefaultRouter

from memberships.views import (
    ParentSignupView,
    SchoolMembershipViewSet,
    StaffInviteAcceptView,
    StaffInviteViewSet,
)

router = DefaultRouter()
router.register('members', SchoolMembershipViewSet, basename='school-membership')
router.register('invites', StaffInviteViewSet, basename='staff-invite')

urlpatterns = [
    # Explicit path first so "accept" is never treated as an invite PK.
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
    path('', include(router.urls)),
]
