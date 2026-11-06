"""
Generate a sample report-card PDF for a student+term (WeasyPrint smoke test).

Example (tenant schema required)::

    python manage.py generate_sample_report_card \\
        --schema testacademy \\
        --student <uuid> --term <uuid> \\
        --out /tmp/report-card.pdf
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from academics.models import Student, Term
from assessment.report_cards import render_report_card_pdf


class Command(BaseCommand):
    help = 'Render a WeasyPrint report-card PDF for one student+term.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            required=True,
            help='Tenant schema_name (e.g. testacademy).',
        )
        parser.add_argument('--student', required=True, help='Student UUID.')
        parser.add_argument('--term', required=True, help='Term UUID.')
        parser.add_argument(
            '--out',
            default='report-card-sample.pdf',
            help='Output PDF path (default: report-card-sample.pdf).',
        )

    def handle(self, *args, **options):
        schema = options['schema']
        out_path = Path(options['out']).resolve()

        with schema_context(schema):
            try:
                student = Student.objects.get(pk=options['student'])
            except Student.DoesNotExist as exc:
                raise CommandError(f'Student not found: {options["student"]}') from exc
            try:
                term = Term.objects.select_related('session').get(pk=options['term'])
            except Term.DoesNotExist as exc:
                raise CommandError(f'Term not found: {options["term"]}') from exc

            try:
                pdf = render_report_card_pdf(student=student, term=term)
            except Exception as exc:
                raise CommandError(f'PDF generation failed: {exc}') from exc

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pdf)
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {len(pdf)} bytes → {out_path} '
                f'({student} / {term})'
            )
        )
