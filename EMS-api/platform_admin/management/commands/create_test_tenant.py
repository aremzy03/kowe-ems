"""Create a Tenant + Domain pair for local development."""

import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context, schema_exists

from memberships.models import SchoolMembership
from platform_admin.models import Domain, Tenant

# PostgreSQL identifiers: start with a letter, then letters/digits/underscore.
_SCHEMA_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')
_RESERVED = frozenset(
    {
        get_public_schema_name(),
        'postgres',
        'information_schema',
        'pg_catalog',
        'pg_toast',
    }
)


def subdomain_to_schema_name(subdomain: str) -> str:
    """Derive a valid PostgreSQL schema name from a subdomain label."""
    schema_name = subdomain.strip().lower().replace('-', '_')
    if not _SCHEMA_RE.match(schema_name):
        raise CommandError(
            f'Invalid schema_name {schema_name!r} from subdomain {subdomain!r}. '
            'Use a label starting with a letter, then letters, digits, or hyphens.'
        )
    if schema_name in _RESERVED or schema_name.startswith('pg_'):
        raise CommandError(f'Schema name {schema_name!r} is reserved.')
    return schema_name


class Command(BaseCommand):
    help = (
        'Create a Tenant + Domain for local development. '
        'Example: python manage.py create_test_tenant "Test Academy" testacademy '
        '--admin-email admin@testacademy.local --admin-password "ChangeMe123!"'
    )

    def add_arguments(self, parser):
        parser.add_argument('school_name', help='Display name of the school')
        parser.add_argument(
            'subdomain',
            help='Subdomain label (becomes schema_name and host prefix), e.g. testacademy',
        )
        parser.add_argument(
            '--domain',
            default=None,
            help='Full hostname (default: <subdomain>.localhost)',
        )
        parser.add_argument(
            '--admin-email',
            default=None,
            help=(
                'Email for the first school admin. Creates/reuses the shared User '
                'and a tenant SchoolMembership with role=admin.'
            ),
        )
        parser.add_argument(
            '--admin-password',
            default=None,
            help=(
                'Password for a newly created admin User. Required when '
                '--admin-email is set and that user does not already exist.'
            ),
        )
        parser.add_argument(
            '--admin-first-name',
            default='',
            help='Optional first name for a newly created admin User.',
        )
        parser.add_argument(
            '--admin-last-name',
            default='',
            help='Optional last name for a newly created admin User.',
        )

    def handle(self, *args, **options):
        school_name = options['school_name'].strip()
        subdomain = options['subdomain'].strip().lower()
        if not school_name:
            raise CommandError('school_name cannot be empty.')
        if '.' in subdomain or '/' in subdomain:
            raise CommandError('subdomain must be a single label, e.g. testacademy (not a FQDN).')

        schema_name = subdomain_to_schema_name(subdomain)
        domain_name = (options['domain'] or f'{subdomain}.localhost').strip().lower()
        admin_email = (options['admin_email'] or '').strip() or None
        admin_password = options['admin_password']
        admin_first_name = (options['admin_first_name'] or '').strip()
        admin_last_name = (options['admin_last_name'] or '').strip()

        if admin_password and not admin_email:
            raise CommandError('--admin-password requires --admin-email.')

        if Tenant.objects.filter(schema_name=schema_name).exists() or schema_exists(schema_name):
            raise CommandError(f'Tenant/schema {schema_name!r} already exists.')
        if Domain.objects.filter(domain=domain_name).exists():
            raise CommandError(f'Domain {domain_name!r} is already in use.')

        User = get_user_model()
        admin_user = None
        admin_created = False

        if admin_email:
            admin_email = User.objects.normalize_email(admin_email)
            admin_user = User.objects.filter(email__iexact=admin_email).first()
            if admin_user is None:
                if not admin_password:
                    raise CommandError(
                        'User does not exist; pass --admin-password to create one.'
                    )
                admin_user = User.objects.create_user(
                    email=admin_email,
                    password=admin_password,
                    first_name=admin_first_name,
                    last_name=admin_last_name,
                )
                admin_created = True

        with transaction.atomic():
            tenant = Tenant(schema_name=schema_name, school_name=school_name, is_active=True)
            # TenantMixin.auto_create_schema=True creates the schema and runs tenant migrations.
            tenant.save()
            Domain.objects.create(domain=domain_name, tenant=tenant, is_primary=True)

            if admin_user is not None:
                with schema_context(schema_name):
                    SchoolMembership.objects.create(
                        user=admin_user,
                        role=SchoolMembership.Role.ADMIN,
                        is_active=True,
                    )

        self.stdout.write(self.style.SUCCESS(f'Created tenant {school_name!r}'))
        self.stdout.write(f'  schema_name: {schema_name}')
        self.stdout.write(f'  domain:      {domain_name}')
        if admin_user is not None:
            verb = 'Created' if admin_created else 'Linked existing'
            self.stdout.write(
                f'  admin:       {verb} user {admin_user.email} '
                f'with SchoolMembership role=admin'
            )
        else:
            self.stdout.write(
                '  admin:       (none — pass --admin-email to seed the first school admin)'
            )
        self.stdout.write('')
        self.stdout.write('Local hostname options:')
        self.stdout.write(f'  /etc/hosts:  127.0.0.1  {domain_name}')
        self.stdout.write(
            '  nip.io:      http://<subdomain>.127.0.0.1.nip.io:8000  '
            '(add a Domain row for that host if you use it)'
        )
        self.stdout.write('')
        self.stdout.write(
            'If auto-create did not apply tenant migrations, run:\n'
            '  python manage.py migrate_schemas --tenant'
        )
