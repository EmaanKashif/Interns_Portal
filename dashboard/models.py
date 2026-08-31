from django.db import models
from accounts.models import User


class Message(models.Model):
    """
    Direct message between Intern and Supervisor.
    Interns can message ONLY their assigned supervisor;
    Supervisors can message ONLY their assigned interns.
    """
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    task = models.ForeignKey('academics.DailyTask', on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"From {self.sender.get_full_name() or self.sender.username} to {self.recipient.get_full_name() or self.recipient.username} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Notification(models.Model):
    """
    System notification generated on messages, task status changes, submissions, and reviews.
    """
    TYPE_MESSAGE = 'message'
    TYPE_TASK = 'task'
    TYPE_SUBMISSION = 'submission'
    TYPE_SYSTEM = 'system'

    TYPE_CHOICES = [
        (TYPE_MESSAGE, 'New Message'),
        (TYPE_TASK, 'Task Update'),
        (TYPE_SUBMISSION, 'Work Submission'),
        (TYPE_SYSTEM, 'System Alert'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='triggered_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
