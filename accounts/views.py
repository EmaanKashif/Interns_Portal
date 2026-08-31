from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import FlexAuthenticationForm, TokenActivationForm
from .models import InternProfile, User


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = FlexAuthenticationForm


def activate_account(request):
    """
    Public account activation view.
    Validates a one-time activation token (or issued Intern ID) with 48-hour expiration.
    Once used, the token is invalidated and the account is activated.
    """
    token_param = request.GET.get('token', '').strip()
    id_param = request.GET.get('intern_id', '').strip()

    initial_data = {}
    if token_param:
        initial_data['token_or_id'] = token_param
    elif id_param:
        initial_data['token_or_id'] = id_param

    if request.method == 'POST':
        form = TokenActivationForm(request.POST)
        if form.is_valid():
            token_or_id = form.cleaned_data['token_or_id'].strip()
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            # Lookup by activation_token OR intern_id
            profile = (
                InternProfile.objects.filter(
                    Q(activation_token=token_or_id) | Q(intern_id__iexact=token_or_id),
                    is_activated=False
                ).first()
            )

            if not profile:
                form.add_error('token_or_id', 'Invalid or already activated token/ID.')
            elif profile.activation_token and not profile.is_token_valid(profile.activation_token):
                form.add_error('token_or_id', 'This activation token has expired (valid for 48 hours). Please request a new activation link from your administrator.')
            elif User.objects.filter(email__iexact=email).exists():
                form.add_error('email', 'This email address is already in use.')
            else:
                username = profile.intern_id.lower()
                name_parts = profile.full_name.split(' ')
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=User.ROLE_INTERN,
                    first_name=first_name,
                    last_name=last_name,
                )
                profile.user = user
                profile.is_activated = True
                profile.activation_token = None  # Invalidate token immediately
                profile.save()

                login(request, user, backend='accounts.backends.FlexAuthBackend')
                return redirect('dashboard:router')

    else:
        form = TokenActivationForm(initial=initial_data)

    return render(request, 'accounts/activate.html', {
        'form': form,
        'token_param': token_param or id_param
    })

