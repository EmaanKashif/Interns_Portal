from django.contrib import admin
from .models import Department, DepartmentAssignment, InternshipWeek, Topic, DailyTask


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'coordinator', 'description')
    list_filter = ('coordinator',)
    search_fields = ('name',)
    autocomplete_fields = ('coordinator',)


@admin.register(DepartmentAssignment)
class DepartmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'intern', 'department', 'start_date', 'end_date')
    list_filter = ('department', 'start_date', 'end_date')
    search_fields = ('intern__full_name', 'department__name')


@admin.register(InternshipWeek)
class InternshipWeekAdmin(admin.ModelAdmin):
    # 'supervisor' aur 'get_effective_coordinator' ko list_display mein add kiya hai
    list_display = ('intern', 'week_number', 'department', 'supervisor', 'get_effective_coordinator', 'start_date', 'end_date')
    list_filter = ('department', 'week_number', 'supervisor')
    search_fields = ('intern__full_name', 'department__name')

    @admin.display(description='Effective Coordinator')
    def get_effective_coordinator(self, obj):
        return obj.effective_coordinator


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'week', 'title', 'description')
    list_filter = ('week',)
    search_fields = ('title', 'week__title')


@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'intern', 'topic', 'date', 'title', 'status', 'created_at')
    list_filter = ('status', 'date', 'topic__week__department')
    search_fields = ('title', 'intern__full_name', 'topic__title')