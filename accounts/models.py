import uuid
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user model. Login can be done via email, username, or intern ID.
    'role' drives which dashboard the user sees and what permissions they get.
    """
    ROLE_ADMIN = 'admin'
    ROLE_SUPERVISOR = 'supervisor'
    ROLE_INTERN = 'intern'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_SUPERVISOR, 'Supervisor'),
        (ROLE_INTERN, 'Intern'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # still required by AbstractUser

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class SupervisorProfile(models.Model):
    """
    One row per supervisor. Created by an admin AFTER
    a User with role='supervisor' exists.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='supervisor_profile'
    )
    department_focus = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class InternProfile(models.Model):
    """
    Created by an Admin/Supervisor BEFORE the intern has any login credentials.
    `user` stays null until the intern activates their account using their one-time token.
    """
    intern_id = models.CharField(max_length=20, unique=True, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='intern_profile',
        null=True, blank=True
    )

    full_name = models.CharField(max_length=150)
    university = models.CharField(max_length=200)
    degree = models.CharField(max_length=150, help_text="Degree / domain, e.g. BS Computer Science")
    start_date = models.DateField()
    end_date = models.DateField()
    supervisor = models.ForeignKey(
        SupervisorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='interns'
    )

    is_activated = models.BooleanField(default=False)
    activation_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    token_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.intern_id:
            self.intern_id = self._generate_intern_id()
        if not self.is_activated and not self.activation_token:
            self.activation_token = uuid.uuid4().hex
            self.token_created_at = timezone.now()
        super().save(*args, **kwargs)

    def _generate_intern_id(self):
        year = self.start_date.year if self.start_date else timezone.now().year
        prefix = f"INT-{year}-"
        last = (
            InternProfile.objects.filter(intern_id__startswith=prefix)
            .order_by('-intern_id')
            .first()
        )
        next_num = int(last.intern_id.split('-')[-1]) + 1 if last else 1
        return f"{prefix}{next_num:04d}"

    def generate_activation_token(self):
        self.activation_token = uuid.uuid4().hex
        self.token_created_at = timezone.now()
        self.save(update_fields=['activation_token', 'token_created_at'])
        return self.activation_token

    def is_token_valid(self, token):
        if self.is_activated or not self.activation_token:
            return False
        if self.activation_token != token:
            return False
        if not self.token_created_at:
            return True
        # Token expires after 48 hours
        return timezone.now() <= self.token_created_at + timedelta(hours=48)

    def __str__(self):
        return f"{self.full_name} ({self.intern_id})"

