from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('task/<int:task_id>/submit/', views.submit_task_api, name='submit_task_api'),
    path('submission/<int:submission_id>/review/', views.review_submission_api, name='review_submission_api'),
    path('submission/<int:submission_id>/download/', views.download_submission_file, name='download_submission_file'),
]
