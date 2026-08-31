import datetime
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, SupervisorProfile, InternProfile
from academics.models import Department, InternshipWeek, Topic, DailyTask, TaskSubmission
from dashboard.models import Message, Notification


class Command(BaseCommand):
    help = "Seeds demo data for admin, supervisors, interns, departments, weeks, topics, tasks, messages, and notifications."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting demo data seeding..."))

        # 0. Create Admin User
        admin_user, created_admin = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "username": "admin",
                "first_name": "System",
                "last_name": "Administrator",
                "role": User.ROLE_ADMIN,
                "is_staff": True,
                "is_superuser": True
            }
        )
        if created_admin or not admin_user.check_password("admin123"):
            admin_user.set_password("admin123")
            admin_user.role = User.ROLE_ADMIN
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()

        # 1. Create Departments
        dept_erp, _ = Department.objects.get_or_create(
            name="ERP Systems & Oracle",
            defaults={"description": "Enterprise resource planning, Oracle financials, & workflow automation."}
        )
        dept_net, _ = Department.objects.get_or_create(
            name="Networking & Cloud",
            defaults={"description": "Cloud infrastructure, Linux systems, network architecture, and security."}
        )
        dept_db, _ = Department.objects.get_or_create(
            name="Database Administration",
            defaults={"description": "SQL optimization, PostgreSQL tuning, indexing, and backup management."}
        )

        # 2. Create Supervisor User & Profile
        sup_user, created_sup = User.objects.get_or_create(
            email="supervisor@example.com",
            defaults={
                "username": "supervisor",
                "first_name": "Sarah",
                "last_name": "Connor",
                "role": User.ROLE_SUPERVISOR,
                "is_staff": True
            }
        )
        if created_sup or not sup_user.check_password("password123"):
            sup_user.set_password("password123")
            sup_user.role = User.ROLE_SUPERVISOR
            sup_user.is_staff = True
            sup_user.save()

        sup_profile, _ = SupervisorProfile.objects.get_or_create(
            user=sup_user,
            defaults={"department_focus": "Engineering & Enterprise Systems"}
        )

        # 3. Create Demo Intern 1 (Activated)
        intern1_user, created_int1 = User.objects.get_or_create(
            email="alex.rivera@example.com",
            defaults={
                "username": "int-2026-0001",
                "first_name": "Alex",
                "last_name": "Rivera",
                "role": User.ROLE_INTERN
            }
        )
        if created_int1 or not intern1_user.check_password("password123"):
            intern1_user.set_password("password123")
            intern1_user.role = User.ROLE_INTERN
            intern1_user.save()

        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=14)
        end_date = start_date + datetime.timedelta(days=60)

        intern1_profile, _ = InternProfile.objects.get_or_create(
            intern_id="INT-2026-0001",
            defaults={
                "user": intern1_user,
                "full_name": "Alex Rivera",
                "university": "Stanford University",
                "degree": "BS Computer Science",
                "start_date": start_date,
                "end_date": end_date,
                "supervisor": sup_profile,
                "is_activated": True
            }
        )

        # 4. Create Demo Intern 2 (Activated)
        intern2_user, created_int2 = User.objects.get_or_create(
            email="maya.lin@example.com",
            defaults={
                "username": "int-2026-0002",
                "first_name": "Maya",
                "last_name": "Lin",
                "role": User.ROLE_INTERN
            }
        )
        if created_int2 or not intern2_user.check_password("password123"):
            intern2_user.set_password("password123")
            intern2_user.role = User.ROLE_INTERN
            intern2_user.save()

        intern2_profile, _ = InternProfile.objects.get_or_create(
            intern_id="INT-2026-0002",
            defaults={
                "user": intern2_user,
                "full_name": "Maya Lin",
                "university": "MIT",
                "degree": "MS Information Systems",
                "start_date": start_date,
                "end_date": end_date,
                "supervisor": sup_profile,
                "is_activated": True
            }
        )

        # 5. Create Pending Intern (Unactivated, testing activation token)
        pending_profile, _ = InternProfile.objects.get_or_create(
            intern_id="INT-2026-0003",
            defaults={
                "full_name": "David Kim",
                "university": "UC Berkeley",
                "degree": "BS Data Science",
                "start_date": today,
                "end_date": today + datetime.timedelta(days=60),
                "supervisor": sup_profile,
                "is_activated": False,
                "activation_token": "demo-token-12345",
                "token_created_at": timezone.now()
            }
        )

        # 6. Build Weeks and Tasks for Intern 1
        week1, _ = InternshipWeek.objects.get_or_create(
            intern=intern1_profile,
            week_number=1,
            defaults={
                "department": dept_erp,
                "start_date": start_date,
                "end_date": start_date + datetime.timedelta(days=6)
            }
        )

        t1, _ = Topic.objects.get_or_create(
            week=week1,
            title="ERP Fundamentals & Architecture",
            defaults={"order": 1}
        )

        task1, _ = DailyTask.objects.get_or_create(
            topic=t1, day_number=1,
            defaults={
                "title": "Orientation & System Environment Setup",
                "description": "Install developer tools, configure ERP sandbox instance, and verify connection credentials.",
                "due_date": start_date,
                "status": DailyTask.STATUS_COMPLETED
            }
        )
        task2, _ = DailyTask.objects.get_or_create(
            topic=t1, day_number=2,
            defaults={
                "title": "Database Schemas & Data Dictionary Review",
                "description": "Study core ERP tables (GL, AP, AR) and document key entity relationships.",
                "due_date": start_date + datetime.timedelta(days=1),
                "status": DailyTask.STATUS_COMPLETED
            }
        )
        task3, _ = DailyTask.objects.get_or_create(
            topic=t1, day_number=3,
            defaults={
                "title": "Workflow Scripting & Business Logic",
                "description": "Write PL/SQL procedures for automated order validation.",
                "due_date": start_date + datetime.timedelta(days=2),
                "status": DailyTask.STATUS_IN_PROGRESS
            }
        )

        # 7. Submissions for Intern 1
        TaskSubmission.objects.get_or_create(
            task=task1,
            intern=intern1_profile,
            defaults={
                "submission_text": "Environment setup verified. Sandbox credentials active.",
                "status": TaskSubmission.STATUS_REVIEWED,
                "feedback": "Great work setting up the sandbox environment promptly!"
            }
        )

        # 8. Messages & Notifications
        Message.objects.get_or_create(
            sender=intern1_user,
            recipient=sup_user,
            content="Hello Sarah! I have finished setting up my environment and started working on topic 1 scripting.",
            defaults={"task": task3}
        )
        Message.objects.get_or_create(
            sender=sup_user,
            recipient=intern1_user,
            content="Awesome Alex! Let me know if you run into any schema validation issues.",
            defaults={"task": task3}
        )

        Notification.objects.get_or_create(
            recipient=sup_user,
            sender=intern1_user,
            title="Work Submitted: Alex Rivera",
            defaults={
                "message": "Alex Rivera submitted work for Day 1: Orientation & System Environment Setup.",
                "notification_type": Notification.TYPE_SUBMISSION,
                "link": f"/supervisor/?intern_id={intern1_profile.id}"
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded demo data!"))
        self.stdout.write(self.style.WARNING("Demo Credentials:"))
        self.stdout.write(" - Admin: admin@example.com or 'admin' / admin123")
        self.stdout.write(" - Supervisor: supervisor@example.com / password123")
        self.stdout.write(" - Intern 1: alex.rivera@example.com or INT-2026-0001 / password123")
        self.stdout.write(" - Intern 2: maya.lin@example.com or INT-2026-0002 / password123")
        self.stdout.write(" - Pending Activation Token: demo-token-12345 (or ID: INT-2026-0003)")
