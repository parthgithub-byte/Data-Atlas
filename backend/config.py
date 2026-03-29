import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default="false"):
    return os.getenv(name, default).strip().lower() == "true"


def _env_list(name, default=""):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    """Application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "osint-footprint-secret-key-change-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-super-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_CHECK_FORM = False
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"
    JWT_COOKIE_SECURE = _env_bool("JWT_COOKIE_SECURE")
    JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "Strict")
    SESSION_COOKIE_SECURE = JWT_COOKIE_SECURE
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = JWT_COOKIE_SAMESITE

    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'footprint.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Browser access control
    CORS_ORIGINS = _env_list(
        "CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000",
    )

    # SearxNG
    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888/search")
    SEARXNG_ENABLED = os.getenv("SEARXNG_ENABLED", "false").lower() == "true"
    SEARXNG_TIME_RANGE = os.getenv("SEARXNG_TIME_RANGE", "month")

    # Task queue / workers
    TASK_QUEUE_ENABLED = os.getenv("TASK_QUEUE_ENABLED", "false").lower() == "true"
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    SCAN_QUEUE_NAME = os.getenv("SCAN_QUEUE_NAME", "scan-jobs")

    # DigiLocker OAuth2
    DIGILOCKER_CLIENT_ID = os.getenv("DIGILOCKER_CLIENT_ID", "")
    DIGILOCKER_CLIENT_SECRET = os.getenv("DIGILOCKER_CLIENT_SECRET", "")
    DIGILOCKER_REDIRECT_URI = os.getenv(
        "DIGILOCKER_REDIRECT_URI",
        "http://localhost:5000/api/auth/digilocker/callback",
    )
    DIGILOCKER_AUTH_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/authorize"
    DIGILOCKER_TOKEN_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/token"
    DIGILOCKER_USERINFO_URL = "https://digilocker.meripehchaan.gov.in/public/oauth2/1/user"

    # Google OAuth2 / OpenID Connect
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/api/auth/google/callback",
    )
    GOOGLE_DISCOVERY_URL = os.getenv(
        "GOOGLE_DISCOVERY_URL",
        "https://accounts.google.com/.well-known/openid-configuration",
    )

    # Authentication hardening
    AUTH_LOCKOUT_THRESHOLD = int(os.getenv("AUTH_LOCKOUT_THRESHOLD", "5"))
    AUTH_LOCKOUT_MINUTES = int(os.getenv("AUTH_LOCKOUT_MINUTES", "15"))
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "10"))
    SELF_SCAN_ONLY = _env_bool("SELF_SCAN_ONLY", "true")

    # Scan limits
    MAX_QUICK_SCAN_SITES = 100
    MAX_FULL_SCAN_URLS = 20
    REQUEST_TIMEOUT = 10
    REQUEST_JITTER_MIN = 0.1
    REQUEST_JITTER_MAX = 0.5
