"""
Django settings for rss_temple project.
"""

import os
import datetime

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ')xz)&yg4)5vlgl*e&%l0ix0q&+s7)5f5#@(=r6eqcfkv^0+oz6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'api.middleware.bodyhandler.BodyHandlerMiddleware',
    'api.middleware.profiling.ProfileMiddleware',
    'api.middleware.cors.CORSMiddleware',
    'api.middleware.authentication.AuthenticationMiddleware',

    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'rss_temple.urls'

WSGI_APPLICATION = 'rss_temple.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    },
}


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = False

USE_L10N = False

USE_TZ = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
        'rss_temple': {
            'handlers': ['console'],
            'level': os.getenv('RSS_TEMPLE_LOG_LEVEL', 'INFO'),
        },
        'metrics': {
            'handlers': ['console'],
            'level': os.getenv('METRICS_LOG_LEVEL', 'INFO'),
        },
    },
}

CORS_ALLOW_ORIGINS = '*'
CORS_ALLOW_METHODS = 'GET,POST,PUT,DELETE,OPTIONS,HEAD'
CORS_ALLOW_HEADERS = 'Pragma,Cache-Control,Content-Type,If-Modified-Since,X-Requested-With,Authorization,X-Session-Token,X-Auth-Token'
CORS_EXPOSE_HEADERS = ''

PROFILING_OUTPUT_FILE = os.environ.get('PROFILING_OUTPUT_FILE')

AUTHENTICATION_DISABLE = [
    (r'^/api/login/my/?$', ['POST']),
    (r'^/api/login/google/?$', ['POST']),
    (r'^/api/login/facebook/?$', ['POST']),
    (r'^/api/login/my/session/?$', ['POST']),
    (r'^/api/login/google/session/?$', ['POST']),
    (r'^/api/login/facebook/session/?$', ['POST']),
]

REALM = 'RSS Temple'

DEFAULT_COUNT = 50
MAX_COUNT = 1000
DEFAULT_SKIP = 0
DEFAULT_RETURN_OBJECTS = True
DEFAULT_RETURN_TOTAL_COUNT = True

DEFAULT_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_DATE_FORMAT = '%Y-%m-%d'
DEFAULT_TIME_FORMAT = '%H:%M:%S'

SESSION_EXPIRY_INTERVAL = datetime.timedelta(days=1)

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
