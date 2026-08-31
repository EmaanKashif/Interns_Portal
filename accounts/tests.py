import datetime
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.utils import timezone
from accounts.models import User, SupervisorProfile, InternProfile
from academics.models import Department, InternshipWeek, Topic, DailyTask, TaskSubmission, validate_submission_file
from dashboard.models import Message, Notification


class SecurityAndFeatureTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Admin
        self.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role=User.ROLE_ADMIN
        )

        # Supervisor 1
        self.sup_user1 = User.objects.create_user(
            username='sup1',
            email='sup1@test.com',
            password='Password123!',
            role=User.ROLE_SUPERVISOR
        )
        self.sup_profile1 = SupervisorProfile.objects.create(user=self.sup_user1, department_focus='ERP')

        # Supervisor 2 (Unassigned to Intern 1)
        self.sup_user2 = User.objects.create_user(
            username='sup2',
            email='sup2@test.com',
            password='Password123!',
            role=User.ROLE_SUPERVISOR
        )
        self.sup_profile2 = SupervisorProfile.objects.create(user=self.sup_user2, department_focus='Networking')

        # Intern 1 (Assigned to Supervisor 1)
        self.intern_user1 = User.objects.create_user(
            username='int-2026-0001',
            email='intern1@test.com',
            password='Password123!',
            role=User.ROLE_INTERN
        )
        self.intern_profile1 = InternProfile.objects.create(
            user=self.intern_user1,
            full_name='Alex Rivera',
            university='Stanford',
            degree='CS',
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=60),
            supervisor=self.sup_profile1,
            is_activated=True
        )

        # Department & Task
        self.dept = Department.objects.create(name='ERP & Cloud')
        self.week = InternshipWeek.objects.create(
            intern=self.intern_profile1, department=self.dept, week_number=1,
            start_date=datetime.date.today(), end_date=datetime.date.today() + datetime.timedelta(days=6)
        )
        self.topic = Topic.objects.create(week=self.week, title='ERP Systems')
        self.task = DailyTask.objects.create(topic=self.topic, day_number=1, title='Setup Environment')

    def test_flex_authentication(self):
        """Verify login works via Email, Username, or Intern ID."""
        # Email login
        self.assertTrue(self.client.login(username='intern1@test.com', password='Password123!'))
        self.client.logout()

        # Intern ID login
        self.assertTrue(self.client.login(username='INT-2026-0001', password='Password123!'))
        self.client.logout()

        # Admin username login
        self.assertTrue(self.client.login(username='admin_test', password='Password123!'))
        self.client.logout()

    def test_token_activation(self):
        """Verify token generation, validation, and single-use invalidation."""
        pending_profile = InternProfile.objects.create(
            full_name='David Kim',
            university='Berkeley',
            degree='Data Science',
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=60),
            supervisor=self.sup_profile1,
            is_activated=False
        )
        token = pending_profile.generate_activation_token()
        self.assertTrue(pending_profile.is_token_valid(token))

        # Activate via endpoint
        response = self.client.post('/accounts/activate/', {
            'token_or_id': token,
            'email': 'david.kim@test.com',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        })
        self.assertEqual(response.status_code, 302)

        pending_profile.refresh_from_db()
        self.assertTrue(pending_profile.is_activated)
        self.assertFalse(pending_profile.is_token_valid(token))  # Token invalidated immediately

    def test_messaging_rbac_scoping(self):
        """Verify Intern can message ONLY assigned supervisor."""
        self.client.login(username='intern1@test.com', password='Password123!')

        # Message assigned supervisor (Allowed)
        res1 = self.client.post('/messages/send/', {
            'recipient_id': self.sup_user1.id,
            'content': 'Hello Supervisor 1'
        })
        self.assertEqual(res1.status_code, 200)

        # Message unassigned supervisor (Denied - 403)
        res2 = self.client.post('/messages/send/', {
            'recipient_id': self.sup_user2.id,
            'content': 'Hello Supervisor 2'
        })
        self.assertEqual(res2.status_code, 403)

    def test_file_submission_validation(self):
        """Verify file upload validation rejects disallowed extensions."""
        class DummyFile:
            name = 'malicious_script.exe'
            size = 1024

        with self.assertRaises(ValidationError):
            validate_submission_file(DummyFile())
