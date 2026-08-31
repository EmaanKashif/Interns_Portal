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
    path('intern/<int:intern_id>/detail/', views.intern_detail_api, name='intern_detail_api'),
]

