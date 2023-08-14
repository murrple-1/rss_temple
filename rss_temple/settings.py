"""
Django settings for rss_temple project.

Generated by 'django-admin startproject' using Django 3.2.12.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

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
    "rest_framework.authtoken",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.google",
    "drf_yasg",
    "corsheaders",
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
]

if DEBUG:
    MIDDLEWARE.append("api.middleware.profiler.ProfilerMiddleware")

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
        "DIRS": [],
    },
]

WSGI_APPLICATION = "rss_temple.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

REDIS_URL = os.getenv("APP_REDIS_URL", "redis://redis:6379")

if os.getenv("APP_IN_DOCKER", "false").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql_psycopg2",
            "NAME": os.getenv("APP_DB_NAME", "postgres"),
            "USER": os.getenv("APP_DB_USER", "postgres"),
            "PASSWORD": os.getenv("APP_DB_PASSWORD", "password"),
            "HOST": os.getenv("APP_DB_HOST", "postgresql"),
            "PORT": int(os.getenv("APP_DB_PORT", "5432")),
        }
    }

    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"
    SESSION_COOKIE_SECURE = True
else:
    # Basically used in CI test phase or when running tests locally.
    # We don't load redis for that, so avoid setting the cache.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }
    SESSION_COOKIE_SECURE = False


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
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
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("APP_DJANGO_LOG_LEVEL", "INFO"),
        },
        "rss_temple": {
            "handlers": ["console"],
            "level": os.getenv("APP_LOG_LEVEL", "INFO"),
        },
        "rss_temple.feed_handler": {
            "handlers": ["console"],
            "level": os.getenv("APP_FEED_LOG_LEVEL", "ERROR"),
        },
    },
}

if os.getenv("APP_IN_DOCKER", "false").lower() == "true":
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/1",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 5,  # 5 minutes
        },
        "stable_query": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/2",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 60,  # 1 hour
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
    }

CSRF_TRUSTED_ORIGINS = (
    csrf_trusted_origins.split(",")
    if (csrf_trusted_origins := os.getenv("APP_CSRF_TRUSTED_ORIGINS")) is not None
    else []
)

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

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": ("drf_ujson.renderers.UJSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "drf_ujson.parsers.UJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "TEST_REQUEST_RENDERER_CLASSES": (
        "drf_ujson.renderers.UJSONRenderer",
        "rest_framework.renderers.MultiPartRenderer",
    ),
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
}

# drf-yasg
SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "SECURITY_DEFINITIONS": {
        "Basic": {"type": "basic"},
        "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"},
    },
    "SECURITY_REQUIREMENTS": [
        {"Basic": []},
        {"Bearer": []},
    ],
}

# corsheaders
CORS_ALLOW_ALL_ORIGINS = True

# app
_test_runner_type = os.environ.get("TEST_RUNNER_TYPE", "standard").lower()
if _test_runner_type == "standard":
    pass
elif _test_runner_type == "xml":
    TEST_RUNNER = "xmlrunner.extra.djangotestrunner.XMLTestRunner"
    TEST_OUTPUT_DIR = "./test-results/"
    TEST_OUTPUT_VERBOSE = int(os.environ.get("TEST_OUTPUT_VERBOSE", "1"))
elif _test_runner_type == "timed":
    TEST_RUNNER = "rss_temple.testrunner.DjangoTimedTestRunner"
    TEST_SLOW_TEST_THRESHOLD = float(os.environ.get("TEST_SLOW_TEST_THRESHOLD", "0.5"))
else:
    raise RuntimeError("unknown 'TEST_RUNNER_TYPE'")


USER_UNREAD_GRACE_INTERVAL = datetime.timedelta(days=-7)
USER_UNREAD_GRACE_MIN_COUNT = 10

SUCCESS_BACKOFF_SECONDS = 60
MIN_ERROR_BACKOFF_SECONDS = 60
MAX_ERROR_BACKOFF_SECONDS = 7257600  # 3 months

ARCHIVE_BACKOFF_SECONDS = 60 * 60 * 24
ARCHIVE_TIME_THRESHOLD = datetime.timedelta(days=-45)
ARCHIVE_COUNT_THRESHOLD = 1000

MAX_FEED_ENTRIES_STABLE_QUERY_COUNT = 5000

ACCOUNT_CONFIRM_EMAIL_URL = os.getenv(
    "APP_ACCOUNT_CONFIRM_EMAIL_URL", "http://localhost:4200/verify"
)
ACCOUNT_EMAIL_VERIFICATION_SENT_URL = os.getenv(
    "APP_ACCOUNT_EMAIL_VERIFICATION_SENT_URL", "http://localhost:4200/emailsent"
)
PASSWORD_RESET_CONFIRM_URL_FORMAT = os.getenv(
    "APP_PASSWORD_RESET_CONFIRM_URL_FORMAT",
    "http://localhost:4200/resetpassword?token={token}&userId={userId}",
)
SOCIAL_CONNECTIONS_URL = os.getenv(
    "APP_SOCIAL_CONNECTIONS_URL", "http://localhost:4200/main/profile"
)

try:
    from .local_settings import *
except ImportError:
    pass
