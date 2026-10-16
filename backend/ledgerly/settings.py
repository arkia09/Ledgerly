"""Ledgerly backend settings. Local-only app: no login, no cloud, SQLite."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # backend/
PROJECT_ROOT = BASE_DIR.parent                         # repo root

SECRET_KEY = os.environ.get("LEDGERLY_SECRET_KEY", "local-dev-only-not-a-secret")
DEBUG = os.environ.get("LEDGERLY_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ledgerly.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ledgerly.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The React dev server (Vite). 127.0.0.1 is included because Vite sometimes binds to it.
CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# ---- Ledgerly settings ----
# Folder holding extract.py / schema.py / prompt.txt (flat imports, so it goes on sys.path).
LEDGERLY_EXTRACTION_DIR = PROJECT_ROOT / "extraction"
# Saved model output used when LEDGERLY_FAKE_EXTRACT=1.
LEDGERLY_FAKE_OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "v3"
# Used only by `manage.py load_demo`.
LEDGERLY_GROUND_TRUTH_DIR = PROJECT_ROOT / "data" / "ground_truth"
LEDGERLY_PAGE_IMAGES_DIR = PROJECT_ROOT / "data" / "pages"
# Minimum rapidfuzz ratio (0-100) for suggesting an existing customer.
LEDGERLY_MATCH_THRESHOLD = int(os.environ.get("LEDGERLY_MATCH_THRESHOLD", "85"))
