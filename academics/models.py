import os
from django.core.exceptions import ValidationError
from intern_portal.supabase_storage import SupabaseStorage
from django.db import models


def validate_submission_file(file):
    """
    Validates file extension and size for task submission security.
    """
    allowed_extensions = ['.pdf', '.docx', '.doc', '.zip', '.png', '.jpg', '.jpeg', '.txt', '.py', '.sql']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(allowed_extensions)}")
    
    max_size_mb = 10
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size exceeds the maximum limit of {max_size_mb} MB.")


class Department(models.Model):
    """A rotation department, e.g. ERP, Networking, Database. Reused across interns."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class TaskTemplate(models.Model):
    """Default daily task for a department's rotation — used to auto-generate each intern's schedule.
    Supervisors manage these via the admin to control what gets assigned per department."""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='task_templates')
    day_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['day_number']

    def __str__(self):
        return f"{self.department.name} · Day {self.day_number}: {self.title}"


class InternshipWeek(models.Model):
    """
    One week of one intern's schedule, assigned to a department.
    Supervisors create these to build the intern's rotation plan.
    """
    intern = models.ForeignKey(
        'accounts.InternProfile', on_delete=models.CASCADE, related_name='weeks'
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name='weeks'
    )
    week_number = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    course_outline_title = models.CharField(max_length=200,blank=True )
    course_outline_text = models.TextField(blank=True)
    course_outline_file = models.FileField(
        storage=SupabaseStorage(),
        upload_to='course_outlines/',
        blank=True,
        null=True
    )
        
    class Meta:
        unique_together = ('intern', 'week_number')
        ordering = ['week_number']

    def __str__(self):
        return f"Week {self.week_number} · {self.department.name} · {self.intern.intern_id}"


class Topic(models.Model):
    """A topic within a week, e.g. 'Oracle ERP'. Holds an ordered set of daily tasks."""
    week = models.ForeignKey(InternshipWeek, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class DailyTask(models.Model):
    """A single day's task/assignment under a topic."""
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='tasks')
    day_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ['day_number']

    def __str__(self):
        return f"Day {self.day_number}: {self.title}"


class TaskSubmission(models.Model):
    """Stores work submitted by an intern for a DailyTask."""
    STATUS_SUBMITTED = 'submitted'
    STATUS_REVIEWED = 'reviewed'
    STATUS_REVISION_REQUESTED = 'revision_requested'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_REVIEWED, 'Reviewed / Approved'),
        (STATUS_REVISION_REQUESTED, 'Revision Requested'),
    ]

    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE, related_name='submissions')
    intern = models.ForeignKey('accounts.InternProfile', on_delete=models.CASCADE, related_name='task_submissions')
    submission_text = models.TextField(blank=True)
    attached_file = models.FileField(
        upload_to='submissions/',
        validators=[validate_submission_file],
        blank=True, null=True
    )
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Submission by {self.intern.full_name} for Task {self.task_id}"

