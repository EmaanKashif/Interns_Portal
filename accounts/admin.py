from django.contrib import admin
from .models import User, CoordinatorProfile, InternProfile


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'username', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'username', 'first_name', 'last_name')


@admin.register(CoordinatorProfile)
class CoordinatorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'department_focus', 'is_activated')
    list_filter = ('is_activated', 'department_focus')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'department_focus')


@admin.register(InternProfile)
class InternProfileAdmin(admin.ModelAdmin):
    # Dynamic columns added to list_display
    list_display = (
        'intern_id', 
        'full_name', 
        'get_current_week', 
        'get_days_left', 
        'get_active_coordinator',
        'is_active'
    )
    
    list_filter = ('is_active', 'supervisor', 'university')
    search_fields = ('intern_id', 'full_name', 'university', 'degree', 'user__email')

    # Custom methods to call the @property logic from InternProfile
    @admin.display(description='Current Week')
    def get_current_week(self, obj):
        return obj.current_week_display

    @admin.display(description='Time Remaining')
    def get_days_left(self, obj):
        days = obj.days_remaining
        if days == 0:
            return "Completed"
        return f"{days} days ({days // 7}w {days % 7}d)"

    @admin.display(description='Active Coordinator')
    def get_active_coordinator(self, obj):
        return obj.active_coordinator