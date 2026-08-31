from django import forms
from django.contrib.auth.forms import AuthenticationForm


class FlexAuthenticationForm(AuthenticationForm):
    """
    Accepts Email address, Username, or Intern ID with password.
    Returns generic error messages to avoid account enumeration.
    """
    username = forms.CharField(
        label='Email address or Intern ID',
        widget=forms.TextInput(attrs={'placeholder': 'name@example.com or INT-2026-0001', 'class': 'form-control'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'class': 'form-control'})
    )

    error_messages = {
        'invalid_login': 'Invalid Email/Intern ID or password. Please try again.',
        'inactive': 'This account is inactive.',
    }


class TokenActivationForm(forms.Form):
    """
    Activation form requiring a valid, unexpired one-time activation token or Intern ID.
    """
    token_or_id = forms.CharField(
        label='Activation Token or Intern ID',
        max_length=64,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your Activation Token or Intern ID', 'class': 'form-control'})
    )
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'class': 'form-control'})
    )
    password = forms.CharField(
        label='Create Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'At least 8 characters', 'class': 'form-control'}),
        min_length=8
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Re-enter password', 'class': 'form-control'}),
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if pwd and confirm and pwd != confirm:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data

