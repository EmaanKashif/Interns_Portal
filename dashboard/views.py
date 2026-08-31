import datetime
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
    """
    Dedicated Admin Dashboard:
    Overview of system metrics, intern onboarding, supervisor management, and department focus areas.
    """
    total_interns = InternProfile.objects.count()
    activated_interns = InternProfile.objects.filter(is_activated=True).count()
    pending_activations = InternProfile.objects.filter(is_activated=False).count()
    total_supervisors = SupervisorProfile.objects.count()
    total_departments = Department.objects.count()

    interns = InternProfile.objects.select_related('supervisor__user', 'user').all()
    supervisors = SupervisorProfile.objects.select_related('user').all()
    departments = Department.objects.all()

    context = {
        'total_interns': total_interns,
        'activated_interns': activated_interns,
        'pending_activations': pending_activations,
        'total_supervisors': total_supervisors,
        'total_departments': total_departments,
        'interns': interns,
        'supervisors': supervisors,
        'departments': departments,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@role_required('intern')
def intern_dashboard(request):
    """Intern dashboard displaying current rotation week, tasks, submissions, and progress."""
    profile = get_object_or_404(InternProfile, user=request.user)

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

    # Unread notifications count
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
    """Supervisor dashboard managing assigned interns, task reviews, and message channels."""
    profile = get_object_or_404(SupervisorProfile, user=request.user)
    interns = profile.interns.select_related('user').all()

    intern_rows = []
    total_cohort_tasks = 0
    total_cohort_completed = 0

    for intern in interns:
        tasks = DailyTask.objects.filter(topic__week__intern=intern)
        total = tasks.count()
        completed = tasks.filter(status=DailyTask.STATUS_COMPLETED).count()
        in_progress = tasks.filter(status=DailyTask.STATUS_IN_PROGRESS).count()
        pct = round((completed / total) * 100, 1) if total else 0

        # Unread messages from this intern
        unread_msg = Message.objects.filter(sender=intern.user, recipient=request.user, is_read=False).count() if intern.user else 0

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

    context = {
        'profile': profile,
        'intern_rows': intern_rows,
        'total_interns': len(intern_rows),
        'cohort_pct': cohort_pct,
        'total_cohort_completed': total_cohort_completed,
        'total_cohort_tasks': total_cohort_tasks,
        'departments': departments,
        'supervisors': supervisors,
    }
    return render(request, 'dashboard/supervisor_dashboard.html', context)


@login_required
@require_POST
def issue_intern_id_api(request):
    """
    API endpoint allowing Admins or Supervisors to issue a new Intern ID & activation token.
    Auto-generates Intern Profile, Intern ID (e.g. INT-2026-0004), random UUID4 token,
    and sets up initial rotation curriculum weeks and daily tasks.
    """
    user = request.user
    if user.role not in [User.ROLE_ADMIN, User.ROLE_SUPERVISOR] and not user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    full_name = request.POST.get('full_name', '').strip()
    university = request.POST.get('university', '').strip()
    degree = request.POST.get('degree', '').strip()
    department_id = request.POST.get('department_id')
    supervisor_id = request.POST.get('supervisor_id')
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')

    if not full_name or not university or not degree:
        return JsonResponse({'success': False, 'error': 'Full name, university, and degree domain are required.'}, status=400)

    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.date.today()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date + datetime.timedelta(days=60)
    except ValueError:
        start_date = datetime.date.today()
        end_date = start_date + datetime.timedelta(days=60)

    supervisor = None
    if supervisor_id:
        supervisor = SupervisorProfile.objects.filter(pk=supervisor_id).first()
    elif user.role == User.ROLE_SUPERVISOR:
        supervisor = getattr(user, 'supervisor_profile', None)

    department = Department.objects.filter(pk=department_id).first() if department_id else Department.objects.first()

    # Create Intern Profile (auto-generates intern_id and activation_token)
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

    # Build initial curriculum week & sample daily tasks if department exists
    if department:
        week1 = InternshipWeek.objects.create(
            intern=profile,
            department=department,
            week_number=1,
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=6)
        )

        t1 = Topic.objects.create(week=week1, title=f"Orientation & {department.name} Setup", order=1)
        DailyTask.objects.create(
            topic=t1, day_number=1,
            title="System Access & Environment Setup",
            description="Access your workspace tools and review initial department guidelines.",
            due_date=start_date,
            status=DailyTask.STATUS_PENDING
        )
        DailyTask.objects.create(
            topic=t1, day_number=2,
            title="Core Concepts & Architecture Review",
            description="Study the foundational architecture documentation.",
            due_date=start_date + datetime.timedelta(days=1),
            status=DailyTask.STATUS_PENDING
        )

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
def create_supervisor_api(request):
    """API endpoint allowing Admins to create a new Supervisor user & profile."""
    if request.user.role != User.ROLE_ADMIN and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '').strip()
    department_focus = request.POST.get('department_focus', '').strip()

    if not email or not password or not first_name:
        return JsonResponse({'success': False, 'error': 'First name, email, and password are required.'}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({'success': False, 'error': 'User with this email already exists.'}, status=400)

    username = email.split('@')[0]
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=User.ROLE_SUPERVISOR,
        is_staff=True
    )

    SupervisorProfile.objects.create(
        user=user,
        department_focus=department_focus or "Enterprise Operations"
    )

    return JsonResponse({
        'success': True,
        'message': f"Supervisor account created for {user.get_full_name()} ({user.email})."
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
    """
    API for Interns to message their assigned Supervisor, or Supervisor to message their assigned Intern.
    Enforces strict backend RBAC messaging boundaries.
    """
    user = request.user
    recipient_id = request.POST.get('recipient_id')
    content = request.POST.get('content', '').strip()
    task_id = request.POST.get('task_id')

    if not recipient_id or not content:
        return JsonResponse({'success': False, 'error': 'Recipient and message content are required.'}, status=400)

    recipient = get_object_or_404(User, pk=recipient_id)

    # Scoped access control check
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
        return JsonResponse({'success': False, 'error': 'Permission denied. You can only communicate with your assigned supervisor/intern.'}, status=403)

    task = DailyTask.objects.filter(pk=task_id).first() if task_id else None

    msg = Message.objects.create(
        sender=user,
        recipient=recipient,
        content=content,
        task=task
    )

    # Generate Notification
    Notification.objects.create(
        recipient=recipient,
        sender=user,
        title=f"New Message from {user.get_full_name() or user.username}",
        message=content[:100] + ('...' if len(content) > 100 else ''),
        link="/intern/" if recipient.role == User.ROLE_INTERN else "/supervisor/",
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
    """
    API returning conversation history between logged-in user and target user.
    Backend RBAC enforced. Marks incoming messages as read.
    """
    target_user_id = request.GET.get('target_user_id')
    if not target_user_id:
        return JsonResponse({'success': False, 'error': 'Target user required.'}, status=400)

    target_user = get_object_or_404(User, pk=target_user_id)
    user = request.user

    # Permission check
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

    # Mark incoming as read
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
    """API returning notifications for the logged-in user."""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:15]
    unread_count = notifications.filter(is_read=False).count()

    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'link': n.link or '#',
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d, %H:%M')
        })

    return JsonResponse({
        'success': True,
        'unread_count': unread_count,
        'notifications': data
    })


@login_required
@require_POST
def mark_notification_read_api(request, notification_id):
    """Marks a notification as read."""
    n = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    n.is_read = True
    n.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def update_task_status(request, task_id):
    """AJAX endpoint allowing interns to update task status in real time."""
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

    # If updated by Intern, notify Supervisor
    if intern_profile and intern_profile.supervisor and intern_profile.supervisor.user:
        Notification.objects.create(
            recipient=intern_profile.supervisor.user,
            sender=request.user,
            title=f"Task Status Updated: {intern_profile.full_name}",
            message=f"Task '{task.title}' updated to '{task.get_status_display()}'.",
            link=f"/supervisor/?intern_id={intern_profile.id}",
            notification_type=Notification.TYPE_TASK
        )

    # Recalculate intern stats
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
