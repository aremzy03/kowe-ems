from django.contrib import admin

from .models import SchoolMembership, StaffInvite


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)


@admin.register(StaffInvite)
class StaffInviteAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'status', 'invited_by', 'expires_at', 'created_at')
    list_filter = ('role', 'status')
    search_fields = ('email', 'token')
    raw_id_fields = ('invited_by',)
    readonly_fields = ('token', 'created_at', 'accepted_at')
