import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import DailyTask, DepartmentAssignment

logger = logging.getLogger(__name__)

# --- Progress Calculation Engine (Imported by dashboard/views.py) ---

def calculate_intern_progress(intern):
    """Calculates overall progress percentage and department-level progress for an intern."""
    total_tasks = DailyTask.objects.filter(intern=intern).count()
    completed_tasks = DailyTask.objects.filter(intern=intern, status='completed').count()
    overall_progress = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    dept_progress = {}
    assignments = DepartmentAssignment.objects.filter(intern=intern)
    for assign in assignments:
        dept_tasks = DailyTask.objects.filter(intern=intern, topic__week__department=assign.department)
        total_d = dept_tasks.count()
        comp_d = dept_tasks.filter(status='completed').count()
        dept_progress[assign.department.id] = {
            'name': assign.department.name,
            'progress': round((comp_d / total_d) * 100) if total_d > 0 else 0,
            'start_date': assign.start_date,
            'end_date': assign.end_date,
            'weeks': assign.duration_in_weeks
        }

    return {
        'overall': overall_progress,
        'departments': dept_progress
    }


# --- Deliverables & Submission APIs ---

@login_required
@require_POST
def submit_task_api(request, task_id):
    """Submits deliverable notes and supports multiple file attachments."""
    try:
        intern_profile = getattr(request.user, 'intern_profile', None)
        if not intern_profile:
            return JsonResponse({'success': False, 'error': 'Unauthorized: Only interns can submit deliverables.'}, status=403)

        task = get_object_or_404(DailyTask, pk=task_id)

        # Check ownership
        if task.intern and task.intern != intern_profile:
            return JsonResponse({'success': False, 'error': 'Permission denied: You do not own this task.'}, status=403)

        # Check if week is locked
        if task.topic and task.topic.week and task.topic.week.is_locked:
            return JsonResponse({
                'success': False,
                'error': '🔒 This week is locked because its deadline has passed. Submissions are disabled.'
            }, status=403)

        submission_notes = request.POST.get('submission_text', '').strip()
        if submission_notes:
            task.description = submission_notes

        # Handle Multiple Files
        files = request.FILES.getlist('attached_file') or request.FILES.getlist('attached_files')
        for file_obj in files:
            if file_obj.size > 10 * 1024 * 1024:
                return JsonResponse({'success': False, 'error': f'File "{file_obj.name}" exceeds maximum allowed size of 10 MB.'}, status=400)
            
            # Save primary attachment to task
            if not task.attached_file:
                task.attached_file = file_obj

        task.status = 'submitted'
        task.save()

        return JsonResponse({
            'success': True,
            'message': 'Deliverables submitted successfully!',
            'task_id': task.id,
            'status': task.get_status_display(),
            'description': task.description
        })

    except Exception as exc:
        logger.error(f"Error submitting task {task_id}: {str(exc)}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(exc)}'}, status=500)


@login_required
def get_task_details_api(request, task_id):
    """Returns task details and submitted files list for the Deliverables modal."""
    task = get_object_or_404(DailyTask, pk=task_id)
    
    files_data = []
    if task.attached_file:
        files_data.append({
            'id': task.id,
            'name': task.attached_file.name.split('/')[-1],
            'url': task.attached_file.url
        })

    return JsonResponse({
        'success': True,
        'title': task.title,
        'notes': task.description or '',
        'files': files_data
    })

@login_required
@require_POST
def delete_submission_api(request, submission_id):
    """Clears uploaded file attachment on DailyTask."""
    try:
        task = get_object_or_404(DailyTask, pk=submission_id)
        intern_profile = getattr(request.user, 'intern_profile', None)
        is_admin = request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', '') == 'admin'

        if task.intern == intern_profile or is_admin:
            if task.attached_file:
                task.attached_file.delete(save=False)
                task.attached_file = None
                task.save()
            return JsonResponse({'success': True, 'message': 'File deleted successfully.'})
        
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    except Exception as exc:
        logger.error(f"Error deleting submission {submission_id}: {str(exc)}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(exc)}'}, status=500)


@login_required
@require_POST
def review_submission_api(request, submission_id):
    """Allows coordinators or admins to review and update the status of a daily task."""
    try:
        task = get_object_or_404(DailyTask, pk=submission_id)
        user = request.user

        coordinator_profile = getattr(user, 'coordinator_profile', None)
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', '') == 'admin'
        is_their_coordinator = coordinator_profile and task.intern and task.intern.supervisor == coordinator_profile

        if not (is_admin or is_their_coordinator):
            return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

        status_choice = request.POST.get('status', '').strip()
        valid_statuses = [choice[0] for choice in DailyTask.STATUS_CHOICES]

        if status_choice not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status choice.'}, status=400)

        task.status = status_choice
        task.save()

        return JsonResponse({
            'success': True,
            'message': f'Task status updated to {task.get_status_display()}.',
            'task_id': task.id,
            'status': task.status
        })

    except Exception as exc:
        logger.error(f"Error reviewing submission {submission_id}: {str(exc)}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(exc)}'}, status=500)


@login_required
def download_submission_file(request, submission_id):
    """Handles secure deliverable downloads."""
    task = get_object_or_404(DailyTask, pk=submission_id)

    is_owner = hasattr(request.user, 'intern_profile') and task.intern == request.user.intern_profile
    coordinator_profile = getattr(request.user, 'coordinator_profile', None)
    is_admin = request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', '') == 'admin'
    is_their_coordinator = coordinator_profile and task.intern and task.intern.supervisor == coordinator_profile

    if not (is_owner or is_admin or is_their_coordinator):
        return JsonResponse({'error': 'Unauthorized file access.'}, status=403)

    if task.attached_file:
        try:
            return FileResponse(task.attached_file.open('rb'), as_attachment=True, filename=task.attached_file.name)
        except Exception as e:
            logger.error(f"Error reading file for task {submission_id}: {e}")
            raise Http404("File could not be retrieved.")
    elif task.attached_file_url:
        return redirect(task.attached_file_url)
    else:
        raise Http404("No attached file exists for this task submission.")