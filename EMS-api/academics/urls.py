from django.urls import include, path
from rest_framework.routers import DefaultRouter

from academics.views import (
    ArmViewSet,
    ClassLevelViewSet,
    ClassSubjectAssignmentViewSet,
    ClassTeacherAssignmentViewSet,
    EnrollmentViewSet,
    LinkingCodeRedeemView,
    MyClassSubjectAssignmentsView,
    MyClassTeacherAssignmentsView,
    MyStudentsPlaceholderView,
    ParentStudentAccessExampleView,
    SessionViewSet,
    StudentViewSet,
    SubjectViewSet,
    TermViewSet,
)

router = DefaultRouter()
router.register('sessions', SessionViewSet, basename='session')
router.register('terms', TermViewSet, basename='term')
router.register('class-levels', ClassLevelViewSet, basename='class-level')
router.register('arms', ArmViewSet, basename='arm')
router.register('subjects', SubjectViewSet, basename='subject')
router.register('students', StudentViewSet, basename='student')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register(
    'class-subject-assignments',
    ClassSubjectAssignmentViewSet,
    basename='class-subject-assignment',
)
router.register(
    'class-teacher-assignments',
    ClassTeacherAssignmentViewSet,
    basename='class-teacher-assignment',
)

urlpatterns = [
    path(
        'linking-codes/redeem/',
        LinkingCodeRedeemView.as_view(),
        name='linking-code-redeem',
    ),
    path(
        'my-students/',
        MyStudentsPlaceholderView.as_view(),
        name='my-students',
    ),
    path(
        'my-students/<uuid:student_id>/',
        ParentStudentAccessExampleView.as_view(),
        name='parent-student-detail-placeholder',
    ),
    path(
        'my-assignments/',
        MyClassSubjectAssignmentsView.as_view(),
        name='my-assignments',
    ),
    path(
        'my-classes/',
        MyClassTeacherAssignmentsView.as_view(),
        name='my-classes',
    ),
    path('', include(router.urls)),
]
