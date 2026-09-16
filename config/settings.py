"""
Django settings for PivotMind.

Secrets are loaded from environment variables / a local .env file.
Never hardcode API keys in this file.
"""
import os
from pathlib import Path

from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["*"]
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
    "https://*.now.sh",
    "https://*.render.com",
    "https://*.onrender.com",
    "https://*.railway.app",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "agent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

try:
    import whitenoise  # noqa: F401
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
except ImportError:
    pass

MIDDLEWARE.extend([
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
                "agent.context_processors.navigation",
            ],
        },
    },
]

# Database configuration: support Vercel serverless writable /tmp filesystem fallback
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    tmp_db = Path("/tmp/db.sqlite3")
    if not tmp_db.exists() and (BASE_DIR / "db.sqlite3").exists():
        import shutil
        try:
            shutil.copyfile(BASE_DIR / "db.sqlite3", tmp_db)
        except Exception:
            pass
    db_name = tmp_db if tmp_db.parent.exists() else BASE_DIR / "db.sqlite3"
else:
    db_name = BASE_DIR / "db.sqlite3"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": db_name,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}

# --- PivotMind configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "").strip()
CURRENCY_API_KEY = os.getenv("CURRENCY_API_KEY", "").strip()

AGENT_MAX_TOOL_CALLS = int(os.getenv("AGENT_MAX_TOOL_CALLS", "8"))
AGENT_API_TIMEOUT = int(os.getenv("AGENT_API_TIMEOUT", "12"))
HISTORY_PAGE_SIZE = int(os.getenv("HISTORY_PAGE_SIZE", "8"))
