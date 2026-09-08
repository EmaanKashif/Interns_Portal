from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('task/<int:task_id>/submit/', views.submit_task_api, name='submit_task_api'),
    path('task/<int:task_id>/details/', views.get_task_details_api, name='get_task_details_api'),
    path('submission/<int:submission_id>/delete/', views.delete_submission_api, name='delete_submission_api'),
    path('submission/<int:submission_id>/review/', views.review_submission_api, name='review_submission_api'),
    path('submission/<int:submission_id>/download/', views.download_submission_file, name='download_submission_file'),
]