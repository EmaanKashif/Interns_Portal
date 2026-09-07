"""
Django settings for intern_portal project.
"""

import os
import sys
from pathlib import Path

# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# LOAD .ENV LOCALLY IF AVAILABLE
# ============================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-local-development-key'
)

DEBUG = os.environ.get(
    'DEBUG',
    'False'
).lower() in ('true', '1', 't')

# ============================================================
# HOSTS
# ============================================================

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')

ALLOWED_HOSTS = (
    [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
    if allowed_hosts_env
    else ['127.0.0.1', 'localhost', '.vercel.app', '.onrender.com']
)

# ============================================================
# CSRF
# ============================================================

csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')

if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in csrf_origins_env.split(',')
        if origin.strip()
    ]
else:
    CSRF_TRUSTED_ORIGINS = [
        'https://*.vercel.app',
        'https://*.onrender.com',
    ]

# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',

    # Local apps
    'accounts',
    'academics',
    'dashboard',
]

AUTH_USER_MODEL = 'accounts.User'

# ============================================================
# AUTHENTICATION
# ============================================================

AUTHENTICATION_BACKENDS = [
    'accounts.backends.FlexAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URL / TEMPLATES / WSGI
# ============================================================

ROOT_URLCONF = 'intern_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'intern_portal.wsgi.application'
# ============================================================
# DATABASE SETUP - PRODUCTION SAFE
# ============================================================

import dj_database_url

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,  # Required for serverless / pgBouncer connection pooling
            ssl_require=False
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC FILES (READ-ONLY SAFE)
# ============================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================
# MEDIA & STORAGE (VERCEL / SUPABASE SAFE)
# ============================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Use Supabase storage in production on Vercel
if os.environ.get('VERCEL') or not DEBUG:
    DEFAULT_FILE_STORAGE = 'intern_portal.supabase_storage.SupabaseStorage'


# ============================================================
# SUPABASE STORAGE
# ============================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SECRET_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'course-outline')

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("⚠️ Warning: Supabase storage not configured", file=sys.stderr)

# ============================================================
# LOGIN / LOGOUT
# ============================================================

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:router'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ============================================================
# DEFAULT MODEL FIELD
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ============================================================
# PRODUCTION SECURITY
# ============================================================

# ============================================================
# PRODUCTION SECURITY
# ============================================================

if not DEBUG and os.environ.get('VERCEL'):
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    # Disable SSL enforcement for local development
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False