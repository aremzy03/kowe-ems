from django.urls import include, path
from rest_framework.routers import DefaultRouter

from attendance.views import (
    AdminAttendanceOverviewView,
    AttendanceAuditLogViewSet,
    ClassAttendanceRegisterView,
    DailyAttendanceViewSet,
    ParentStudentDailyAttendanceView,
    StudentTermAttendanceSummaryView,
)

router = DefaultRouter()
router.register('daily', DailyAttendanceViewSet, basename='daily-attendance')
router.register(
    'audit-logs',
    AttendanceAuditLogViewSet,
    basename='attendance-audit-log',
)

urlpatterns = [
    path(
        'summaries/student/',
        StudentTermAttendanceSummaryView.as_view(),
        name='attendance-student-term-summary',
    ),
    path(
        'parents/daily/',
        ParentStudentDailyAttendanceView.as_view(),
        name='attendance-parent-daily-log',
    ),
    path(
        'admin/overview/',
        AdminAttendanceOverviewView.as_view(),
        name='attendance-admin-overview',
    ),
    path(
        'register/',
        ClassAttendanceRegisterView.as_view(),
        name='attendance-class-register',
    ),
    path('', include(router.urls)),
]
