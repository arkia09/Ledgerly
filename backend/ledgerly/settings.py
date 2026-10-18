"""Ledgerly backend settings. Local by default (SQLite, DEBUG on). On Render the env vars below switch it to Postgres + production mode."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # backend/
PROJECT_ROOT = BASE_DIR.parent                         # repo root

SECRET_KEY = os.environ.get("LEDGERLY_SECRET_KEY", "local-dev-only-not-a-secret")
DEBUG = os.environ.get("LEDGERLY_DEBUG", "1") == "1"
if not DEBUG and SECRET_KEY == "local-dev-only-not-a-secret":
    raise RuntimeError("Set LEDGERLY_SECRET_KEY when LEDGERLY_DEBUG=0.")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):          # set automatically by Render
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

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

if not DEBUG:  # production only, so local development needs no extra package
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

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
if os.environ.get("DATABASE_URL"):                       # Render: Postgres
    import dj_database_url
    DATABASES["default"] = dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("LEDGERLY_MEDIA_ROOT", BASE_DIR / "media"))   # Render: persistent disk
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The React dev server (Vite). 127.0.0.1 is included because Vite sometimes binds to it.
CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
# Hosted frontend address(es), comma separated, e.g. https://ledgerly-web.onrender.com (no trailing slash).
CORS_ALLOWED_ORIGINS += [o.strip().rstrip("/") for o in os.environ.get("LEDGERLY_CORS_ORIGINS", "").split(",") if o.strip()]

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
