from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import InternProfile, SupervisorProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department_focus')


@admin.register(InternProfile)
class InternProfileAdmin(admin.ModelAdmin):
    list_display = (
        'intern_id', 'full_name', 'university', 'supervisor',
        'is_activated', 'start_date', 'end_date',
    )
    list_filter = ('is_activated', 'supervisor')
    search_fields = ('full_name', 'intern_id', 'university')
    readonly_fields = ('intern_id', 'is_activated', 'user')
