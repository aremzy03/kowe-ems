"""
Recompute TermResult + TermResultSummary for a class/arm/term.

Explicit ops trigger (same logic as POST /api/assessment/results/recompute/).
Never runs automatically on Score save — ranks stay stable until this command
or the API endpoint is invoked.

Usage (tenant schema)::

    python manage.py recompute_class_results \\
        --schema=demo \\
        --class-level=<uuid> \\
        --arm=<uuid> \\
        --term=<uuid>
"""

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from academics.models import Arm, ClassLevel, Term
from assessment.services import recompute_class_term_summaries


class Command(BaseCommand):
    help = (
        'Recompute TermResult and TermResultSummary (including class ranks) '
        'for one class_level + arm + term in a tenant schema.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            required=True,
            help='Tenant schema name (e.g. demo).',
        )
        parser.add_argument(
            '--class-level',
            required=True,
            dest='class_level_id',
            help='ClassLevel UUID.',
        )
        parser.add_argument(
            '--arm',
            required=True,
            dest='arm_id',
            help='Arm UUID.',
        )
        parser.add_argument(
            '--term',
            required=True,
            dest='term_id',
            help='Term UUID.',
        )

    def handle(self, *args, **options):
        schema = options['schema']
        with schema_context(schema):
            try:
                class_level = ClassLevel.objects.get(pk=options['class_level_id'])
            except ClassLevel.DoesNotExist as exc:
                raise CommandError(
                    f'ClassLevel {options["class_level_id"]} not found in schema {schema}.'
                ) from exc
            try:
                arm = Arm.objects.get(pk=options['arm_id'])
            except Arm.DoesNotExist as exc:
                raise CommandError(
                    f'Arm {options["arm_id"]} not found in schema {schema}.'
                ) from exc
            try:
                term = Term.objects.get(pk=options['term_id'])
            except Term.DoesNotExist as exc:
                raise CommandError(
                    f'Term {options["term_id"]} not found in schema {schema}.'
                ) from exc

            if arm.class_level_id != class_level.pk:
                raise CommandError('Arm does not belong to the given class level.')

            result = recompute_class_term_summaries(
                class_level=class_level,
                arm=arm,
                term=term,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Recomputed results for {class_level}/{arm} term={term}: '
                f'{result["students"]} students, {result["subjects"]} subjects, '
                f'{result["term_results_upserted"]} TermResult rows, '
                f'{len(result["summaries"])} summaries '
                f'(at {result["computed_at"].isoformat()}).'
            )
        )
