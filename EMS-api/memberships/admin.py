"""
School memberships live in each tenant schema. The Django admin session is on
the public schema, so the stock ModelAdmin queryset cannot see or save them.

These views switch into the chosen school's schema for reads and writes.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django_tenants.utils import (
    get_public_schema_name,
    schema_context,
    schema_exists,
)

from platform_admin.models import Tenant

from .models import SchoolMembership, StaffInvite

User = get_user_model()


def _schools():
    return (
        Tenant.objects.exclude(schema_name=get_public_schema_name())
        .order_by('school_name', 'schema_name')
    )


def membership_rows(schema_name=None):
    """Memberships across school schemas. Skips a tenant whose schema is missing."""
    rows = []
    for tenant in _schools():
        if schema_name and tenant.schema_name != schema_name:
            continue
        if not schema_exists(tenant.schema_name):
            continue
        with schema_context(tenant.schema_name):
            memberships = list(SchoolMembership.objects.order_by('joined_at'))
            snapshot = [
                {
                    'schema_name': tenant.schema_name,
                    'school_name': tenant.school_name,
                    'id': membership.pk,
                    'user_id': membership.user_id,
                    'role': membership.role,
                    'role_label': membership.get_role_display(),
                    'is_active': membership.is_active,
                    'joined_at': membership.joined_at,
                }
                for membership in memberships
            ]
        rows.extend(snapshot)

    users = User.objects.in_bulk([row['user_id'] for row in rows])
    for row in rows:
        user = users.get(row['user_id'])
        row['email'] = user.email if user is not None else str(row['user_id'])
        row['change_url'] = reverse(
            'admin:memberships_schoolmembership_change',
            args=[row['schema_name'], row['id']],
        )
    return rows


def _load_membership(schema_name, membership_id):
    tenant = (
        Tenant.objects.exclude(schema_name=get_public_schema_name())
        .filter(schema_name=schema_name)
        .first()
    )
    if tenant is None or not schema_exists(schema_name):
        raise Http404('Unknown school.')
    with schema_context(schema_name):
        try:
            membership = SchoolMembership.objects.get(pk=membership_id)
        except SchoolMembership.DoesNotExist:
            raise Http404('Membership not found.')
        data = {
            'schema_name': schema_name,
            'school_name': tenant.school_name,
            'id': membership.pk,
            'user_id': membership.user_id,
            'role': membership.role,
            'is_active': membership.is_active,
        }
    user = User.objects.filter(pk=data['user_id']).first()
    data['email'] = user.email if user is not None else str(data['user_id'])
    return data


class SchoolMembershipAddForm(forms.Form):
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.none(), label='School')
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='User',
        help_text='Create the person under Users first, then attach them to a school.',
    )
    role = forms.ChoiceField(choices=SchoolMembership.Role.choices)
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].queryset = _schools()
        self.fields['user'].queryset = User.objects.order_by('email')
        self.fields['user'].label_from_instance = lambda user: user.email

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get('tenant')
        user = cleaned.get('user')
        if tenant is None or user is None:
            return cleaned
        if not schema_exists(tenant.schema_name):
            raise forms.ValidationError('That school has no database schema yet.')
        with schema_context(tenant.schema_name):
            exists = SchoolMembership.objects.filter(user_id=user.pk).exists()
        if exists:
            raise forms.ValidationError('This user already belongs to that school. Edit the existing membership to change their role.')
        return cleaned

    def save(self):
        tenant = self.cleaned_data['tenant']
        user = self.cleaned_data['user']
        with schema_context(tenant.schema_name):
            membership = SchoolMembership.objects.create(
                user_id=user.pk,
                role=self.cleaned_data['role'],
                is_active=self.cleaned_data['is_active'],
            )
            membership_id = membership.pk
        return tenant.schema_name, membership_id


class SchoolMembershipChangeForm(forms.Form):
    role = forms.ChoiceField(choices=SchoolMembership.Role.choices)
    is_active = forms.BooleanField(required=False)

    def save(self, schema_name, membership_id):
        with schema_context(schema_name):
            membership = SchoolMembership.objects.get(pk=membership_id)
            membership.role = self.cleaned_data['role']
            membership.is_active = self.cleaned_data['is_active']
            membership.save(update_fields=['role', 'is_active'])


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    """Public-schema admin for tenant-schema memberships."""

    list_display = ('user', 'role', 'is_active', 'joined_at')

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name

        def wrap(view):
            return self.admin_site.admin_view(view)

        return [
            path(
                '',
                wrap(self.membership_list),
                name='%s_%s_changelist' % info,
            ),
            path(
                'add/',
                wrap(self.membership_add),
                name='%s_%s_add' % info,
            ),
            path(
                '<str:schema>/<uuid:membership_id>/change/',
                wrap(self.membership_change),
                name='%s_%s_change' % info,
            ),
        ]

    def membership_list(self, request):
        schema = (request.GET.get('schema') or '').strip()
        context = {
            **self.admin_site.each_context(request),
            'title': 'School memberships',
            'opts': self.model._meta,
            'rows': membership_rows(schema or None),
            'schema_filter': schema,
            'add_url': reverse('admin:memberships_schoolmembership_add'),
        }
        return TemplateResponse(
            request,
            'admin/memberships/schoolmembership_changelist.html',
            context,
        )

    def membership_add(self, request):
        if not self.has_add_permission(request):
            messages.error(request, 'You do not have permission to add a membership.')
            return redirect('admin:memberships_schoolmembership_changelist')
        form = SchoolMembershipAddForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            schema_name, membership_id = form.save()
            messages.success(request, 'Membership saved.')
            return redirect(
                'admin:memberships_schoolmembership_change',
                schema=schema_name,
                membership_id=membership_id,
            )
        return self._render_form(
            request,
            form,
            title='Add school membership',
            membership=None,
        )

    def membership_change(self, request, schema, membership_id):
        if not self.has_change_permission(request):
            messages.error(request, 'You do not have permission to change a membership.')
            return redirect('admin:memberships_schoolmembership_changelist')
        membership = _load_membership(schema, membership_id)
        if request.method == 'POST' and request.POST.get('_delete'):
            if not self.has_delete_permission(request):
                messages.error(request, 'You do not have permission to remove a membership.')
                return redirect(
                    'admin:memberships_schoolmembership_change',
                    schema=schema,
                    membership_id=membership_id,
                )
            with schema_context(schema):
                SchoolMembership.objects.filter(pk=membership_id).delete()
            messages.success(request, 'Membership removed from the school.')
            return redirect('admin:memberships_schoolmembership_changelist')

        form = SchoolMembershipChangeForm(
            request.POST or None,
            initial={'role': membership['role'], 'is_active': membership['is_active']},
        )
        if request.method == 'POST' and form.is_valid():
            form.save(schema, membership_id)
            messages.success(request, 'Role updated.')
            return redirect(
                'admin:memberships_schoolmembership_change',
                schema=schema,
                membership_id=membership_id,
            )
        return self._render_form(
            request,
            form,
            title=f'{membership["email"]} at {membership["school_name"]}',
            membership=membership,
        )

    def _render_form(self, request, form, *, title, membership):
        context = {
            **self.admin_site.each_context(request),
            'title': title,
            'opts': self.model._meta,
            'form': form,
            'membership': membership,
            'changelist_url': reverse('admin:memberships_schoolmembership_changelist'),
        }
        return TemplateResponse(
            request,
            'admin/memberships/schoolmembership_form.html',
            context,
        )


@admin.register(StaffInvite)
class StaffInviteAdmin(admin.ModelAdmin):
    """
    Invites stay in the tenant schema. The public admin does not query that
    table; school staff issue invites from the school app.
    """

    list_display = ('email', 'role', 'status', 'expires_at', 'created_at')

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name

        def wrap(view):
            return self.admin_site.admin_view(view)

        return [
            path('', wrap(self.invite_notice), name='%s_%s_changelist' % info),
        ]

    def invite_notice(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Staff invites',
            'opts': self.model._meta,
            'membership_url': reverse('admin:memberships_schoolmembership_changelist'),
        }
        return TemplateResponse(
            request,
            'admin/memberships/staffinvite_notice.html',
            context,
        )


    def has_add_permission(self, request):
        return False
