from django.urls import include, path
from rest_framework.routers import DefaultRouter

from assessment.views import (
    AssessmentComponentViewSet,
    AuditLogViewSet,
    BroadsheetView,
    MyAssessmentComponentsView,
    RecomputeClassResultsView,
    ReportCardPDFView,
    ScoreViewSet,
    StudentTermResultsView,
    TermResultRemarksView,
)

router = DefaultRouter()
router.register(
    'components',
    AssessmentComponentViewSet,
    basename='assessment-component',
)
router.register('scores', ScoreViewSet, basename='score')
router.register('audit-logs', AuditLogViewSet, basename='score-audit-log')

urlpatterns = [
    path(
        'my-components/',
        MyAssessmentComponentsView.as_view(),
        name='my-assessment-components',
    ),
    path(
        'results/recompute/',
        RecomputeClassResultsView.as_view(),
        name='recompute-class-results',
    ),
    path(
        'results/student/',
        StudentTermResultsView.as_view(),
        name='student-term-results',
    ),
    path(
        'results/remarks/',
        TermResultRemarksView.as_view(),
        name='term-result-remarks',
    ),
    path(
        'broadsheet/',
        BroadsheetView.as_view(),
        name='assessment-broadsheet',
    ),
    path(
        'report-cards/',
        ReportCardPDFView.as_view(),
        name='assessment-report-card-pdf',
    ),
    path('', include(router.urls)),
]
