from django.db import models
from django.utils import timezone
from accounts.models import InternProfile, CoordinatorProfile
from django.core.exceptions import ValidationError


def validate_submission_file(value):
    """
    Validator referenced by historical migrations.
    Enforces a maximum file upload size of 10 MB.
    """
    max_size = 10 * 1024 * 1024  # 10 MB
    if value.size > max_size:
        raise ValidationError('File size cannot exceed 10 MB.')


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    # Each department rotation has its own designated coordinator/contact.
    # Falls back to the intern's assigned supervisor when left unset.
    coordinator = models.ForeignKey(
        'accounts.CoordinatorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
        verbose_name='Department Coordinator',
        help_text="Coordinator responsible for interns rotating through this department."
    )

    def __str__(self):
        return self.name


class DepartmentAssignment(models.Model):
    intern = models.ForeignKey(InternProfile, on_delete=models.CASCADE, related_name='department_assignments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='assignments')
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.intern.user.get_full_name() if self.intern.user else self.intern.full_name} - {self.department.name}"

    @property
    def duration_in_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def duration_in_weeks(self):
        return round(self.duration_in_days / 7, 1)

    @property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

class InternshipWeek(models.Model):
    intern = models.ForeignKey(InternProfile, on_delete=models.CASCADE, related_name='schedule_weeks')
    week_number = models.IntegerField()
    
    # Added null=True to prevent department default prompts
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    
    # Foreign Key for Weekly Coordinator
    supervisor = models.ForeignKey(
        'accounts.CoordinatorProfile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        default=None,
        related_name='assigned_weeks'
    )
    
    start_date = models.DateField()
    end_date = models.DateField()
    course_outline_title = models.CharField(max_length=200, blank=True, null=True, default='')
    course_outline_text = models.TextField(blank=True, null=True, default='')
    course_outline_file = models.FileField(upload_to='outlines/', null=True, blank=True)

    class Meta:
        ordering = ['week_number']
        
    def __str__(self):
        dept_name = self.department.name if self.department else "General"
        return f"Week {self.week_number} - {dept_name}"

    @property
    def is_locked(self):
        return timezone.now().date() > self.end_date

    @property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def status(self):
        today = timezone.now().date()
        if today < self.start_date:
            return "Not Started"
        elif self.is_locked:
            return "Locked"
        else:
            return "In Progress"

    @property
    def effective_coordinator(self):
        if self.supervisor:
            return self.supervisor
        if self.department and self.department.coordinator:
            return self.department.coordinator
        if self.intern:
            return self.intern.supervisor
        return None


class Topic(models.Model):
    week = models.ForeignKey(InternshipWeek, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.week.title} - {self.title}"


class DailyTask(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('completed', 'Completed'),
    ]

    intern = models.ForeignKey(InternProfile, on_delete=models.CASCADE, related_name='daily_tasks')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='tasks')
    date = models.DateField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    attached_file = models.FileField(upload_to='task_submissions/', blank=True, null=True)
    attached_file_url = models.URLField(blank=True, null=True)
    
    # Set default=timezone.now to bypass terminal CLI prompts
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['date', 'created_at']

    def __str__(self):
        username = self.intern.user.username if self.intern.user else self.intern.full_name
        return f"{username} - {self.date} - {self.title}"


# --- Compatibility Alias for Legacy Imports ---
class TaskSubmission(DailyTask):
    """
    Proxy model ensuring dashboard/views.py and older modules importing TaskSubmission 
    continue working seamlessly without raising ImportError.
    """
    class Meta:
        proxy = True
        verbose_name = "Task Submission"
        verbose_name_plural = "Task Submissions"