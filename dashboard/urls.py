from django.urls import path
from . import views

app_name = 'dashboard'
urlpatterns = [
    path('', views.dashboard_router, name='router'),
    path('admin-portal/', views.admin_dashboard, name='admin_dashboard'),
    path('intern/', views.intern_dashboard, name='intern_dashboard'),
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('issue-intern-id/', views.issue_intern_id_api, name='issue_intern_id_api'),
    path('create-supervisor/', views.create_supervisor_api, name='create_supervisor_api'),
    path('create-department/', views.create_department_api, name='create_department_api'),
    path('messages/send/', views.send_message_api, name='send_message_api'),
    path('messages/thread/', views.get_messages_api, name='get_messages_api'),
    path('notifications/', views.get_notifications_api, name='get_notifications_api'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_notification_read_api'),
    path('task/<int:task_id>/update_status/', views.update_task_status, name='update_task_status'),
    path('task/<int:task_id>/update/', views.update_task_api, name='update_task_api'),
    path('intern/<int:intern_id>/detail/', views.intern_detail_api, name='intern_detail_api'),
    path('update-intern-supervisor/<int:intern_id>/', views.update_intern_supervisor_api, name='update_intern_supervisor_api'),
    
    # Intern Offboard & Restore Endpoints
    path('intern/<int:intern_id>/remove/', views.remove_intern_api, name='remove_intern_api'),
    path('intern/<int:intern_id>/restore/', views.restore_intern_api, name='restore_intern_api'),
    path(
    'intern/<int:intern_id>/update/',
    views.update_intern_api,
    name='update_intern'
),
path(
    'create-admin/',
    views.create_admin_api,
    name='create_admin_api'
),
path(
    'supervisor/<int:supervisor_id>/delete/',
    views.delete_supervisor_api,
    name='delete_supervisor'
),
path(
    'intern/task/<int:task_id>/edit/',
    views.intern_edit_task_api,
    name='intern_edit_task'
),
path(
    'intern/week/<int:week_id>/add-day/',
    views.intern_add_day_api,
    name='intern_add_day'
),
path(
    'intern/<int:intern_id>/schedule/',
    views.get_intern_schedule_api,
    name='get_intern_schedule'
),

path(
    'intern/<int:intern_id>/schedule/week/save/',
    views.save_intern_schedule_week_api,
    name='save_intern_schedule_week'
),

path(
    'intern/<int:intern_id>/schedule/week/<int:week_id>/delete/',
    views.delete_intern_schedule_week_api,
    name='delete_intern_schedule_week'
),

]

