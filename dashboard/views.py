import datetime
import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import DailyTask, Department, InternshipWeek, TaskSubmission, Topic
from accounts.decorators import role_required
from accounts.models import InternProfile, SupervisorProfile, User
from .models import Message, Notification


def _is_admin_user(user):
    """Return True for portal admins, Django staff users, and superusers."""
    return (
        user.role == User.ROLE_ADMIN
        or user.is_superuser
        or user.is_staff
    )

# ==========================================
# Official IFL Internship Program Rotation Schedule Matrix
# ==========================================
ROTATION_SCHEDULES = {
    'EMAAN KASHIF': ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation'],
    'MENEHIL': ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation'],
    'MUHAMMAD DANIYAL': ['IT Operations', 'DCI', 'Networks & Security', 'Software dev', 'ERP', 'Report & Presentation'],
    'NIAZ SHAH': ['IT Operations', 'DCI', 'Networks & Security', 'Software dev', 'ERP', 'Report & Presentation'],
    'HASSAN TARIQ': ['DCI', 'Networks & Security', 'Software dev', 'ERP', 'IT Operations', 'Report & Presentation'],
    'SUBHAN': ['Networks & Security', 'DCI', 'Software dev', 'ERP', 'IT Operations', 'Report & Presentation'],
    'Ayesha': ['DCI','Software dev','ERP','IT Operations','Networks & Security','Report & Presentation']
}

DEFAULT_ROTATION = ['ERP', 'Software dev', 'DCI', 'IT Operations', 'Networks & Security', 'Report & Presentation']


def build_full_intern_schedule(profile):
    """
    Automated Helper: Generates all 6 rotation weeks and default daily tasks 
    for an intern profile based on the official IFL schedule matrix.
    """
    if profile.weeks.exists():
        return  # Avoid duplicating if weeks already exist

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

        # Build initial topic & daily tasks
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
    """Sends the logged-in user to the dashboard that matches their role."""
    role = request.user.role
    if role == User.ROLE_INTERN:
        return redirect('dashboard:intern_dashboard')
    if role == User.ROLE_SUPERVISOR:
        return redirect('dashboard:supervisor_dashboard')
    if role == User.ROLE_ADMIN or request.user.is_superuser or request.user.is_staff:
        return redirect('dashboard:admin_dashboard')
    return redirect('accounts:login')


@role_required('admin')
def admin_dashboard(request):
  """Dedicated Admin Dashboard:
  Overview of system metrics, intern onboarding, supervisor management, and
  department focus areas.
  """
  total_interns = InternProfile.objects.filter(
    is_active=True
    ).count()

  activated_interns = InternProfile.objects.filter(
    is_active=True,
    is_activated=True
    ).count()

  pending_activations = InternProfile.objects.filter(
    is_active=True,
    is_activated=False
   ).count()
  total_departments = Department.objects.count()

  # Ensure every User with role='supervisor' has a linked SupervisorProfile
  supervisor_users = User.objects.filter(role=User.ROLE_SUPERVISOR)
  for sup_user in supervisor_users:
    SupervisorProfile.objects.get_or_create(
        user=sup_user,
        defaults={'department_focus': 'Enterprise Operations'},
    )

  # Fetch all supervisor profiles with linked user data
  supervisors = SupervisorProfile.objects.select_related('user').all()
  total_supervisors = supervisors.count()

  interns = InternProfile.objects.select_related(
      'supervisor__user', 'user'
  ).all()

  # Manage Schedules must show active interns only.
  # The main roster still receives `interns`, including removed/archived interns.
  schedule_interns = InternProfile.objects.filter(
      is_active=True
  ).select_related(
      'supervisor__user', 'user'
  )

  departments = Department.objects.all()

  context = {
      'total_interns': total_interns,
      'activated_interns': activated_interns,
      'pending_activations': pending_activations,
      'total_supervisors': total_supervisors,
      'total_departments': total_departments,
      'interns': interns,
      'schedule_interns': schedule_interns,
      'supervisors': supervisors,
      'departments': departments,
  }
  return render(request, 'dashboard/admin_dashboard.html', context)


@role_required('intern')
def intern_dashboard(request):
    """Intern dashboard displaying current rotation week, tasks, submissions, and progress."""
    profile = get_object_or_404(InternProfile, user=request.user)
    today = timezone.localdate()

    ended_weeks = profile.weeks.filter(
        end_date__lt=today
    )

    for week in ended_weeks:

        notification_title = (
            f"Week {week.week_number} Completed"
        )

        # Prevent duplicate notification every time
        # the intern refreshes the dashboard
        already_notified = Notification.objects.filter(
            recipient=request.user,
            title=notification_title
        ).exists()

        if not already_notified:

            Notification.objects.create(
                recipient=request.user,
                sender=None,
                title=notification_title,
                message=(
                    f"Your Week {week.week_number} "
                    f"({week.department.name}) has ended. "
                    f"You can now review your completed work "
                    f"and continue to the next rotation week."
                ),
                link="/intern/",
                notification_type=Notification.TYPE_TASK
            )

    current_week = profile.weeks.order_by('-week_number').first()
    all_weeks = profile.weeks.prefetch_related('topics__tasks__submissions').order_by('week_number')
    
    current_tasks = (
        DailyTask.objects.filter(topic__week=current_week).order_by('day_number')
        if current_week else DailyTask.objects.none()
    )

    all_tasks = DailyTask.objects.filter(topic__week__intern=profile)
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status=DailyTask.STATUS_COMPLETED).count()
    in_progress_tasks = all_tasks.filter(status=DailyTask.STATUS_IN_PROGRESS).count()
    pending_tasks = all_tasks.filter(status=DailyTask.STATUS_PENDING).count()
    progress_pct = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0

    unread_notifications_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    context = {
        'profile': profile,
        'current_week': current_week,
        'all_weeks': all_weeks,
        'current_tasks': current_tasks,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'pending_tasks': pending_tasks,
        'progress_pct': progress_pct,
        'unread_notifications_count': unread_notifications_count,
    }
    return render(request, 'dashboard/intern_dashboard.html', context)


@role_required('supervisor')
def supervisor_dashboard(request):
    """Supervisor dashboard managing active and offboarded assigned interns, task reviews, and messages."""
    profile = get_object_or_404(SupervisorProfile, user=request.user)
    
    # Check if supervisor toggled offboarded/completed view
    show_archived = request.GET.get('archived') == 'true'
    target_active_status = not show_archived

    # Fetch interns assigned to this supervisor (handles both direct profile link & fallback name match)
    interns = InternProfile.objects.filter(
        Q(supervisor=profile) | Q(custom_supervisor_name__icontains=request.user.first_name),
        is_active=target_active_status
    ).select_related('user').distinct()

    intern_rows = []
    total_cohort_tasks = 0
    total_cohort_completed = 0

    for intern in interns:
        tasks = DailyTask.objects.filter(
        topic__week__intern=intern
        )
        total = tasks.count()
        completed = tasks.filter(status=DailyTask.STATUS_COMPLETED).count()
        in_progress = tasks.filter(status=DailyTask.STATUS_IN_PROGRESS).count()
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
    supervisors = SupervisorProfile.objects.select_related('user').all()
    unread_messages_count = Message.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    context = {
        'profile': profile,
        'intern_rows': intern_rows,
        'total_interns': len(intern_rows),
        'cohort_pct': cohort_pct,
        'total_cohort_completed': total_cohort_completed,
        'total_cohort_tasks': total_cohort_tasks,
        'departments': departments,
        'supervisors': supervisors,
        'show_archived': show_archived,
        'unread_messages_count': unread_messages_count,
    }
    return render(request, 'dashboard/supervisor_dashboard.html', context)

@login_required
@require_POST
def issue_intern_id_api(request):
    """
    API endpoint allowing Admins or Supervisors to issue a new Intern ID & activation token.
    Automatically provisions the full 6-week IFL rotation schedule.
    """
    user = request.user
    if user.role not in [User.ROLE_ADMIN, User.ROLE_SUPERVISOR] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    full_name = request.POST.get('full_name', '').strip()
    university = request.POST.get('university', '').strip()
    degree = request.POST.get('degree', '').strip()
    supervisor_id = request.POST.get('supervisor_id')
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

    supervisor = None
    if supervisor_id:
        supervisor = SupervisorProfile.objects.filter(pk=supervisor_id).first()
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor = getattr(user, 'supervisor_profile', None)

    profile = InternProfile.objects.create(
        full_name=full_name,
        university=university,
        degree=degree,
        start_date=start_date,
        end_date=end_date,
        supervisor=supervisor,
        is_activated=False
    )
    profile.generate_activation_token()

    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    activation_url = f"{scheme}://{host}/accounts/activate/?token={profile.activation_token}"

    return JsonResponse({
        'success': True,
        'message': f"Intern Profile created successfully!",
        'intern_id': profile.intern_id,
        'full_name': profile.full_name,
        'activation_token': profile.activation_token,
        'activation_url': activation_url,
        'supervisor': profile.supervisor.user.get_full_name() if (profile.supervisor and profile.supervisor.user) else "Unassigned"
    })


@login_required
@require_POST
def create_custom_week_api(request):
    """
    API allowing Supervisors and Admins to add/edit rotation weeks and daily tasks 
    directly from the web portal UI without touching the code.
    """
    user = request.user
    if user.role not in [User.ROLE_ADMIN, User.ROLE_SUPERVISOR] and not user.is_superuser:
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
    """
    Admin-only API:
    Returns the complete manually assigned schedule for an intern.
    """

    if not _is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    # Removed/archived interns are intentionally excluded from schedule management.
    intern = get_object_or_404(
        InternProfile,
        id=intern_id,
        is_active=True
    )

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

        for topic in week.topics.all():
            for task in topic.tasks.all().order_by('day_number'):
                tasks_data.append({
                    'id': task.id,
                    'day_number': task.day_number,
                    'title': task.title,
                    'description': task.description or '',
                    'due_date': (
                        str(task.due_date)
                        if task.due_date
                        else ''
                    ),
                })

        weeks_data.append({
            'id': week.id,
            'week_number': week.week_number,
            'department_id': week.department_id,
            'department_name': week.department.name,
            'start_date': str(week.start_date),
            'end_date': str(week.end_date),

            'course_outline_title':
                week.course_outline_title or '',

            'course_outline_text':
                week.course_outline_text or '',

            'course_outline_file_name': (
                os.path.basename(
                    week.course_outline_file.name
                )
                if week.course_outline_file
                else ''
            ),

            'course_outline_file_url': (
                week.course_outline_file.url
                if week.course_outline_file
                else ''
            ),

            'tasks': tasks_data,
        })

    return JsonResponse({
        'success': True,

        'intern': {
            'id': intern.id,
            'intern_id': intern.intern_id,
            'full_name': intern.full_name,
            'start_date': (
                str(intern.start_date)
                if intern.start_date
                else ''
            ),
            'end_date': (
                str(intern.end_date)
                if intern.end_date
                else ''
            ),
        },

        'weeks': weeks_data
    })

@login_required
@require_POST
def save_intern_schedule_week_api(request, intern_id):
    """
    Admin-only API:
    Creates or updates one week of an intern's schedule.
    """

    if not _is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    # Only active interns can receive or edit schedules.
    intern = get_object_or_404(
        InternProfile,
        id=intern_id,
        is_active=True
    )

    week_id = request.POST.get('week_id', '').strip()
    week_number = request.POST.get('week_number', '').strip()
    department_id = request.POST.get('department_id', '').strip()
    start_date_str = request.POST.get('start_date', '').strip()
    end_date_str = request.POST.get('end_date', '').strip()

    course_outline_title = request.POST.get(
        'course_outline_title',
        ''
    ).strip()

    course_outline_text = request.POST.get(
        'course_outline_text',
        ''
    ).strip()

    # ----------------------------
    # Basic validation
    # ----------------------------

    if not week_number:
        return JsonResponse({
            'success': False,
            'error': 'Week number is required.'
        }, status=400)

    try:
        week_number = int(week_number)

        if week_number < 1:
            raise ValueError

    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid week number.'
        }, status=400)

    if not department_id:
        return JsonResponse({
            'success': False,
            'error': 'Department is required.'
        }, status=400)

    department = get_object_or_404(
        Department,
        id=department_id
    )

    if not start_date_str or not end_date_str:
        return JsonResponse({
            'success': False,
            'error': 'Start date and end date are required.'
        }, status=400)

    try:
        start_date = datetime.datetime.strptime(
            start_date_str,
            '%Y-%m-%d'
        ).date()

        end_date = datetime.datetime.strptime(
            end_date_str,
            '%Y-%m-%d'
        ).date()

    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid date format.'
        }, status=400)

    if end_date < start_date:
        return JsonResponse({
            'success': False,
            'error': 'End date cannot be before start date.'
        }, status=400)

    # ----------------------------
    # Existing week OR new week
    # ----------------------------

    if week_id:

        week = get_object_or_404(
            InternshipWeek,
            id=week_id,
            intern=intern
        )

        duplicate = InternshipWeek.objects.filter(
            intern=intern,
            week_number=week_number
        ).exclude(id=week.id).exists()

        if duplicate:
            return JsonResponse({
                'success': False,
                'error': (
                    f'Week {week_number} already exists '
                    f'for this intern.'
                )
            }, status=400)

    else:

        if InternshipWeek.objects.filter(
            intern=intern,
            week_number=week_number
        ).exists():

            return JsonResponse({
                'success': False,
                'error': (
                    f'Week {week_number} already exists '
                    f'for this intern.'
                )
            }, status=400)

        week = InternshipWeek(
            intern=intern
        )

    # ----------------------------
    # Save week
    # ----------------------------

    week.week_number = week_number
    week.department = department
    week.start_date = start_date
    week.end_date = end_date
    week.course_outline_title = course_outline_title
    week.course_outline_text = course_outline_text

    # Optional uploaded outline
    uploaded_file = request.FILES.get(
        'course_outline_file'
    )

    if uploaded_file:

        allowed_extensions = (
            '.pdf',
            '.doc',
            '.docx'
        )

        file_name = uploaded_file.name.lower()

        if not file_name.endswith(allowed_extensions):
            return JsonResponse({
                'success': False,
                'error': (
                    'Course outline must be a '
                    'PDF, DOC, or DOCX file.'
                )
            }, status=400)

        # 10 MB maximum
        if uploaded_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': (
                    'Course outline file cannot '
                    'be larger than 10 MB.'
                )
            }, status=400)

        week.course_outline_file = uploaded_file

    try:
        week.save()
    except Exception as exc:
        # Keep AJAX responses as JSON instead of returning Django's HTML 500 page.
        # The server log still contains the underlying storage/database error.
        return JsonResponse({
            'success': False,
            'error': (
                'The week could not be saved. '
                'If a file was attached, check the configured file storage. '
                f'Details: {exc}'
            )
        }, status=500)

    # ----------------------------
    # Ensure the week has a topic
    # ----------------------------

    topic = week.topics.order_by('order').first()

    if not topic:
        topic = Topic.objects.create(
            week=week,
            title=f'{department.name} Weekly Tasks',
            order=1
        )

    return JsonResponse({
        'success': True,
        'message': (
            f'Week {week.week_number} saved successfully.'
        ),
        'week_id': week.id
    })

@login_required
@require_POST
def delete_intern_schedule_week_api(
    request,
    intern_id,
    week_id
):
    """
    Admin-only API:
    Deletes a schedule week if it has no submitted work.
    """

    if not _is_admin_user(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    intern = get_object_or_404(
        InternProfile,
        id=intern_id,
        is_active=True
    )

    week = get_object_or_404(
        InternshipWeek,
        id=week_id,
        intern=intern
    )

    # Protect intern submission history
    has_submissions = TaskSubmission.objects.filter(
        task__topic__week=week
    ).exists()

    if has_submissions:
        return JsonResponse({
            'success': False,
            'error': (
                'This week cannot be deleted because '
                'the intern has already submitted work for it.'
            )
        }, status=400)

    week_number = week.week_number
    week.delete()

    return JsonResponse({
        'success': True,
        'message': f'Week {week_number} deleted successfully.'
    })

@login_required
@require_POST
def update_intern_supervisor_api(request, intern_id):
    """API endpoint allowing Admins or Supervisors to inline-update an intern's supervisor."""
    user = request.user
    if user.role not in [User.ROLE_ADMIN, User.ROLE_SUPERVISOR] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    intern = get_object_or_404(InternProfile, pk=intern_id)
    sup_name = request.POST.get('supervisor_name', '').strip()

    if not sup_name:
        intern.supervisor = None
        intern.custom_supervisor_name = ''
    else:
        supervisor_obj = SupervisorProfile.objects.filter(
            Q(user__first_name__icontains=sup_name) |
            Q(user__last_name__icontains=sup_name) |
            Q(user__username__icontains=sup_name)
        ).first()

        if supervisor_obj:
            intern.supervisor = supervisor_obj
            intern.custom_supervisor_name = ''
        else:
            intern.supervisor = None
            intern.custom_supervisor_name = sup_name

    intern.save()
    return JsonResponse({'success': True, 'message': 'Supervisor updated successfully.'})

@login_required
@require_POST
def remove_intern_api(request, intern_id):
    # Admin / superuser can remove any intern
    if _is_admin_user(request.user):
        intern = get_object_or_404(
            InternProfile,
            id=intern_id
        )

    # Supervisor can only remove their assigned intern
    elif request.user.role == User.ROLE_SUPERVISOR:
        profile = get_object_or_404(
            SupervisorProfile,
            user=request.user
        )

        intern = get_object_or_404(
            InternProfile,
            id=intern_id,
            supervisor=profile
        )

    else:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    # Soft remove / archive intern
    intern.is_active = False
    intern.save(update_fields=['is_active'])

    return JsonResponse({
        'success': True,
        'message': 'Intern removed successfully.'
    })

@login_required
@require_POST
def restore_intern_api(request, intern_id):
    # Admin / superuser can restore any intern
    if _is_admin_user(request.user):
        intern = get_object_or_404(
            InternProfile,
            id=intern_id
        )

    # Supervisor can only restore their assigned intern
    elif request.user.role == User.ROLE_SUPERVISOR:
        profile = get_object_or_404(
            SupervisorProfile,
            user=request.user
        )

        intern = get_object_or_404(
            InternProfile,
            id=intern_id,
            supervisor=profile
        )

    else:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    # Restore intern
    intern.is_active = True
    intern.save(update_fields=['is_active'])

    return JsonResponse({
        'success': True,
        'message': 'Intern restored successfully.'
    })

@login_required
@require_POST
def intern_edit_task_api(request, task_id):

    if request.user.role != User.ROLE_INTERN:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    intern = get_object_or_404(
        InternProfile,
        user=request.user
    )

    task = get_object_or_404(
        DailyTask,
        id=task_id,
        topic__week__intern=intern
    )

    title = request.POST.get('title', '').strip()
    description = request.POST.get(
        'description',
        ''
    ).strip()
    due_date = request.POST.get(
        'due_date',
        ''
    ).strip()

    if not title:
        return JsonResponse({
            'success': False,
            'error': 'Task title is required.'
        }, status=400)

    task.title = title
    task.description = description

    if due_date:
        try:
            task.due_date = datetime.datetime.strptime(
                due_date,
                '%Y-%m-%d'
            ).date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid due date.'
            }, status=400)

    task.save()

    return JsonResponse({
        'success': True,
        'message': 'Task updated successfully.'
    })

@login_required
@require_POST
def intern_add_day_api(request, week_id):
    """
    Allows an intern to add a new daily task row
    to one of their own internship weeks.
    """

    # Get logged-in intern
    intern = get_object_or_404(
        InternProfile,
        user=request.user
    )

    # IMPORTANT:
    # Intern can only add a day to their own week
    week = get_object_or_404(
        InternshipWeek,
        id=week_id,
        intern=intern
    )

    # Get the first/main topic of this week
    topic = week.topics.order_by('order').first()

    # Safety fallback in case a week somehow has no topic
    if not topic:
        topic = Topic.objects.create(
            week=week,
            title=f"{week.department.name} Tasks",
            order=1
        )

    # Find the highest existing day number in THIS WEEK
    last_task = (
        DailyTask.objects
        .filter(topic__week=week)
        .order_by('-day_number')
        .first()
    )

    if last_task:
        next_day_number = last_task.day_number + 1
    else:
        next_day_number = 1

    # Optional protection:
    # an internship week normally should not exceed 7 days
    if next_day_number > 7:
        return JsonResponse({
            'success': False,
            'error': 'A week cannot contain more than 7 days.'
        }, status=400)

    # Calculate the date for the new day
    due_date = week.start_date + datetime.timedelta(
        days=next_day_number - 1
    )

    # Don't go past week end date
    if due_date > week.end_date:
        due_date = week.end_date

    # Create editable placeholder task
    task = DailyTask.objects.create(
        topic=topic,
        day_number=next_day_number,
        title=f"Day {next_day_number} Task",
        description="Add task description...",
        due_date=due_date,
        status=DailyTask.STATUS_PENDING
    )

    return JsonResponse({
        'success': True,
        'message': f'Day {next_day_number} added successfully.',
        'task_id': task.id,
        'day_number': task.day_number
    })


@login_required
@require_POST
def update_intern_api(request, intern_id):
    # Only admin/superuser can edit intern details
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    intern = get_object_or_404(InternProfile, id=intern_id)

    # Get submitted values
    full_name = request.POST.get('full_name', '').strip()
    university = request.POST.get('university', '').strip()
    degree = request.POST.get('degree', '').strip()
    supervisor_name = request.POST.get('supervisor_name', '').strip()

    # Required fields
    if not full_name:
        return JsonResponse({
            'success': False,
            'error': 'Full name is required.'
        }, status=400)

    if not university:
        return JsonResponse({
            'success': False,
            'error': 'University is required.'
        }, status=400)

    if not degree:
        return JsonResponse({
            'success': False,
            'error': 'Degree / domain is required.'
        }, status=400)

    # Update normal intern details
    intern.full_name = full_name
    intern.university = university
    intern.degree = degree

    # ------------------------------------
    # UPDATE SUPERVISOR
    # ------------------------------------

    # Blank field = unassign supervisor
    if not supervisor_name:
        intern.supervisor = None
        intern.custom_supervisor_name = ''

    else:
        matched_supervisor = None

        # Search existing supervisors by their displayed full name
        supervisors = SupervisorProfile.objects.select_related('user').all()

        for supervisor in supervisors:
            existing_name = supervisor.user.get_full_name().strip()

            # If first/last name is empty, use username
            if not existing_name:
                existing_name = supervisor.user.username

            if existing_name.lower() == supervisor_name.lower():
                matched_supervisor = supervisor
                break

        # Existing supervisor selected
        if matched_supervisor:
            intern.supervisor = matched_supervisor
            intern.custom_supervisor_name = ''

        # Manually typed supervisor
        else:
            intern.supervisor = None
            intern.custom_supervisor_name = supervisor_name

    intern.save()

    return JsonResponse({
        'success': True,
        'message': 'Intern details updated successfully.'
    })

@login_required
@require_POST
def update_task_api(request, task_id):
    """Supervisor edits a daily task's title, description, or due date — reflects immediately on intern dashboard."""
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

    if (
        request.user.role != User.ROLE_ADMIN
        and not request.user.is_superuser
    ):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    first_name = request.POST.get(
        'first_name',
        ''
    ).strip()

    last_name = request.POST.get(
        'last_name',
        ''
    ).strip()

    email = request.POST.get(
        'email',
        ''
    ).strip().lower()

    password = request.POST.get(
        'password',
        ''
    )

    confirm_password = request.POST.get(
        'confirm_password',
        ''
    )

    if not first_name or not email or not password:
        return JsonResponse({
            'success': False,
            'error': 'First name, email and password are required.'
        }, status=400)

    if password != confirm_password:
        return JsonResponse({
            'success': False,
            'error': 'Passwords do not match.'
        }, status=400)

    if len(password) < 8:
        return JsonResponse({
            'success': False,
            'error': 'Password must be at least 8 characters.'
        }, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({
            'success': False,
            'error': 'An account with this email already exists.'
        }, status=400)

    # Generate a unique username from the email
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
        'message': (
            f'Admin account created successfully for '
            f'{admin_user.get_full_name() or admin_user.email}.'
        )
    })

@login_required
@require_POST
def create_supervisor_api(request):
    """
    Allow admin to add a supervisor using:
    - full name
    - real email
    - department

    The supervisor account is created without a usable password.
    A one-time activation link is returned so the supervisor can
    set their own password securely.
    """

    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    full_name = request.POST.get('full_name', '').strip()
    email = request.POST.get('email', '').strip().lower()
    department_focus = request.POST.get(
        'department_focus',
        ''
    ).strip()

    # -----------------------------
    # Validation
    # -----------------------------
    if not full_name:
        return JsonResponse({
            'success': False,
            'error': 'Supervisor name is required.'
        }, status=400)

    if not email:
        return JsonResponse({
            'success': False,
            'error': 'Supervisor email is required.'
        }, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({
            'success': False,
            'error': 'A user with this email already exists.'
        }, status=400)

    # -----------------------------
    # Split full name
    # -----------------------------
    name_parts = full_name.split()

    first_name = name_parts[0]

    if len(name_parts) > 1:
        last_name = ' '.join(name_parts[1:])
    else:
        last_name = ''

    # -----------------------------
    # Generate unique username
    # -----------------------------
    base_username = full_name.lower().replace(' ', '_')

    username = base_username
    counter = 1

    while User.objects.filter(username__iexact=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    # -----------------------------
    # Create supervisor User
    # -----------------------------
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=User.ROLE_SUPERVISOR,
        is_staff=False,

        # Supervisor cannot login until activation
        is_active=False
    )

    # Admin does NOT choose supervisor password
    user.set_unusable_password()
    user.save()

    # -----------------------------
    # Create Supervisor Profile
    # -----------------------------
    profile = SupervisorProfile.objects.create(
        user=user,
        department_focus=department_focus or "General",
        is_activated=False
    )

    # -----------------------------
    # Generate activation token
    # -----------------------------
    token = profile.generate_activation_token()

    # -----------------------------
    # Build activation link
    # -----------------------------
    activation_url = request.build_absolute_uri(
        f'/accounts/supervisor-activate/?token={token}'
    )

    return JsonResponse({
        'success': True,
        'message': f'Supervisor {full_name} added successfully.',
        'full_name': full_name,
        'email': email,
        'supervisor_id': profile.id,
        'activation_url': activation_url
    })

@login_required
@require_POST
def delete_supervisor_api(request, supervisor_id):

    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied.'
        }, status=403)

    supervisor = get_object_or_404(
        SupervisorProfile,
        id=supervisor_id
    )

    supervisor_name = (
        supervisor.user.get_full_name().strip()
        or supervisor.user.username
    )

    user = supervisor.user

    # Keep interns — only remove their supervisor assignment.
    InternProfile.objects.filter(
        supervisor=supervisor
    ).update(
        supervisor=None,
        custom_supervisor_name=''
    )

    # Delete supervisor profile
    supervisor.delete()

    # Delete the internal User created for this supervisor
    if user:
        user.delete()

    return JsonResponse({
        'success': True,
        'message': f'{supervisor_name} deleted successfully.'
    })

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

    return JsonResponse({
        'success': True,
        'message': f"Department '{dept.name}' created successfully."
    })


@login_required
@require_POST
def send_message_api(request):
    """API for Interns and Supervisors to communicate."""
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
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor_profile = getattr(user, 'supervisor_profile', None)
        if supervisor_profile:
            intern_recipient_profile = getattr(recipient, 'intern_profile', None)
            if intern_recipient_profile and intern_recipient_profile.supervisor == supervisor_profile:
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
            f"/supervisor/?chat={user.id}"
            if recipient.role == User.ROLE_SUPERVISOR
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
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor_profile = getattr(user, 'supervisor_profile', None)
        if supervisor_profile:
            target_intern_profile = getattr(target_user, 'intern_profile', None)
            if target_intern_profile and target_intern_profile.supervisor == supervisor_profile:
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

    # Get all notifications for current user first
    base_notifications = Notification.objects.filter(
        recipient=request.user
    )

    # Count unread BEFORE limiting results
    unread_count = base_notifications.filter(
        is_read=False
    ).count()

    # Only show latest 15 notifications
    notifications = base_notifications.order_by(
        '-created_at'
    )[:15]

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

            # Required so clicking a message notification can open chat
            'sender_id': n.sender.id if n.sender else None,
            'sender_name': (
                n.sender.get_full_name() or n.sender.username
                if n.sender
                else ''
            ),
        })
    return JsonResponse({
        'success': True,
        'unread_count': unread_count,
        'notifications': data
    })

@login_required
@require_POST
def mark_notification_read_api(request, notification_id):
    """Marks notification as read."""
    n = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    n.is_read = True
    n.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_task_status(request, task_id):
    """AJAX endpoint for interns to update task status in real time."""
    task = get_object_or_404(DailyTask, pk=task_id)

    intern_profile = getattr(request.user, 'intern_profile', None)
    supervisor_profile = getattr(request.user, 'supervisor_profile', None)

    allowed = False
    if intern_profile and task.topic.week.intern == intern_profile:
        allowed = True
    elif supervisor_profile and task.topic.week.intern.supervisor == supervisor_profile:
        allowed = True
    elif request.user.is_staff or request.user.role == User.ROLE_ADMIN:
        allowed = True

    if not allowed:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    new_status = request.POST.get('status')
    valid_statuses = [choice[0] for choice in DailyTask.STATUS_CHOICES]

    if new_status not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Invalid status value.'}, status=400)

    task.status = new_status
    task.save()

    if intern_profile and intern_profile.supervisor and intern_profile.supervisor.user:
        Notification.objects.create(
            recipient=intern_profile.supervisor.user,
            sender=request.user,
            title=f"Task Status Updated: {intern_profile.full_name}",
            message=f"Task '{task.title}' updated to '{task.get_status_display()}'.",
            link=f"/supervisor/?intern_id={intern_profile.id}",
            notification_type=Notification.TYPE_TASK
        )

    intern = task.topic.week.intern
    all_tasks = DailyTask.objects.filter(topic__week__intern=intern)
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status=DailyTask.STATUS_COMPLETED).count()
    in_progress_tasks = all_tasks.filter(status=DailyTask.STATUS_IN_PROGRESS).count()
    pending_tasks = all_tasks.filter(status=DailyTask.STATUS_PENDING).count()
    progress_pct = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0

    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'new_status': task.status,
        'status_display': task.get_status_display(),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'pending_tasks': pending_tasks,
        'progress_pct': progress_pct
    })


@login_required
def intern_detail_api(request, intern_id):
    """API returning detailed profile, schedule, and tasks for modal view."""
    intern = get_object_or_404(InternProfile, pk=intern_id)
    user = request.user

    if user.role == User.ROLE_SUPERVISOR:
        if intern.supervisor != getattr(user, 'supervisor_profile', None):
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    elif user.role == User.ROLE_INTERN:
        if intern.user != user:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    all_tasks = DailyTask.objects.filter(topic__week__intern=intern)
    total = all_tasks.count()
    completed = all_tasks.filter(status=DailyTask.STATUS_COMPLETED).count()
    pct = round((completed / total) * 100, 1) if total else 0

    weeks_data = []
    for week in intern.weeks.order_by('week_number').prefetch_related('topics__tasks__submissions'):
        topics_data = []
        for topic in week.topics.all():
            tasks_data = []
            for task in topic.tasks.all():
                submission = task.submissions.first()
                tasks_data.append({
                    'id': task.id,
                    'day_number': task.day_number,
                    'title': task.title,
                    'description': task.description or '',
                    'due_date': str(task.due_date) if task.due_date else '',
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'has_submission': submission is not None,
                    'submission_id': submission.id if submission else None,
                    'submission_status': submission.get_status_display() if submission else None,
                    'submission_text': submission.submission_text if submission else '',
                    'file_name': os.path.basename(submission.attached_file.name) if (submission and submission.attached_file) else '',
                    'feedback': submission.feedback if submission else ''
                })
            topics_data.append({
                'id': topic.id,
                'title': topic.title,
                'tasks': tasks_data
            })
        weeks_data.append({
            'id': week.id,
            'week_number': week.week_number,
            'department': week.department.name,
            'start_date': str(week.start_date),
            'end_date': str(week.end_date),
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
            'start_date': str(intern.start_date),
            'end_date': str(intern.end_date),
            'supervisor': intern.supervisor.user.get_full_name() if (intern.supervisor and intern.supervisor.user) else "Unassigned",
            'supervisor_user_id': intern.supervisor.user.id if (intern.supervisor and intern.supervisor.user) else None,
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