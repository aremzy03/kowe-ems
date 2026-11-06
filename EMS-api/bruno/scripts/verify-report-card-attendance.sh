#!/usr/bin/env bash
# Confirm report-card HTML attendance section has real numbers (PDF streams
# often omit glyph-decoded digits). Reads student/term from Local.bru.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"

.venv/bin/python <<'PY'
import re
from pathlib import Path

import django

django.setup()

from django_tenants.utils import schema_context
from platform_admin.models import Domain
from academics.models import Student, Term
from assessment.report_cards import (
    get_attendance_summary_for_report,
    render_report_card_html,
)

env = Path('bruno/environments/Local.bru').read_text()
vars_ = dict(re.findall(r'^\s*(\w+):\s*(.+)$', env, re.M))
student_id = vars_['studentId'].strip()
term_id = vars_['termId'].strip()

domain = Domain.objects.select_related('tenant').get(domain='testacademy.localhost')
with schema_context(domain.tenant.schema_name):
    student = Student.objects.get(pk=student_id)
    term = Term.objects.get(pk=term_id)
    att = get_attendance_summary_for_report(student=student, term=term).as_dict()
    html = render_report_card_html(student=student, term=term)

assert att.get('available') is True, att
assert att.get('days_present') == 1, att
assert att.get('total_school_days') == 60, att
assert att.get('attendance_percentage') == '1.67', att
assert 'Attendance summary' in html
assert 'Days present' in html
assert 'Total school days' in html
assert '1.67' in html
assert 'Attendance data not available' not in html
print('OK: report card attendance section shows real data '
      f"(present={att['days_present']}, total={att['total_school_days']}, "
      f"pct={att['attendance_percentage']}%)")
PY
