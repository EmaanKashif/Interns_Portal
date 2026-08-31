from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User


class FlexAuthBackend(ModelBackend):
    """
    Custom authentication backend allowing users to log in with:
    - Email address (case-insensitive)
    - Username (case-insensitive)
    - Intern ID e.g. INT-2026-0001 (case-insensitive)
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        username_clean = username.strip()

        try:
            user = User.objects.filter(
                Q(email__iexact=username_clean) |
                Q(username__iexact=username_clean) |
                Q(intern_profile__intern_id__iexact=username_clean)
            ).distinct().first()
        except Exception:
            return None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
