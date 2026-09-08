from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard Portals
    path('', views.dashboard_router, name='router'),
    path('admin-portal/', views.admin_dashboard, name='admin_dashboard'),
    path('coordinator/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('intern/', views.intern_dashboard, name='intern_dashboard'),

    # Admin & Coordinator Action APIs
    path('issue-intern-id/', views.issue_intern_id_api, name='issue_intern_id_api'),
    path('create-coordinator/', views.create_coordinator_api, name='create_coordinator_api'),
    path('create-department/', views.create_department_api, name='create_department_api'),
    path('create-admin/', views.create_admin_api, name='create_admin_api'),
    path('coordinator/<int:coordinator_id>/delete/', views.delete_coordinator_api, name='delete_coordinator'),

    # Intern Management APIs
    path('intern/<int:intern_id>/detail/', views.intern_detail_api, name='intern_detail_api'),
    path('intern/<int:intern_id>/update/', views.update_intern_api, name='update_intern'),
    path('update-intern-coordinator/<int:intern_id>/', views.update_intern_coordinator_api, name='update_intern_coordinator_api'),
    path('intern/<int:intern_id>/remove/', views.remove_intern_api, name='remove_intern_api'),
    path('intern/<int:intern_id>/restore/', views.restore_intern_api, name='restore_intern_api'),

    # Schedule Management APIs
    path('intern/<int:intern_id>/schedule/', views.get_intern_schedule_api, name='get_intern_schedule'),
    path('intern/<int:intern_id>/schedule/week/save/', views.save_intern_schedule_week_api, name='save_intern_schedule_week'),
    path('intern/<int:intern_id>/schedule/week/<int:week_id>/delete/', views.delete_intern_schedule_week_api, name='delete_intern_schedule_week'),
    path('intern/week/<int:week_id>/toggle-lock/', views.toggle_week_lock, name='toggle_week_lock'),

    # Task Management APIs
    path('intern/week/<int:week_id>/add-day/', views.intern_add_day_api, name='intern_add_day_api'),
    path('intern/task/<int:task_id>/edit/', views.intern_edit_task_api, name='intern_edit_task_api'),
    path('task/<int:task_id>/update_status/', views.update_task_status, name='update_task_status'),
    path('task/<int:task_id>/update/', views.update_task_api, name='update_task_api'),
    path('task/<int:task_id>/delete/', views.delete_task_api, name='delete_task_api'),

    # Communication & Notification APIs
    path('get-messages/', views.get_messages_api, name='get_messages_api'),
    path('send-message/', views.send_message_api, name='send_message_api'),
    path('message/<int:message_id>/delete/', views.delete_message_api, name='delete_message'),
    path('notifications/', views.get_notifications_api, name='get_notifications_api'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_notification_read_api'),
]