import datetime
import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction

from academics.models import DailyTask, Department, InternshipWeek, TaskSubmission, Topic, DepartmentAssignment
from academics.views import calculate_intern_progress
from accounts.decorators import role_required
from accounts.models import InternProfile, CoordinatorProfile, User
from .models import Message, Notification


def _can_manage_schedules(user):
    """Return True for portal admins, coordinators, staff, and superusers."""
    return (
        user.role in [User.ROLE_ADMIN, User.ROLE_COORDINATOR]
        or user.is_superuser
        or user.is_staff
    )


ROTATION_SCHEDULES = {
    'EMAAN KASHIF': ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation'],
    'MENEHIL': ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation'],
    'MUHAMMAD DANIYAL': ['IT Operations', 'DCI', 'Networks & Security', 'Software dev', 'ERP', 'Report & Presentation'],
    'NIAZ SHAH': ['IT Operations', 'DCI', 'Networks & Security', 'Software dev', 'ERP', 'Report & Presentation'],
    'HASSAN TARIQ': ['DCI', 'Networks & Security', 'Software dev', 'ERP', 'IT Operations', 'Report & Presentation'],
    'SUBHAN': ['Networks & Security', 'DCI', 'Software dev', 'ERP', 'IT Operations', 'Report & Presentation'],
    'Ayesha': ['DCI', 'Software dev', 'ERP', 'IT Operations', 'Networks & Security', 'Report & Presentation']
}

DEFAULT_ROTATION = ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation']


def build_full_intern_schedule(profile):
    """
    Generates 6 rotation weeks and default daily tasks for an intern profile.
    """
    if profile.weeks.exists():
        return

    normalized_name = profile.full_name.upper().strip()
    dept_names = ROTATION_SCHEDULES.get(normalized_name, DEFAULT_ROTATION)
    curr_start = profile.start_date or datetime.date(2026, 8, 25)

    for week_num, dept_name in enumerate(dept_names, start=1):
        dept_obj, _ = Department.objects.get_or_create(
            name=dept_name,
            defaults={'description': f'{dept_name} Domain Rotation Focus Area'}
        )

        curr_end = curr_start + datetime.timedelta(days=6)

        week_obj = InternshipWeek.objects.create(
            intern=profile,
            department=dept_obj,
            week_number=week_num,
            start_date=curr_start,
            end_date=curr_end
        )

        topic = Topic.objects.create(
            week=week_obj,
            title=f"Orientation & {dept_name} Setup",
            order=1
        )

        DailyTask.objects.create(
            topic=topic,
            day_number=1,
            title="System Access & Environment Setup",
            description=f"Access workspace tools and review initial department guidelines for {dept_name}.",
            due_date=curr_start,
            status=DailyTask.STATUS_PENDING
        )

        DailyTask.objects.create(
            topic=topic,
            day_number=2,
            title="Core Concepts & Architecture Review",
            description=f"Study foundational architecture documentation and guidelines for {dept_name}.",
            due_date=curr_start + datetime.timedelta(days=1),
            status=DailyTask.STATUS_PENDING
        )

        curr_start = curr_end + datetime.timedelta(days=1)


@login_required
def dashboard_router(request):
    """Routes users cleanly to their specific portal based on role."""
    user = request.user
    
    if user.role == getattr(User, 'ROLE_ADMIN', 'admin') or user.is_superuser:
        return redirect('dashboard:admin_dashboard')
    elif user.role == getattr(User, 'ROLE_COORDINATOR', 'coordinator'):
        return redirect('dashboard:coordinator_dashboard')
    elif user.role == getattr(User, 'ROLE_INTERN', 'intern'):
        return redirect('dashboard:intern_dashboard')
    else:
        return redirect('dashboard:intern_dashboard')


@role_required('admin')
def admin_dashboard(request):
    """Dedicated Admin Dashboard for system-wide oversight."""
    total_interns = InternProfile.objects.filter(is_active=True).count()
    activated_interns = InternProfile.objects.filter(is_active=True, is_activated=True).count()
    pending_activations = InternProfile.objects.filter(is_active=True, is_activated=False).count()
    total_departments = Department.objects.count()

    coordinator_users = User.objects.filter(role=User.ROLE_COORDINATOR)
    for coord_user in coordinator_users:
        CoordinatorProfile.objects.get_or_create(
            user=coord_user,
            defaults={'department_focus': 'Enterprise Operations'},
        )

    coordinators = CoordinatorProfile.objects.select_related('user').all()
    total_coordinators = coordinators.count()

    interns = InternProfile.objects.select_related('supervisor__user', 'user').all()
    schedule_interns = InternProfile.objects.filter(is_active=True).select_related('supervisor__user', 'user')
    departments = Department.objects.all()

    context = {
        'total_interns': total_interns,
        'activated_interns': activated_interns,
        'pending_activations': pending_activations,
        'total_supervisors': total_coordinators,
        'total_coordinators': total_coordinators,
        'total_departments': total_departments,
        'interns': interns,
        'schedule_interns': schedule_interns,
        'supervisors': coordinators,
        'coordinators': coordinators,
        'departments': departments,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@role_required('intern')
@login_required
def intern_dashboard(request):
    profile = getattr(request.user, 'intern_profile', None)
    if not profile:
        return redirect('login')

    assignments = DepartmentAssignment.objects.filter(intern=profile)
    assigned_departments = [a.department for a in assignments]

    if assigned_departments:
        all_weeks = InternshipWeek.objects.filter(department__in=assigned_departments).prefetch_related('topics__tasks').order_by('week_number')
    else:
        all_weeks = InternshipWeek.objects.all().prefetch_related('topics__tasks').order_by('week_number')

    progress_data = calculate_intern_progress(profile)

    user_tasks = DailyTask.objects.filter(intern=profile)
    completed_tasks = user_tasks.filter(status='completed').count()
    in_progress_tasks = user_tasks.filter(status='in_progress').count()
    pending_tasks = user_tasks.filter(status__in=['not_started', 'submitted', 'pending']).count()

    for week in all_weeks:
        week_tasks = DailyTask.objects.filter(topic__week=week, intern=profile)
        w_total = week_tasks.count()
        w_completed = week_tasks.filter(status='completed').count()
        week.progress = {
            'total': w_total,
            'completed': w_completed,
            'pct': round((w_completed / w_total) * 100) if w_total > 0 else 0,
        }
        week.coordinator = week.effective_coordinator

    context = {
        'profile': profile,
        'all_weeks': all_weeks,
        'weeks': all_weeks,
        'progress_data': progress_data,
        'progress_pct': progress_data['overall'],
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'pending_tasks': pending_tasks,
    }

    return render(request, 'dashboard/intern_dashboard.html', context)


@login_required
@role_required([getattr(User, 'ROLE_COORDINATOR', 'coordinator')])
def coordinator_dashboard(request):
    """Coordinator portal managing assigned active and offboarded interns."""
    profile = get_object_or_404(CoordinatorProfile, user=request.user)
    
    show_archived = request.GET.get('archived') == 'true'
    target_active_status = not show_archived

    interns = InternProfile.objects.filter(
        supervisor=profile,
        is_active=target_active_status
    ).select_related('user').distinct()

    intern_rows = []
    total_cohort_tasks = 0
    total_cohort_completed = 0

    for intern in interns:
        tasks = DailyTask.objects.filter(intern=intern)
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        in_progress = tasks.filter(status='in_progress').count()
        pct = round((completed / total) * 100, 1) if total else 0

        unread_msg = Message.objects.filter(
            sender=intern.user, 
            recipient=request.user, 
            is_read=False
        ).count() if intern.user else 0

        total_cohort_tasks += total
        total_cohort_completed += completed

        intern_rows.append({
            'intern': intern,
            'progress_pct': pct,
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'unread_msg': unread_msg
        })

    cohort_pct = round((total_cohort_completed / total_cohort_tasks) * 100, 1) if total_cohort_tasks else 0
    departments = Department.objects.all()
    coordinators = CoordinatorProfile.objects.select_related('user').all()

    context = {
        'profile': profile,
        'intern_rows': intern_rows,
        'total_interns': len(intern_rows),
        'cohort_pct': cohort_pct,
        'total_cohort_completed': total_cohort_completed,
        'total_cohort_tasks': total_cohort_tasks,
        'departments': departments,
        'coordinators': coordinators,
        'show_archived': show_archived,
    }
    return render(request, 'dashboard/coordinator_dashboard.html', context)


@login_required
@require_POST
def issue_intern_id_api(request):
    """Allows Admins or Coordinators to issue a new Intern ID & activation token."""
    user = request.user
    if user.role not in [User.ROLE_ADMIN, getattr(User, 'ROLE_COORDINATOR', 'coordinator')] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    full_name = request.POST.get('full_name', '').strip()
    university = request.POST.get('university', '').strip()
    degree = request.POST.get('degree', '').strip()
    coordinator_id = request.POST.get('coordinator_id') or request.POST.get('supervisor_id')
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')

    if not full_name or not university or not degree:
        return JsonResponse({'success': False, 'error': 'Full name, university, and degree domain are required.'}, status=400)

    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.date(2026, 8, 25)
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date + datetime.timedelta(days=42)
    except ValueError:
        start_date = datetime.date(2026, 8, 25)
        end_date = start_date + datetime.timedelta(days=42)

    coordinator = None
    if coordinator_id:
        coordinator = CoordinatorProfile.objects.filter(pk=coordinator_id).first()
    elif user.role == getattr(User, 'ROLE_COORDINATOR', 'coordinator'):
        coordinator = getattr(user, 'coordinator_profile', None)

    profile = InternProfile.objects.create(
        full_name=full_name,
        university=university,
        degree=degree,
        start_date=start_date,
        end_date=end_date,
        supervisor=coordinator,
        is_activated=False
    )
    profile.generate_activation_token()

    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    activation_url = f"{scheme}://{host}/accounts/activate/?token={profile.activation_token}"

    return JsonResponse({
        'success': True,
        'message': "Intern Profile created successfully!",
        'intern_id': profile.intern_id,
        'full_name': profile.full_name,
        'activation_token': profile.activation_token,
        'activation_url': activation_url,
        'coordinator': profile.supervisor.user.get_full_name() if (profile.supervisor and profile.supervisor.user) else "Unassigned"
    })


@login_required
@require_POST
def create_custom_week_api(request):
    """API allowing Coordinators and Admins to add/edit rotation weeks."""
    user = request.user
    if user.role not in [User.ROLE_ADMIN, User.ROLE_COORDINATOR] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern_id = request.POST.get('intern_id')
    dept_id = request.POST.get('department_id')
    week_number = request.POST.get('week_number')
    topic_title = request.POST.get('topic_title', 'Weekly Domain Overview').strip()
    task_title = request.POST.get('task_title', '').strip()
    task_desc = request.POST.get('task_description', '').strip()
    start_date_str = request.POST.get('start_date')

    intern = get_object_or_404(InternProfile, pk=intern_id)
    department = get_object_or_404(Department, pk=dept_id)

    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.date.today()
    except ValueError:
        start_date = datetime.date.today()

    end_date = start_date + datetime.timedelta(days=6)

    week_obj, _ = InternshipWeek.objects.get_or_create(
        intern=intern,
        week_number=week_number,
        defaults={
            'department': department,
            'start_date': start_date,
            'end_date': end_date
        }
    )
    week_obj.department = department
    week_obj.save()

    topic = Topic.objects.create(week=week_obj, title=topic_title, order=1)

    if task_title:
        DailyTask.objects.create(
            topic=topic,
            day_number=1,
            title=task_title,
            description=task_desc,
            due_date=start_date,
            status=DailyTask.STATUS_PENDING
        )

    return JsonResponse({'success': True, 'message': f'Week {week_number} ({department.name}) updated successfully.'})


@login_required
def get_intern_schedule_api(request, intern_id):
    """Returns the complete schedule for an intern."""
    try:
        if not _can_manage_schedules(request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        intern = get_object_or_404(InternProfile, id=intern_id, is_active=True)

        weeks = (
            InternshipWeek.objects
            .filter(intern=intern)
            .select_related('department')
            .prefetch_related('topics__tasks')
            .order_by('week_number')
        )

        weeks_data = []

        for week in weeks:
            tasks_data = []
            
            topics = week.topics.all() if hasattr(week, 'topics') else []
            for topic in topics:
                for task in topic.tasks.all():
                    tasks_data.append({
                        'id': task.id,
                        'day_number': getattr(task, 'day_number', 1),
                        'title': getattr(task, 'title', ''),
                        'description': getattr(task, 'description', '') or '',
                        'due_date': str(task.due_date) if getattr(task, 'due_date', None) else '',
                    })

            if not tasks_data:
                direct_tasks = DailyTask.objects.filter(intern=intern, topic__week=week)
                for task in direct_tasks:
                    tasks_data.append({
                        'id': task.id,
                        'day_number': getattr(task, 'day_number', 1),
                        'title': getattr(task, 'title', ''),
                        'description': getattr(task, 'description', '') or '',
                        'due_date': str(task.date if hasattr(task, 'date') else task.due_date) or '',
                    })

            file_name = ''
            file_url = ''
            if hasattr(week, 'course_outline_file') and week.course_outline_file:
                try:
                    file_name = os.path.basename(week.course_outline_file.name)
                    file_url = week.course_outline_file.url
                except ValueError:
                    file_name = ''
                    file_url = ''

            weeks_data.append({
                'id': week.id,
                'week_number': week.week_number,
                'department_id': week.department_id if week.department else '',
                'department_name': week.department.name if week.department else 'General',
                'start_date': str(week.start_date) if week.start_date else '',
                'end_date': str(week.end_date) if week.end_date else '',
                'course_outline_title': getattr(week, 'course_outline_title', '') or '',
                'course_outline_text': getattr(week, 'course_outline_text', '') or '',
                'course_outline_file_name': file_name,
                'course_outline_file_url': file_url,
                'tasks': tasks_data,
            })

        return JsonResponse({
            'success': True,
            'intern': {
                'id': intern.id,
                'intern_id': intern.intern_id,
                'full_name': intern.full_name,
                'start_date': str(intern.start_date) if intern.start_date else '',
                'end_date': str(intern.end_date) if intern.end_date else '',
            },
            'weeks': weeks_data
        })

    except Exception as exc:
        print("GET SCHEDULE API ERROR:", str(exc))
        return JsonResponse({'success': False, 'error': f'Server Error: {str(exc)}'}, status=500)


@login_required
@require_POST
@transaction.atomic
def save_intern_schedule_week_api(request, intern_id):
    """Creates or updates one week of an intern's schedule safely."""
    try:
        if not _can_manage_schedules(request.user):
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        intern = get_object_or_404(InternProfile, id=intern_id, is_active=True)

        week_id = request.POST.get('week_id', '').strip()
        week_number = request.POST.get('week_number', '').strip()
        department_id = request.POST.get('department_id', '').strip()
        coordinator_id = request.POST.get('coordinator_id', '').strip() or request.POST.get('supervisor_id', '').strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()

        course_outline_title = request.POST.get('course_outline_title', '').strip()
        course_outline_text = request.POST.get('course_outline_text', '').strip()

        if not week_number or not department_id or not coordinator_id or not start_date_str or not end_date_str:
            return JsonResponse({'success': False, 'error': 'Week number, department, coordinator, start date, and end date are required.'}, status=400)

        week_number = int(week_number)
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        department = get_object_or_404(Department, id=department_id)
        coordinator = get_object_or_404(CoordinatorProfile, id=coordinator_id)

        if week_id:
            week = get_object_or_404(InternshipWeek, id=week_id)
            if InternshipWeek.objects.filter(intern=intern, week_number=week_number).exclude(id=week.id).exists():
                return JsonResponse({'success': False, 'error': f'Week {week_number} already exists.'}, status=400)
        else:
            if InternshipWeek.objects.filter(intern=intern, week_number=week_number).exists():
                return JsonResponse({'success': False, 'error': f'Week {week_number} already exists.'}, status=400)
            week = InternshipWeek()

        week.intern = intern
        week.week_number = week_number
        week.department = department
        week.supervisor = coordinator
        week.start_date = start_date
        week.end_date = end_date

        if hasattr(week, 'course_outline_title'):
            week.course_outline_title = course_outline_title
        if hasattr(week, 'course_outline_text'):
            week.course_outline_text = course_outline_text

        uploaded_file = request.FILES.get('course_outline_file')
        if uploaded_file and hasattr(week, 'course_outline_file'):
            week.course_outline_file = uploaded_file

        week.save()

        topic = Topic.objects.filter(week=week).first()
        if not topic:
            Topic.objects.create(
                week=week,
                title=f"{department.name} Weekly Tasks"
            )

        return JsonResponse({
            'success': True,
            'message': f'Week {week.week_number} saved successfully.',
            'week_id': week.id
        })

    except Exception as e:
        print("SAVE SCHEDULE ERROR:", str(e))
        return JsonResponse({'success': False, 'error': f'Server Error: {str(e)}'}, status=400)


@login_required
@require_POST
def delete_intern_schedule_week_api(request, intern_id, week_id):
    """Deletes a schedule week if it has no submitted work."""
    if not _can_manage_schedules(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern = get_object_or_404(InternProfile, id=intern_id, is_active=True)
    week = get_object_or_404(InternshipWeek, id=week_id, intern=intern)

    has_submissions = TaskSubmission.objects.filter(task__topic__week=week).exists()
    if has_submissions:
        return JsonResponse({'success': False, 'error': 'This week cannot be deleted because the intern has submitted work.'}, status=400)

    week_number = week.week_number
    week.delete()

    return JsonResponse({'success': True, 'message': f'Week {week_number} deleted successfully.'})


@login_required
@require_POST
def update_intern_coordinator_api(request, intern_id):
    """API endpoint allowing Admins or Coordinators to inline-update an intern's coordinator."""
    user = request.user
    if user.role not in [User.ROLE_ADMIN, getattr(User, 'ROLE_COORDINATOR', 'coordinator')] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern = get_object_or_404(InternProfile, pk=intern_id)
    coord_name = request.POST.get('coordinator_name', '').strip() or request.POST.get('supervisor_name', '').strip()

    if not coord_name:
        intern.supervisor = None
        intern.custom_supervisor_name = ''
    else:
        coordinator_obj = CoordinatorProfile.objects.filter(
            Q(user__first_name__icontains=coord_name) |
            Q(user__last_name__icontains=coord_name) |
            Q(user__username__icontains=coord_name)
        ).first()

        if coordinator_obj:
            intern.supervisor = coordinator_obj
            intern.custom_supervisor_name = ''
        else:
            intern.supervisor = None
            intern.custom_supervisor_name = coord_name

    intern.save()
    return JsonResponse({'success': True, 'message': 'Coordinator updated successfully.'})


@login_required
@require_POST
def remove_intern_api(request, intern_id):
    """Soft remove / archive intern."""
    user = request.user
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        intern = get_object_or_404(InternProfile, id=intern_id)
    elif user.role == User.ROLE_COORDINATOR:
        profile = get_object_or_404(CoordinatorProfile, user=user)
        intern = get_object_or_404(InternProfile, id=intern_id, supervisor=profile)
    else:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern.is_active = False
    intern.save(update_fields=['is_active'])

    return JsonResponse({'success': True, 'message': 'Intern removed successfully.'})


@login_required
@require_POST
def restore_intern_api(request, intern_id):
    """Restore archived intern."""
    user = request.user
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        intern = get_object_or_404(InternProfile, id=intern_id)
    elif user.role == User.ROLE_COORDINATOR:
        profile = get_object_or_404(CoordinatorProfile, user=user)
        intern = get_object_or_404(InternProfile, id=intern_id, supervisor=profile)
    else:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern.is_active = True
    intern.save(update_fields=['is_active'])

    return JsonResponse({'success': True, 'message': 'Intern restored successfully.'})


@login_required
@require_POST
def intern_edit_task_api(request, task_id):
    """Safely updates a task item."""
    try:
        intern = get_object_or_404(InternProfile, user=request.user)
        task = get_object_or_404(DailyTask, id=task_id, intern=intern)

        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        task_date_str = request.POST.get('date', '').strip() or request.POST.get('due_date', '').strip()

        if not title:
            return JsonResponse({'success': False, 'error': 'Task title is required.'}, status=400)

        task.title = title
        task.description = description

        if task_date_str:
            try:
                task_date = datetime.datetime.strptime(task_date_str, '%Y-%m-%d').date()
                if hasattr(task, 'date'):
                    task.date = task_date
                elif hasattr(task, 'due_date'):
                    task.due_date = task_date
            except ValueError:
                pass

        task.save()
        return JsonResponse({'success': True, 'message': 'Task updated successfully.'})

    except Exception as exc:
        print("EDIT TASK API ERROR:", str(exc))
        return JsonResponse({'success': False, 'error': f'Server Error: {str(exc)}'}, status=500)


@login_required
@require_POST
def intern_add_day_api(request, week_id):
    """Allows adding task items to an internship week."""
    try:
        intern = get_object_or_404(InternProfile, user=request.user)
        week = get_object_or_404(InternshipWeek, id=week_id, intern=intern)

        topic = week.topics.first() if hasattr(week, 'topics') and week.topics.exists() else None
        if not topic:
            dept_name = week.department.name if week.department else 'General'
            topic = Topic.objects.create(week=week, title=f"{dept_name} Tasks")

        target_date_str = request.POST.get('date', '').strip()
        
        if target_date_str:
            try:
                task_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                task_date = week.start_date or datetime.date.today()
        else:
            distinct_dates_count = DailyTask.objects.filter(topic=topic).values('date').distinct().count()
            start_date = week.start_date or datetime.date.today()
            task_date = start_date + datetime.timedelta(days=distinct_dates_count)
            if week.end_date and task_date > week.end_date:
                task_date = week.end_date

        same_day_task_count = DailyTask.objects.filter(topic=topic, date=task_date).count()
        task_title = request.POST.get('title', '').strip() or f"Task {same_day_task_count + 1}"

        task = DailyTask.objects.create(
            topic=topic,
            intern=intern,
            title=task_title,
            description=request.POST.get('description', '').strip(),
            date=task_date,
            status=getattr(DailyTask, 'STATUS_PENDING', 'pending')
        )

        return JsonResponse({
            'success': True,
            'message': 'Task added successfully.',
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'date': str(task.date),
                'status': task.status,
            }
        })

    except Exception as exc:
        print("ADD TASK API ERROR:", str(exc))
        return JsonResponse({'success': False, 'error': f'Server Error: {str(exc)}'}, status=500)


@login_required
@require_POST
def update_intern_api(request, intern_id):
    """Update intern details and assigned coordinator."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern = get_object_or_404(InternProfile, id=intern_id)

    full_name = request.POST.get('full_name', '').strip()
    university = request.POST.get('university', '').strip()
    degree = request.POST.get('degree', '').strip()
    coordinator_name = request.POST.get('coordinator_name', '').strip() or request.POST.get('supervisor_name', '').strip()

    if not full_name or not university or not degree:
        return JsonResponse({'success': False, 'error': 'Full name, university, and degree domain are required.'}, status=400)

    intern.full_name = full_name
    intern.university = university
    intern.degree = degree

    if not coordinator_name:
        intern.supervisor = None
        intern.custom_supervisor_name = ''
    else:
        matched_coordinator = None
        coordinators = CoordinatorProfile.objects.select_related('user').all()

        for coord in coordinators:
            existing_name = coord.user.get_full_name().strip() if coord.user else ''
            if not existing_name and coord.user:
                existing_name = coord.user.username

            if existing_name.lower() == coordinator_name.lower():
                matched_coordinator = coord
                break

        if matched_coordinator:
            intern.supervisor = matched_coordinator
            intern.custom_supervisor_name = ''
        else:
            intern.supervisor = None
            intern.custom_supervisor_name = coordinator_name

    intern.save()
    return JsonResponse({'success': True, 'message': 'Intern details updated successfully.'})


@login_required
@require_POST
def update_task_api(request, task_id):
    """Coordinator edits a daily task's title, description, or due date."""
    task = get_object_or_404(DailyTask, id=task_id, topic__week__intern__supervisor__user=request.user)
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    due_date_str = request.POST.get('due_date', '').strip()

    if title:
        task.title = title
    task.description = description
    if due_date_str:
        try:
            task.due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format.'}, status=400)

    task.save()
    return JsonResponse({'success': True, 'title': task.title, 'description': task.description, 'due_date': str(task.due_date) if task.due_date else None})


@login_required
@require_POST
def create_admin_api(request):
    """Allows an existing admin to create another admin account."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not first_name or not email or not password:
        return JsonResponse({'success': False, 'error': 'First name, email and password are required.'}, status=400)

    if password != confirm_password:
        return JsonResponse({'success': False, 'error': 'Passwords do not match.'}, status=400)

    if len(password) < 8:
        return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters.'}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({'success': False, 'error': 'An account with this email already exists.'}, status=400)

    base_username = email.split('@')[0]
    username = base_username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f'{base_username}{counter}'
        counter += 1

    admin_user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=User.ROLE_ADMIN,
        is_staff=True
    )

    return JsonResponse({
        'success': True,
        'message': f'Admin account created successfully for {admin_user.get_full_name() or admin_user.email}.'
    })


@login_required
@require_POST
def create_coordinator_api(request):
    """Allows admin to add a coordinator."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    full_name = request.POST.get('full_name', '').strip()
    email = request.POST.get('email', '').strip().lower()
    department_focus = request.POST.get('department_focus', '').strip()

    if not full_name or not email:
        return JsonResponse({'success': False, 'error': 'Coordinator name and email are required.'}, status=400)

    existing_user = User.objects.filter(email__iexact=email).first()

    if existing_user and existing_user.is_active:
        return JsonResponse({'success': False, 'error': 'An active user account with this email already exists.'}, status=400)

    if existing_user and not existing_user.is_active:
        user = existing_user
        profile, _ = CoordinatorProfile.objects.get_or_create(user=user)
    else:
        name_parts = full_name.split()
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        base_username = full_name.lower().replace(' ', '_')
        username = base_username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=getattr(User, 'ROLE_COORDINATOR', 'coordinator'),
            is_staff=False,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        profile = CoordinatorProfile.objects.create(
            user=user,
            department_focus=department_focus or "General",
            is_activated=False
        )

    token = getattr(profile, 'activation_token', None)
    if not token and hasattr(profile, 'generate_activation_token'):
        token = profile.generate_activation_token()

    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    activation_url = f"{scheme}://{host}/accounts/activate/?token={token}"

    return JsonResponse({
        'success': True,
        'message': f'Activation link generated for {full_name}.',
        'full_name': full_name,
        'email': email,
        'coordinator_id': profile.id,
        'activation_url': activation_url
    })


@login_required
@require_POST
def delete_coordinator_api(request, coordinator_id):
    """Safely deletes a coordinator profile."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    coordinator = get_object_or_404(CoordinatorProfile, id=coordinator_id)
    user = coordinator.user
    coord_name = user.get_full_name().strip() or user.username or user.email if user else f"Coordinator #{coordinator.id}"

    InternProfile.objects.filter(supervisor=coordinator).update(supervisor=None)
    coordinator.delete()

    if user and user.role != User.ROLE_ADMIN and not user.is_superuser:
        user.delete()

    return JsonResponse({'success': True, 'message': f'{coord_name} removed as coordinator successfully.'})


@login_required
@require_POST
def create_department_api(request):
    """API endpoint allowing Admins to create a new rotation Department."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'error': 'Department name is required.'}, status=400)

    dept, created = Department.objects.get_or_create(
        name=name,
        defaults={'description': description}
    )

    if not created:
        return JsonResponse({'success': False, 'error': 'Department already exists.'}, status=400)

    return JsonResponse({'success': True, 'message': f"Department '{dept.name}' created successfully."})


@login_required
@require_POST
def send_message_api(request):
    """API for Interns and Coordinators to communicate."""
    user = request.user
    recipient_id = request.POST.get('recipient_id')
    content = request.POST.get('content', '').strip()
    task_id = request.POST.get('task_id')

    if not recipient_id or not content:
        return JsonResponse({'success': False, 'error': 'Recipient and message content are required.'}, status=400)

    recipient = get_object_or_404(User, pk=recipient_id)

    allowed = False
    if user.role == User.ROLE_INTERN:
        intern_profile = getattr(user, 'intern_profile', None)
        if intern_profile and intern_profile.supervisor and intern_profile.supervisor.user == recipient:
            allowed = True
    elif user.role == User.ROLE_COORDINATOR:
        coord_profile = getattr(user, 'coordinator_profile', None)
        if coord_profile:
            intern_recipient_profile = getattr(recipient, 'intern_profile', None)
            if intern_recipient_profile and intern_recipient_profile.supervisor == coord_profile:
                allowed = True
    elif user.role == User.ROLE_ADMIN or user.is_superuser:
        allowed = True

    if not allowed:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    task = DailyTask.objects.filter(pk=task_id).first() if task_id else None

    msg = Message.objects.create(sender=user, recipient=recipient, content=content, task=task)

    Notification.objects.create(
        recipient=recipient,
        sender=user,
        title=f"New Message from {user.get_full_name() or user.username}",
        message=content[:100] + ('...' if len(content) > 100 else ''),
        link=(
            f"/coordinator/?chat={user.id}"
            if recipient.role == User.ROLE_COORDINATOR
            else f"/intern/?chat={user.id}"
        ),
        notification_type=Notification.TYPE_MESSAGE
    )

    return JsonResponse({
        'success': True,
        'message_id': msg.id,
        'sender': user.get_full_name() or user.username,
        'content': msg.content,
        'created_at': msg.created_at.strftime('%b %d, %H:%M')
    })


@login_required
def get_messages_api(request):
    """API returning conversation history."""
    target_user_id = request.GET.get('target_user_id')
    if not target_user_id:
        return JsonResponse({'success': False, 'error': 'Target user required.'}, status=400)

    target_user = get_object_or_404(User, pk=target_user_id)
    user = request.user

    allowed = False
    if user.role == User.ROLE_INTERN:
        intern_profile = getattr(user, 'intern_profile', None)
        if intern_profile and intern_profile.supervisor and intern_profile.supervisor.user == target_user:
            allowed = True
    elif user.role == User.ROLE_COORDINATOR:
        coord_profile = getattr(user, 'coordinator_profile', None)
        if coord_profile:
            target_intern_profile = getattr(target_user, 'intern_profile', None)
            if target_intern_profile and target_intern_profile.supervisor == coord_profile:
                allowed = True
    elif user.role == User.ROLE_ADMIN or user.is_superuser:
        allowed = True

    if not allowed:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    messages_qs = Message.objects.filter(
        (Q(sender=user, recipient=target_user) | Q(sender=target_user, recipient=user))
    ).order_by('created_at')

    Message.objects.filter(sender=target_user, recipient=user, is_read=False).update(is_read=True)

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'is_me': m.sender == user,
            'content': m.content,
            'created_at': m.created_at.strftime('%b %d, %I:%M %p')
        })

    return JsonResponse({
        'success': True,
        'target_user_name': target_user.get_full_name() or target_user.username,
        'messages': messages_data
    })


@login_required
def get_notifications_api(request):
    """API returning notifications."""
    base_notifications = Notification.objects.filter(recipient=request.user)
    unread_count = base_notifications.filter(is_read=False).count()
    notifications = base_notifications.order_by('-created_at')[:15]

    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'link': n.link or '#',
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d, %H:%M'),
            'sender_id': n.sender.id if n.sender else None,
            'sender_name': (n.sender.get_full_name() or n.sender.username if n.sender else ''),
        })
    return JsonResponse({'success': True, 'unread_count': unread_count, 'notifications': data})


@login_required
@require_POST
def mark_notification_read_api(request, notification_id):
    """Marks notification as read."""
    n = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    n.is_read = True
    n.save()
    return JsonResponse({'success': True})


def _compute_task_stats(tasks_qs):
    total = tasks_qs.count()
    completed = tasks_qs.filter(status='completed').count()
    in_progress = tasks_qs.filter(status='in_progress').count()
    pending = tasks_qs.filter(status__in=['not_started', 'submitted', 'pending']).count()
    pct = round((completed / total) * 100, 1) if total > 0 else 0
    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'pct': pct,
    }


@login_required
@require_POST
def update_task_status(request, task_id):
    """AJAX endpoint for interns, coordinators, and admins to update task status."""
    try:
        task = get_object_or_404(DailyTask, pk=task_id)
        week = task.topic.week if task.topic else None

        intern_profile = getattr(request.user, 'intern_profile', None)
        coord_profile = getattr(request.user, 'coordinator_profile', None)

        owning_intern = task.intern or (week.intern if week else None)

        allowed = False
        if intern_profile and owning_intern == intern_profile:
            allowed = True
        elif coord_profile and owning_intern and (
            owning_intern.supervisor == coord_profile
            or (week and week.department and week.department.coordinator == coord_profile)
        ):
            allowed = True
        elif request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', '') == 'admin':
            allowed = True

        if not allowed:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        if week and week.is_locked and not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'This week is locked and its tasks are read-only.'}, status=403)

        new_status = request.POST.get('status', '').strip()
        valid_statuses = [choice[0] for choice in DailyTask.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': f'Invalid status: {new_status}'}, status=400)

        task.status = new_status
        task.updated_at = timezone.now()
        task.save(update_fields=['status', 'updated_at'])

        notify_target = None
        if week and week.department and week.department.coordinator and week.department.coordinator.user:
            notify_target = week.department.coordinator.user
        elif owning_intern and owning_intern.supervisor and owning_intern.supervisor.user:
            notify_target = owning_intern.supervisor.user

        if notify_target and owning_intern:
            try:
                Notification.objects.create(
                    recipient=notify_target,
                    sender=request.user,
                    title=f"Task Status Updated: {owning_intern.full_name}",
                    message=f"Task '{task.title}' updated to '{task.get_status_display()}'.",
                    link=f"/dashboard/coordinator/?intern_id={owning_intern.id}",
                    notification_type=Notification.TYPE_TASK,
                )
            except Exception as notif_err:
                print("Notification creation skipped:", str(notif_err))

        overall_stats = _compute_task_stats(DailyTask.objects.filter(intern=owning_intern)) if owning_intern else _compute_task_stats(DailyTask.objects.none())

        if week:
            week_tasks = DailyTask.objects.filter(topic__week=week, intern=owning_intern) if owning_intern else DailyTask.objects.filter(topic__week=week)
            week_stats = _compute_task_stats(week_tasks)
        else:
            week_stats = _compute_task_stats(DailyTask.objects.none())

        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'new_status': task.status,
            'status_display': task.get_status_display(),
            'total_tasks': overall_stats['total'],
            'completed_tasks': overall_stats['completed'],
            'in_progress_tasks': overall_stats['in_progress'],
            'pending_tasks': overall_stats['pending'],
            'progress_pct': overall_stats['pct'],
            'week_id': week.id if week else None,
            'week_total_tasks': week_stats['total'],
            'week_completed_tasks': week_stats['completed'],
            'week_in_progress_tasks': week_stats['in_progress'],
            'week_pending_tasks': week_stats['pending'],
            'week_progress_pct': week_stats['pct'],
        })

    except Exception as exc:
        print("UPDATE TASK STATUS ERROR:", str(exc))
        return JsonResponse({'success': False, 'error': f'Server Error: {str(exc)}'}, status=500)


@login_required
def intern_detail_api(request, intern_id):
    """API returning detailed profile, schedule, and tasks for modal view."""
    intern = get_object_or_404(InternProfile, pk=intern_id)
    user = request.user

    if user.role == User.ROLE_COORDINATOR:
        coord_profile = getattr(user, 'coordinator_profile', None)
        if intern.supervisor != coord_profile:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    elif user.role == User.ROLE_INTERN:
        if intern.user != user:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    all_tasks = DailyTask.objects.filter(intern=intern)
    total = all_tasks.count()
    completed = all_tasks.filter(status='completed').count()
    pct = round((completed / total) * 100, 1) if total else 0

    assignments = DepartmentAssignment.objects.filter(intern=intern)
    assigned_depts = [a.department for a in assignments]

    if assigned_depts:
        weeks_qs = InternshipWeek.objects.filter(department__in=assigned_depts).prefetch_related('topics__tasks').order_by('week_number')
    else:
        weeks_qs = InternshipWeek.objects.all().prefetch_related('topics__tasks').order_by('week_number')

    weeks_data = []
    for week in weeks_qs:
        topics_data = []
        for topic in week.topics.all():
            tasks_data = []
            for task in topic.tasks.filter(intern=intern):
                has_file = bool(task.attached_file or task.attached_file_url)
                file_name = os.path.basename(task.attached_file.name) if task.attached_file else ''
                
                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description or '',
                    'due_date': str(task.date) if task.date else '',
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'has_submission': has_file or task.status == 'submitted',
                    'file_name': file_name,
                    'file_url': task.attached_file.url if task.attached_file else (task.attached_file_url or ''),
                })
            topics_data.append({
                'id': topic.id,
                'title': topic.title,
                'tasks': tasks_data
            })

        weeks_data.append({
            'id': week.id,
            'week_number': week.week_number,
            'department': week.department.name if week.department else 'General',
            'start_date': str(week.start_date),
            'end_date': str(week.end_date),
            'course_outline_title': week.course_outline_title or '',
            'course_outline_text': week.course_outline_text or '',
            'course_outline_file_url': week.course_outline_file.url if week.course_outline_file else '',
            'topics': topics_data
        })

    return JsonResponse({
        'success': True,
        'intern': {
            'id': intern.id,
            'full_name': intern.full_name,
            'intern_id': intern.intern_id,
            'university': intern.university,
            'degree': intern.degree,
            'start_date': str(intern.start_date) if intern.start_date else '',
            'end_date': str(intern.end_date) if intern.end_date else '',
            'coordinator': intern.supervisor.user.get_full_name() if (intern.supervisor and intern.supervisor.user) else "Unassigned",
            'coordinator_user_id': intern.supervisor.user.id if (intern.supervisor and intern.supervisor.user) else None,
            'is_activated': intern.is_activated,
            'activation_token': intern.activation_token
        },
        'stats': {
            'completed': completed,
            'total': total,
            'pct': pct
        },
        'weeks': weeks_data
    })


@login_required
@require_POST
def delete_message_api(request, message_id):
    """Allows sender or Admin to delete a message."""
    msg = get_object_or_404(Message, pk=message_id)

    if msg.sender != request.user and request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    msg.delete()
    return JsonResponse({'success': True, 'message': 'Message deleted successfully.'})


@login_required
@require_POST
def delete_task_api(request, task_id):
    """Allows Intern, Coordinator, or Admin to delete a daily task."""
    task = get_object_or_404(DailyTask, pk=task_id)
    user = request.user

    owning_intern = task.intern or (task.topic.week.intern if task.topic and task.topic.week else None)
    coord_profile = getattr(user, 'coordinator_profile', None)

    allowed = False
    if getattr(user, 'intern_profile', None) and owning_intern == user.intern_profile:
        allowed = True
    elif coord_profile and owning_intern and owning_intern.supervisor == coord_profile:
        allowed = True
    elif user.is_staff or user.is_superuser or user.role == User.ROLE_ADMIN:
        allowed = True

    if not allowed:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    task_id_ref = task.id
    task.delete()

    return JsonResponse({'success': True, 'message': 'Task deleted successfully.', 'task_id': task_id_ref})