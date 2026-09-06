import uuid
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_COORDINATOR = 'supervisor'  # Database value remains 'supervisor' to protect existing foreign keys
    ROLE_INTERN = 'intern'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_COORDINATOR, 'Coordinator'),
        (ROLE_INTERN, 'Intern'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class CoordinatorProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='supervisor_profile'
    )
    department_focus = models.CharField(max_length=100, blank=True)

    # Coordinator account activation
    is_activated = models.BooleanField(default=False)

    activation_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True
    )

    token_created_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Coordinator Profile'
        verbose_name_plural = 'Coordinator Profiles'

    def generate_activation_token(self):
        self.activation_token = uuid.uuid4().hex
        self.token_created_at = timezone.now()
        self.save(
            update_fields=[
                'activation_token',
                'token_created_at'
            ]
        )
        return self.activation_token

    def is_token_valid(self, token):
        if self.is_activated or not self.activation_token:
            return False

        if self.activation_token != token:
            return False

        if not self.token_created_at:
            return True

        return timezone.now() <= (
            self.token_created_at + timedelta(hours=48)
        )

    def __str__(self):
        return f"Coordinator: {self.user.get_full_name() or self.user.username}"


# Backward-compatibility alias
SupervisorProfile = CoordinatorProfile


class InternProfile(models.Model):
    intern_id = models.CharField(max_length=20, unique=True, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='intern_profile',
        null=True, blank=True
    )

    full_name = models.CharField(max_length=150)
    university = models.CharField(max_length=200)
    degree = models.CharField(max_length=150, help_text="Degree / domain, e.g. BS Computer Science")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Underlying DB column 'supervisor_id' maintained to avoid SQLite column missing errors
    supervisor = models.ForeignKey(
        CoordinatorProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='interns', verbose_name='Coordinator'
    )

    # Property alias for coordinator access in Python views & templates
    @property
    def coordinator(self):
        return self.supervisor

    @coordinator.setter
    def coordinator(self, value):
        self.supervisor = value

    # Support for manual entry
    custom_supervisor_name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Custom Coordinator Name"
    )

    is_activated = models.BooleanField(default=False)
    is_active = models.BooleanField(
        default=True, 
        help_text="Unchecked = removed by coordinator; hides intern without deleting their history."
    )
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
            .exclude(intern_id='')
            .order_by('-intern_id')
            .first()
        )
        if last and last.intern_id:
            try:
                next_num = int(last.intern_id.split('-')[-1]) + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
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
        return timezone.now() <= self.token_created_at + timedelta(hours=48)

    def __str__(self):
        return f"{self.full_name} ({self.intern_id})"
    
    # =========================================================
    # Dynamic Intern Progress & Coordinator Tracking Properties
    # =========================================================

    @property
    def total_weeks(self):
        """Calculates total internship duration in weeks."""
        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days + 1
            return max(1, round(days / 7))
        return 0

    @property
    def current_week_object(self):
        """Fetches the InternshipWeek entry matching today's date."""
        today = timezone.now().date()
        return self.schedule_weeks.filter(start_date__lte=today, end_date__gte=today).first()

    @property
    def current_week_display(self):
        """Returns string status e.g., 'Week 3 of 6', 'Not Started', or 'Completed'."""
        today = timezone.now().date()
        
        if self.start_date and today < self.start_date:
            return "Not Started"
        if self.end_date and today > self.end_date:
            return "Completed"

        curr_wk = self.current_week_object
        if curr_wk:
            return f"Week {curr_wk.week_number} of {self.total_weeks}"

        # Fallback calculation if schedule entry is not explicitly generated
        if self.start_date:
            days_passed = (today - self.start_date).days
            wk_num = (days_passed // 7) + 1
            return f"Week {wk_num} of {self.total_weeks}"

        return "N/A"

    @property
    def days_remaining(self):
        """Calculates exact days left until internship end_date."""
        today = timezone.now().date()
        if not self.end_date or today > self.end_date:
            return 0
        return (self.end_date - today).days

    @property
    def active_coordinator(self):
        """
        Dynamically gets current week's coordinator name cleanly.
        """
        curr_wk = self.current_week_object
        coord_obj = None

        if curr_wk and curr_wk.effective_coordinator:
            coord_obj = curr_wk.effective_coordinator
        elif self.supervisor:
            coord_obj = self.supervisor
        elif self.custom_supervisor_name:
            # Strip out any 'Coordinator:' prefix if manually entered previously
            clean_name = str(self.custom_supervisor_name).replace("Coordinator:", "").strip()
            return clean_name or "Unassigned"

        if coord_obj:
            # Extract clean string representation
            if hasattr(coord_obj, 'user') and coord_obj.user:
                name = coord_obj.user.get_full_name() or coord_obj.user.username
            else:
                name = str(coord_obj)
            
            # Clean up redundant prefixes
            return name.replace("Coordinator:", "").strip()

        return "Unassigned"