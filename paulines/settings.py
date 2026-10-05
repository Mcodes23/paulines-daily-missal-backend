"""
Django settings for Paulines Daily Missal project.
Clean, modern, and production-ready configuration.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# ───────────────────────────────────────────────
# Base Paths & Environment
# ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ───────────────────────────────────────────────
# Core Settings
# ───────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1", "dashboard.tymirahealth.com"]

# Allow all in dev (optional)
if DEBUG:
    ALLOWED_HOSTS.append("*")

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://dashboard.tymirahealth.com",
]

# ───────────────────────────────────────────────
# Installed Apps
# ───────────────────────────────────────────────
INSTALLED_APPS = [
    # Theme & UI Enhancements
    "jazzmin",              # modern admin theme
    "nested_admin",         # hierarchical inlines
   # "tabbed_admin",         # tabbed admin forms
    "django_ckeditor_5",    # CKEditor 5 (secure modern editor)
    "rest_framework",

    # Django Core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project Apps
    "accounts.apps.AccountsConfig",
    "missal.apps.MissalConfig",
]

# ───────────────────────────────────────────────
# JWT Configuration
# ───────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30

# ───────────────────────────────────────────────
# Middleware
# ───────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ───────────────────────────────────────────────
# URLs & WSGI
# ───────────────────────────────────────────────
ROOT_URLCONF = "paulines.urls"
WSGI_APPLICATION = "paulines.wsgi.application"

# ───────────────────────────────────────────────
# Templates
# ───────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ───────────────────────────────────────────────
# Database: PostgreSQL
# ───────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "paulines_daily_missal_dev"),
        "USER": os.getenv("DB_USER", "paulines_dba"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": True,
        "OPTIONS": {"sslmode": "prefer"},
        "TEST": {"NAME": os.getenv("DB_TEST_NAME", "paulines_daily_missal_test")},
    }
}

# ───────────────────────────────────────────────
# Authentication & Localization
# ───────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ───────────────────────────────────────────────
# Static & Media
# ───────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/login/'


# ───────────────────────────────────────────────
# Jazzmin Admin Configuration
# ───────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title": "Paulines Missal Admin",
    "site_header": "Paulines Daily Missal",
    "welcome_sign": "Liturgical Day Management",
    "search_model": "missal.LiturgicalDay",
    "show_sidebar": True,
    "related_modal_active": True,
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index"},
    ],
    "icons": {
        "missal.LiturgicalDay": "fas fa-cross",
        "missal.Reading": "fas fa-book-open",
        "missal.SpecialSections": "fas fa-praying-hands",
    },
}

JAZZMIN_SETTINGS["custom_js"] = ["admin/js/fix_popup_host.js"]


# ───────────────────────────────────────────────
# CKEditor 5 Configuration
# ───────────────────────────────────────────────
CKEDITOR_5_UPLOAD_PATH = "uploads/"
CKEDITOR_5_CUSTOM_CSS = "admin/css/missal.css"   # optional custom stylesheet
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading", "|",
            "bold", "italic", "underline", "link", "|",
            "bulletedList", "numberedList", "|",
            "blockQuote", "insertTable", "|",
            "undo", "redo"
        ],
        "height": 400,
        "width": "100%",
    },
}
