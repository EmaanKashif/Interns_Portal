import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from dashboard.models import Notification
from .models import DailyTask, TaskSubmission


@login_required
@require_POST
def submit_task_api(request, task_id):
    """
    API endpoint for interns to submit work and optional files for a task.
    Backend RBAC: Intern can ONLY submit work for their own assigned task.
    File upload is validated for type and 10MB size limit.
    Triggers a notification to their assigned supervisor.
    """
    task = get_object_or_404(DailyTask, pk=task_id)
    intern_profile = getattr(request.user, 'intern_profile', None)

    if not intern_profile or task.topic.week.intern != intern_profile:
        return JsonResponse({'success': False, 'error': 'Permission denied. You can only submit work for your assigned tasks.'}, status=403)

    submission_text = request.POST.get('submission_text', '').strip()
    attached_file = request.FILES.get('attached_file')

    if not submission_text and not attached_file:
        return JsonResponse({'success': False, 'error': 'Please provide text notes or attach a file.'}, status=400)

    try:
        submission = TaskSubmission(
            task=task,
            intern=intern_profile,
            submission_text=submission_text,
            attached_file=attached_file,
            status=TaskSubmission.STATUS_SUBMITTED
        )
        submission.full_clean()
        submission.save()

        # Update task status to Completed or In Progress if specified
        new_status = request.POST.get('status', DailyTask.STATUS_COMPLETED)
        if new_status in [choice[0] for choice in DailyTask.STATUS_CHOICES]:
            task.status = new_status
            task.save()

        # Trigger notification to Supervisor
        if intern_profile.supervisor and intern_profile.supervisor.user:
            Notification.objects.create(
                recipient=intern_profile.supervisor.user,
                sender=request.user,
                title=f"Work Submitted: {intern_profile.full_name}",
                message=f"{intern_profile.full_name} submitted work for '{task.title}'.",
                link=f"/supervisor/?intern_id={intern_profile.id}",
                notification_type=Notification.TYPE_SUBMISSION
            )

        return JsonResponse({
            'success': True,
            'message': 'Submission received successfully!',
            'submission_id': submission.id,
            'task_id': task.id,
            'task_status': task.status,
            'task_status_display': task.get_status_display(),
            'file_url': submission.attached_file.url if submission.attached_file else None,
            'file_name': os.path.basename(submission.attached_file.name) if submission.attached_file else None
        })

    except ValidationError as e:
        error_msg = e.messages[0] if isinstance(e.messages, list) else str(e)
        return JsonResponse({'success': False, 'error': error_msg}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Submission failed: {str(e)}"}, status=500)


@login_required
@require_POST
def review_submission_api(request, submission_id):
    """
    API endpoint for Supervisors to review work submissions and provide feedback.
    Backend RBAC: Supervisor can ONLY review submissions for their assigned interns.
    Triggers a notification to the intern.
    """
    submission = get_object_or_404(TaskSubmission, pk=submission_id)
    user = request.user

    allowed = False
    if user.role == User.ROLE_ADMIN or user.is_staff:
        allowed = True
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor_profile = getattr(user, 'supervisor_profile', None)
        if supervisor_profile and submission.intern.supervisor == supervisor_profile:
            allowed = True

    if not allowed:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    status_val = request.POST.get('status', TaskSubmission.STATUS_REVIEWED)
    feedback_text = request.POST.get('feedback', '').strip()

    if status_val not in [choice[0] for choice in TaskSubmission.STATUS_CHOICES]:
        return JsonResponse({'success': False, 'error': 'Invalid status.'}, status=400)

    submission.status = status_val
    submission.feedback = feedback_text
    submission.reviewed_at = timezone.now()
    submission.save()

    # Trigger notification to Intern
    if submission.intern.user:
        Notification.objects.create(
            recipient=submission.intern.user,
            sender=user,
            title="Task Feedback Received",
            message=f"Your supervisor reviewed your submission for '{submission.task.title}'. Status: {submission.get_status_display()}.",
            link="/intern/",
            notification_type=Notification.TYPE_SUBMISSION
        )

    return JsonResponse({
        'success': True,
        'message': 'Review saved and intern notified.',
        'submission_id': submission.id,
        'status_display': submission.get_status_display(),
        'feedback': submission.feedback
    })


@login_required
def download_submission_file(request, submission_id):
    """
    Secure file download view. Serves task files ONLY to authorized users:
    - The intern who submitted the file
    - The supervisor assigned to that intern
    - Admin / Staff users
    """
    submission = get_object_or_404(TaskSubmission, pk=submission_id)
    if not submission.attached_file:
        raise Http404("No file attached to this submission.")

    user = request.user
    allowed = False

    if user.is_staff or user.role == User.ROLE_ADMIN:
        allowed = True
    elif user.role == User.ROLE_INTERN:
        if submission.intern.user == user:
            allowed = True
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor_profile = getattr(user, 'supervisor_profile', None)
        if supervisor_profile and submission.intern.supervisor == supervisor_profile:
            allowed = True

    if not allowed:
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    file_path = submission.attached_file.path
    if not os.path.exists(file_path):
        raise Http404("Requested file does not exist on disk.")

    response = FileResponse(open(file_path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
    return response
