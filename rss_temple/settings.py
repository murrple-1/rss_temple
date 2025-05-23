import datetime
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "APP_SECRET_KEY",
    "PLEASE_OVERRIDE_ME",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("APP_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = ["*"]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.google",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "corsheaders",
    "django_apscheduler",
    "silk",
    "api.apps.ApiConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "silk.middleware.SilkyMiddleware",
]

ROOT_URLCONF = "rss_temple.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
        "APP_DIRS": True,
        "DIRS": ["api/templates/"],
    },
]

WSGI_APPLICATION = "rss_temple.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

REDIS_URL = os.getenv("APP_REDIS_URL", "redis://valkey:6379")

if os.getenv("APP_IN_DOCKER", "false").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("APP_DB_NAME", "postgres"),
            "USER": os.getenv("APP_DB_USER", "postgres"),
            "PASSWORD": os.getenv("APP_DB_PASSWORD", "password"),
            "HOST": os.getenv("APP_DB_HOST", "postgresql"),
            "PORT": int(os.getenv("APP_DB_PORT", "5432")),
        }
    }

    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"
else:
    # Basically used in CI test phase or when running tests locally.
    # We don't load redis for that, so avoid setting the cache.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }

SESSION_COOKIE_SECURE = os.getenv("APP_SESSION_COOKIE_SECURE", "true") == "true"
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_DOMAIN = os.getenv("APP_SESSION_COOKIE_DOMAIN", "localhost")
SESSION_SAVE_EVERY_REQUEST = True


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 6,
        },
    },
    {
        "NAME": "api.password_validation.HasLowercaseValidator",
    },
    {
        "NAME": "api.password_validation.HasUppercaseValidator",
    },
    {
        "NAME": "api.password_validation.HasDigitValidator",
    },
    {
        "NAME": "api.password_validation.HasSpecialCharacterValidator",
    },
    {
        "NAME": "api.password_validation.ElevatedCommonPasswordValidator",
    },
    {
        "NAME": "api.password_validation.ElevatedUserAttributeSimilarityValidator",
    },
]

AUTH_USER_MODEL = "api.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = os.getenv("TZ", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "_static")

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "app_console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        }
    },
    "loggers": {
        "django": {
            "level": os.getenv("APP_DJANGO_LOG_LEVEL", "INFO"),
        },
        "django.db.backends": {
            "level": os.getenv("APP_DJANGO_DB_BACKEND_LOG_LEVEL", "INFO"),
        },
        "query_utils": {
            "handlers": ["app_console"],
            "level": os.getenv("APP_LOG_LEVEL", "INFO"),
        },
        "rss_temple": {
            "handlers": ["app_console"],
            "level": os.getenv("APP_LOG_LEVEL", "INFO"),
        },
        "rss_temple.feed_handler": {
            "level": os.getenv("APP_FEED_LOG_LEVEL", "ERROR"),
            "propagate": False,
        },
    },
}

if os.getenv("APP_IN_DOCKER", "false").lower() == "true":
    CACHES = {
        "default": {
            "BACKEND": "redis_lock.django_cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/1",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 5,  # 5 minutes
        },
        "stable_query": {
            "BACKEND": "redis_lock.django_cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/2",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 60,  # 1 hour
        },
        "captcha": {
            "BACKEND": "redis_lock.django_cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/3",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 5,  # 5 minutes
        },
        "throttle": {
            "BACKEND": "redis_lock.django_cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/4",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "default-cache",
            "TIMEOUT": 60 * 5,  # 5 minutes
        },
        "stable_query": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "stable-query-cache",
            "TIMEOUT": 60 * 60,  # 1 hour
        },
        "captcha": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "captcha-cache",
            "TIMEOUT": 60 * 5,  # 5 minutes
        },
        "throttle": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-cache",
        },
    }

CSRF_TRUSTED_ORIGINS = (
    csrf_trusted_origins.split(",")
    if (csrf_trusted_origins := os.getenv("APP_CSRF_TRUSTED_ORIGINS"))
    else ["http://localhost:4200"]
)
CSRF_COOKIE_SECURE = os.getenv("APP_CSRF_COOKIE_SECURE", "true") == "true"
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_DOMAIN = os.getenv("APP_CSRF_COOKIE_DOMAIN", "localhost")

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("APP_EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("APP_EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("APP_EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("APP_EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = os.getenv("APP_EMAIL_USE_TLS", "false").lower() == "true"
    EMAIL_USE_SSL = os.getenv("APP_EMAIL_USE_SSL", "false").lower() == "true"
    EMAIL_TIMEOUT = (
        None if (timeout := os.getenv("APP_EMAIL_TIMEOUT")) is None else float(timeout)
    )

DEFAULT_FROM_EMAIL = os.getenv("APP_DEFAULT_FROM_EMAIL", "webmaster@localhost")

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.authentication.ExpiringTokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("drf_ujson.renderers.UJSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "drf_ujson.parsers.UJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_THROTTLE_CLASSES": ("api.throttling.UserRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "50/minute",
        "user": "100/minute",
        "dj_rest_auth": "50/minute",
        "user_delete": "3/minute",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "TEST_REQUEST_RENDERER_CLASSES": (
        "drf_ujson.renderers.UJSONRenderer",
        "rest_framework.renderers.MultiPartRenderer",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# AllAuth
SITE_ID = 1
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
SOCIALACCOUNT_PROVIDERS = {
    "google": {"ID_TOKEN_ISSUER": "accounts.google.com"},
    "facebook": {},
}
SOCIALACCOUNT_ADAPTER = "api.socialaccount_adapter.SocialAccountAdapter"

# dj-rest-auth
REST_AUTH = {
    "OLD_PASSWORD_FIELD_ENABLED": True,
    "USER_DETAILS_SERIALIZER": "api.serializers.UserDetailsSerializer",
    "PASSWORD_CHANGE_SERIALIZER": "api.serializers.PasswordChangeSerializer",
    "PASSWORD_RESET_CONFIRM_SERIALIZER": "api.serializers.PasswordResetConfirmSerializer",
    "REGISTER_SERIALIZER": "api.serializers.RegisterSerializer",
    "LOGIN_SERIALIZER": "api.serializers.LoginSerializer",
    "TOKEN_CREATOR": "api.token_creator.create_token",
    "TOKEN_MODEL": "api.models.Token",
}

# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "RSS Temple API",
    "DESCRIPTION": "RSS Temple is a RSS/Atom service",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "AUTHENTICATION_WHITELIST": [
        "api.authentication.ExpiringTokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

# corsheaders
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["X-CSRFToken"]

# django-csp
CSP_IMG_SRC = ("'self'", "data:", "cdn.redoc.ly", "cdn.jsdelivr.net")
CSP_STYLE_SRC_ELEM = (
    "'self'",
    "'unsafe-inline'",
    "fonts.googleapis.com",
    "cdn.jsdelivr.net",
)
CSP_SCRIPT_SRC_ELEM = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net")
CSP_SCRIPT_SRC_ATTR = ("'self'", "'unsafe-inline'")
CSP_WORKER_SRC = ("'self'", "blob:")
CSP_FONT_SRC = ("'self'", "fonts.gstatic.com")

# django-silk
SILKY_INTERCEPT_PERCENT = int(os.getenv("APP_SILK_INTERCEPT_PERCENT", "50"))
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_RECORDED_REQUESTS = 10**4
SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10
SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
SILKY_PYTHON_PROFILER_RESULT_PATH = os.path.join(BASE_DIR, "_silk_profiles")
SILKY_PYTHON_PROFILER_EXTENDED_FILE_NAME = True
SILKY_DELETE_PROFILES = True
SILKY_MAX_REQUEST_BODY_SIZE = int(
    os.getenv("APP_SILKY_MAX_REQUEST_BODY_SIZE", "8192")
)  # 8kb
SILKY_MAX_RESPONSE_BODY_SIZE = int(
    os.getenv("APP_SILKY_MAX_RESPONSE_BODY_SIZE", "8192")
)  # 8kb

# app
_test_runner_type = os.getenv("TEST_RUNNER_TYPE", "standard").lower()
if _test_runner_type == "standard":
    pass
elif _test_runner_type == "timed":
    TEST_RUNNER = "rss_temple.testrunner.DjangoTimedTestRunner"
    TEST_SLOW_TEST_THRESHOLD = float(os.getenv("TEST_SLOW_TEST_THRESHOLD", "0.5"))
else:
    raise RuntimeError("unknown 'TEST_RUNNER_TYPE'")

DOWNLOAD_MAX_BYTE_COUNT = int(
    os.getenv("APP_DOWNLOAD_MAX_BYTE_COUNT", "-1")
)  # set to -1 for unlimited

_captcha_data_path = Path(__file__).parent / "../api/captcha/"

CAPTCHA_EXPIRY_INTERVAL = datetime.timedelta(minutes=5)
CAPTCHA_IMAGE_WIDTH = 160
CAPTCHA_IMAGE_HEIGHT = 60
CAPTCHA_IMAGE_FONTS_DIR = [
    str(_captcha_data_path / "fonts/Moms_typewriter.ttf"),
    str(_captcha_data_path / "fonts/Sears_Tower.ttf"),
]
CAPTCHA_IMAGE_FONT_SIZES = (44, 50, 56)
CAPTCHA_AUDIO_VOICES_DIR = str(_captcha_data_path / "voices/")
CAPTCHA_SEND_ANSWER = os.getenv("APP_CAPTCHA_SEND_ANSWER") == "true"

TOKEN_EXPIRY_INTERVAL = datetime.timedelta(days=14)

USER_UNREAD_GRACE_INTERVAL = datetime.timedelta(days=-7)
USER_UNREAD_GRACE_MIN_COUNT = 10

SUCCESS_BACKOFF_SECONDS = 60.0
MIN_ERROR_BACKOFF_SECONDS = 60.0
MAX_ERROR_BACKOFF_SECONDS = 60.0 * 60.0 * 24.0 * 28.0 * 3.0  # 3 months
FEED_IS_DEAD_MAX_INTERVAL = datetime.timedelta(days=28.0 * 6)  # 6 months

ARCHIVE_BACKOFF_SECONDS = 60.0 * 60.0 * 24.0  # 1 day
ARCHIVE_TIME_THRESHOLD = datetime.timedelta(days=-45)
ARCHIVE_COUNT_THRESHOLD = 1000

MAX_FEED_ENTRIES_STABLE_QUERY_COUNT = 5000
FEED_ENTRY_LANGUAGES_CACHE_TIMEOUT_SECONDS = 60.0 * 5.0  # 5 minutes

FEED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS = 60.0 * 15.0  # 15 minutes
FEED_ARCHIVED_COUNT_LOOKUPS_CACHE_TIMEOUT_SECONDS = 60.0 * 60.0 * 12.0  # 12 hours

ACCOUNT_CONFIRM_EMAIL_URL = os.getenv(
    "APP_ACCOUNT_CONFIRM_EMAIL_URL", "http://localhost:4200/verify?token=%(key)s"
)
ACCOUNT_EMAIL_VERIFICATION_SENT_URL = os.getenv(
    "APP_ACCOUNT_EMAIL_VERIFICATION_SENT_URL", "http://localhost:4200/emailsent"
)
PASSWORD_RESET_CONFIRM_URL_FORMAT = os.getenv(
    "APP_PASSWORD_RESET_CONFIRM_URL_FORMAT",
    "http://localhost:4200/resetpassword?token=%(token)s&userId=%(userId)s",
)
SOCIAL_CONNECTIONS_URL = os.getenv(
    "APP_SOCIAL_CONNECTIONS_URL", "http://localhost:4200/main/profile"
)
SOCIAL_SIGNUP_URL = os.getenv("APP_SOCIAL_SIGNUP_URL", "http://localhost:4200/register")

LINGUA_MINIMUM_RELATIVE_DISTANCE = 0.45

LABELING_EXPIRY_INTERVAL = datetime.timedelta(days=7)

EXPOSED_FEEDS_CACHE_TIMEOUT_SECONDS: float | None = 60.0 * 60.0 * 12.0  # 12 hours
CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS: float | None = (
    60.0 * 30.0
)  # 30 minutes

try:
    from .local_settings import *  # noqa: F403
except ImportError:
    pass
