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
SECRET_KEY = "django-insecure-$*7qpc@r-g3e67e=qze01cq3zbwwy9z^5qws1$qmr^+%=z*h6b"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api.apps.ApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.throttle.ThrottleMiddleware",
    "api.middleware.bodyhandler.BodyHandlerMiddleware",
    "api.middleware.profiling.ProfileMiddleware",
    "api.middleware.cors.CORSMiddleware",  # deprecate
    "api.middleware.authentication.AuthenticationMiddleware",
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
        "DIRS": [
            "api/render",
        ],
    },
]

WSGI_APPLICATION = "rss_temple.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}


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


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"

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
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
        },
        "rss_temple": {
            "handlers": ["console"],
            "level": os.environ.get("RSS_TEMPLE_LOG_LEVEL", "INFO"),
        },
        "metrics": {
            "handlers": ["console"],
            "level": os.environ.get("METRICS_LOG_LEVEL", "INFO"),
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "default-cache",
    },
    "stable_query": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "stable-query-cache",
    },
    "throttle": {
        # this should be memcache or Redis in production. don't enable in dev, as it causes tests to fail
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
}

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

THROTTLE_ENABLE = [
    (
        "authentications",
        [
            (r"^/api/login/my/?$", ["POST"]),
            (r"^/api/login/google/?$", ["POST"]),
            (r"^/api/login/facebook/?$", ["POST"]),
            (r"^/api/login/my/session/?$", ["POST"]),
            (r"^/api/login/google/session/?$", ["POST"]),
            (r"^/api/login/facebook/session/?$", ["POST"]),
            (r"^/api/session/?$", ["DELETE"]),
            (r"^/api/passwordresettoken/request/?$", ["POST"]),
            (r"^/api/passwordresettoken/reset/?$", ["POST"]),
            (r"^/api/passwordresettoken/reset/?$", ["POST"]),
            (r"^/api/user/verify/?$", ["POST"]),
        ],
        30,
        60,
    ),
]

CORS_ALLOW_ORIGINS = "*"
CORS_ALLOW_METHODS = "GET,POST,PUT,DELETE,OPTIONS,HEAD"
CORS_ALLOW_HEADERS = "Pragma,Cache-Control,Content-Type,If-Modified-Since,X-Requested-With,Authorization,X-Session-Token"
CORS_EXPOSE_HEADERS = ""

PROFILING_OUTPUT_FILE = os.environ.get("PROFILING_OUTPUT_FILE")

AUTHENTICATION_DISABLE = [
    (r"^/api/login/my/?$", ["POST"]),
    (r"^/api/login/google/?$", ["POST"]),
    (r"^/api/login/facebook/?$", ["POST"]),
    (r"^/api/login/my/session/?$", ["POST"]),
    (r"^/api/login/google/session/?$", ["POST"]),
    (r"^/api/login/facebook/session/?$", ["POST"]),
    (r"^/api/session/?$", ["DELETE"]),
    (r"^/api/passwordresettoken/request/?$", ["POST"]),
    (r"^/api/passwordresettoken/reset/?$", ["POST"]),
    (r"^/api/passwordresettoken/reset/?$", ["POST"]),
    (r"^/api/user/verify/?$", ["POST"]),
]

REALM = "RSS Temple"

DEFAULT_COUNT = 50
MAX_COUNT = 1000
DEFAULT_SKIP = 0
DEFAULT_RETURN_OBJECTS = True
DEFAULT_RETURN_TOTAL_COUNT = True

DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M:%S"

SESSION_EXPIRY_INTERVAL = datetime.timedelta(days=1)

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]

USER_VERIFICATION_EXPIRY_INTERVAL = datetime.timedelta(days=30)
PASSWORDRESETTOKEN_EXPIRY_INTERVAL = datetime.timedelta(days=1)
VERIFY_URL_FORMAT = "http://localhost:4200/verify?token={verify_token}"

USER_UNREAD_GRACE_INTERVAL = datetime.timedelta(days=-7)
USER_UNREAD_GRACE_MIN_COUNT = 10

SUCCESS_BACKOFF_SECONDS = 60
MIN_ERROR_BACKOFF_SECONDS = 60
MAX_ERROR_BACKOFF_SECONDS = 7257600  # 3 months
