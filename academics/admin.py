from django.contrib import admin

from .models import DailyTask, Department, InternshipWeek, Topic


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 1


@admin.register(InternshipWeek)
class InternshipWeekAdmin(admin.ModelAdmin):
    list_display = ('intern', 'week_number', 'department', 'start_date', 'end_date')
    list_filter = ('department',)
    inlines = [TopicInline]


class DailyTaskInline(admin.TabularInline):
    model = DailyTask
    extra = 1


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'week', 'order')
    inlines = [DailyTaskInline]


@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'day_number', 'status', 'due_date')
    list_filter = ('status',)
