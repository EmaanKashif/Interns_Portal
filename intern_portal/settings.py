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
# DATABASE SETUP - TRANSACTION POOLER FOR VERCEL
# ============================================================

import dj_database_url
from urllib.parse import urlparse

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

def get_database_config():
    """Get database configuration using Transaction pooler for Vercel"""
    
    # If no DATABASE_URL, use SQLite
    if not DATABASE_URL:
        print("⚠️ No DATABASE_URL found, using SQLite", file=sys.stderr)
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
    
    try:
        # Parse the URL
        parsed = urlparse(DATABASE_URL)
        is_supabase = 'supabase.co' in parsed.hostname if parsed.hostname else False
        
        # Check if using correct port for transaction pooler
        if is_supabase:
            if parsed.port == 5432:
                print("❌ ERROR: Using direct connection (port 5432).", file=sys.stderr)
                print("❌ For Vercel serverless functions, you MUST use the Transaction pooler (port 6543).", file=sys.stderr)
                print("❌ Please update your DATABASE_URL in Vercel environment variables.", file=sys.stderr)
                # Fallback to SQLite
                return {
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': BASE_DIR / 'db.sqlite3',
                    }
                }
            elif parsed.port == 6543:
                print("✅ Using Transaction pooler (port 6543) - Correct for Vercel!", file=sys.stderr)
            else:
                print(f"⚠️ Using port {parsed.port}. For Vercel, use port 6543.", file=sys.stderr)
        
        # Parse the database URL
        config = dj_database_url.parse(DATABASE_URL)
        
        # Vercel-specific optimizations for serverless
        db_options = {
            'sslmode': 'require',
            'connect_timeout': 30,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        }
        
        # CRITICAL: Disable connection pooling for serverless
        config['CONN_MAX_AGE'] = 0
        config['OPTIONS'] = db_options
        
        print(f"✅ Database configured: {config['ENGINE']}", file=sys.stderr)
        if is_supabase:
            print(f"✅ Supabase Transaction pooler: {config['HOST']}:{config['PORT']}", file=sys.stderr)
        
        return {'default': config}
        
    except Exception as e:
        print(f"⚠️ Error parsing DATABASE_URL: {e}", file=sys.stderr)
        print(f"⚠️ Falling back to SQLite", file=sys.stderr)
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

DATABASES = get_database_config()

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
# STATIC FILES
# ============================================================

STATIC_URL = '/static/'

# Ensure the directory exists
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT.mkdir(exist_ok=True)

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT.mkdir(exist_ok=True)

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

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True