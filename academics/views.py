import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import InternshipWeek, Topic, DailyTask, DepartmentAssignment

logger = logging.getLogger(__name__)

# --- Progress Calculation Engine ---

def calculate_intern_progress(intern):
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

# --- Task Management Views ---

@login_required
def add_daily_task(request, topic_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    topic = get_object_or_404(Topic, id=topic_id)
    week = topic.week
    
    # Enforce Backend Week Locking
    if week.is_locked:
        return JsonResponse({
            'error': '🔒 This week is locked because its deadline has passed. Late additions are not allowed.'
        }, status=403)

    # Server-side ownership verification
    intern_profile = getattr(request.user, 'intern_profile', None)
    if not intern_profile:
        return JsonResponse({'error': 'Unauthorized: Only interns can add tasks.'}, status=403)

    task_date = request.POST.get('date') or timezone.now().date()
    title = request.POST.get('title')
    description = request.POST.get('description', '')

    if not title:
        return JsonResponse({'error': 'Task title is required.'}, status=400)

    task = DailyTask.objects.create(
        intern=intern_profile,
        topic=topic,
        date=task_date,
        title=title,
        description=description,
        status='submitted',
        attached_file=request.FILES.get('attached_file')
    )

    return JsonResponse({
        'success': True,
        'message': 'Task created successfully.',
        'task': {
            'id': task.id,
            'title': task.title,
            'date': str(task.date),
            'status': task.get_status_display()
        }
    })

@login_required
def edit_daily_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    intern_profile = getattr(request.user, 'intern_profile', None)
    task = get_object_or_404(DailyTask, id=task_id)

    if task.intern != intern_profile:
        return JsonResponse({'error': 'Permission denied: You do not own this task.'}, status=403)

    if task.topic.week.is_locked:
        return JsonResponse({'error': '🔒 Cannot edit a task in a locked week.'}, status=403)

    title = request.POST.get('title')
    description = request.POST.get('description')
    due_date = request.POST.get('due_date')

    if title:
        task.title = title
    if description is not None:
        task.description = description
    if due_date:
        task.date = due_date

    task.save()
    return JsonResponse({'success': True, 'message': 'Task updated successfully.'})

@login_required
def delete_daily_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    intern_profile = getattr(request.user, 'intern_profile', None)
    task = get_object_or_404(DailyTask, id=task_id)

    if task.intern != intern_profile:
        return JsonResponse({'error': 'Permission denied: You do not own this task.'}, status=403)

    if task.topic.week.is_locked:
        return JsonResponse({'error': '🔒 Cannot delete task in a locked week.'}, status=403)

    task.delete()
    return JsonResponse({'success': True, 'message': 'Task deleted successfully.'})

@login_required
def update_task_status(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    task = get_object_or_404(DailyTask, id=task_id)
    status_choice = request.POST.get('status')

    valid_statuses = dict(DailyTask.STATUS_CHOICES).keys()
    if status_choice not in valid_statuses:
        return JsonResponse({'error': 'Invalid task status.'}, status=400)

    task.status = status_choice
    task.save()

    progress = calculate_intern_progress(task.intern)
    return JsonResponse({
        'success': True,
        'message': 'Task status updated.',
        'progress_pct': progress['overall']
    })

# --- Submission & File Handlers ---

@login_required
def submit_task_api(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    intern_profile = getattr(request.user, 'intern_profile', None)
    if not intern_profile:
        return JsonResponse({'error': 'Unauthorized: Only interns can submit deliverables.'}, status=403)

    task = get_object_or_404(DailyTask, id=task_id)

    if task.intern != intern_profile:
        return JsonResponse({'error': 'Permission denied: You do not own this task.'}, status=403)

    if task.topic.week.is_locked:
        return JsonResponse({
            'error': '🔒 This week is locked because its deadline has passed. Submissions are disabled.'
        }, status=403)

    submission_notes = request.POST.get('submission_text', '')
    if submission_notes:
        task.description = f"{task.description}\n\nSubmission Notes: {submission_notes}".strip()

    file_obj = request.FILES.get('attached_file')
    if file_obj:
        if file_obj.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File is too large. Maximum allowed size is 10 MB.'}, status=400)
        task.attached_file = file_obj

    task.status = 'submitted'
    task.save()

    return JsonResponse({
        'success': True,
        'message': 'Work submitted successfully!',
        'task_id': task.id,
        'status': task.get_status_display()
    })

@login_required
def review_submission_api(request, submission_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    is_coordinator = hasattr(request.user, 'supervisor_profile') or request.user.role in ['admin', 'supervisor']
    if not is_coordinator:
        return JsonResponse({'error': 'Unauthorized: Only Coordinators or Admins can review submissions.'}, status=403)

    task = get_object_or_404(DailyTask, id=submission_id)
    status_choice = request.POST.get('status')

    valid_statuses = dict(DailyTask.STATUS_CHOICES).keys()
    if status_choice not in valid_statuses:
        return JsonResponse({'error': f'Invalid status choice.'}, status=400)

    task.status = status_choice
    task.save()

    return JsonResponse({
        'success': True,
        'message': f'Task status updated to {task.get_status_display()}.',
        'task_id': task.id,
        'status': task.status
    })

@login_required
def download_submission_file(request, submission_id):
    """
    Handles file downloads for task deliverables with authorization security.
    """
    task = get_object_or_404(DailyTask, id=submission_id)

    # Ownership / Privilege Check
    is_owner = hasattr(request.user, 'intern_profile') and task.intern == request.user.intern_profile
    is_coordinator_or_admin = hasattr(request.user, 'supervisor_profile') or request.user.role in ['admin', 'supervisor']

    if not (is_owner or is_coordinator_or_admin):
        return JsonResponse({'error': 'Unauthorized file access.'}, status=403)

    if task.attached_file:
        try:
            return FileResponse(task.attached_file.open('rb'), as_attachment=True, filename=task.attached_file.name)
        except Exception as e:
            logger.error(f"Error reading file for task {submission_id}: {e}")
            raise Http404("File could not be retrieved from local storage.")
    elif task.attached_file_url:
        return redirect(task.attached_file_url)
    else:
        raise Http404("No attached file exists for this task submission.")