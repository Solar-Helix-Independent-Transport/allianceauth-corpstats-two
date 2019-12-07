import os

from django.contrib import messages
from celery.schedules import crontab

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_celery_beat',
    'bootstrapform',
    'sortedm2m',
    'esi',
    'allianceauth',
    'allianceauth.authentication',
    'allianceauth.services',
    'allianceauth.eveonline',
    'allianceauth.groupmanagement',
    'allianceauth.notifications',
    'allianceauth.thirdparty.navhelper',
]

SECRET_KEY = "wow I'm a really bad default secret key"

# Celery configuration
BROKER_URL = 'redis://localhost:6379/0'
CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"
CELERYBEAT_SCHEDULE = {
    'esi_cleanup_callbackredirect': {
        'task': 'esi.tasks.cleanup_callbackredirect',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'esi_cleanup_token': {
        'task': 'esi.tasks.cleanup_token',
        'schedule': crontab(minute=0, hour=0),
    },
    'run_model_update': {
        'task': 'allianceauth.eveonline.tasks.run_model_update',
        'schedule': crontab(minute=0, hour="*/6"),
    },
    'check_all_character_ownership': {
        'task': 'allianceauth.authentication.tasks.check_all_character_ownership',
        'schedule': crontab(minute=0, hour='*/4'),
    }
}

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
]

ROOT_URLCONF = 'allianceauth.urls'

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale/'),
)

ugettext = lambda s: s
LANGUAGES = (
    ('en', ugettext('English')),
    ('de', ugettext('German')),
    ('es', ugettext('Spanish')),
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(PROJECT_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'allianceauth.notifications.context_processors.user_notification_count',
                'allianceauth.groupmanagement.context_processors.can_manage_groups',
                'allianceauth.context_processors.auth_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'allianceauth.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

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

AUTHENTICATION_BACKENDS = ['allianceauth.authentication.backends.StateBackend',
                           'django.contrib.auth.backends.ModelBackend']

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Bootstrap messaging css workaround
MESSAGE_TAGS = {
    messages.ERROR: 'danger'
}

CACHES = {
    "default": {
        "BACKEND": "redis_cache.RedisCache",
        "LOCATION": "localhost:6379",
        "OPTIONS": {
            "DB": 1,
        }
    }
}

DEBUG = True
ALLOWED_HOSTS = ['*']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(os.path.join(BASE_DIR, 'alliance_auth.sqlite3')),
    },
}

SITE_NAME = 'Alliance Auth'

LOGIN_URL = 'auth_login_user'  # view that handles login logic

LOGIN_REDIRECT_URL = 'authentication:dashboard'  # default destination when logging in if no redirect specified
LOGOUT_REDIRECT_URL = 'authentication:dashboard'  # destination after logging out
# Both of these redirects accept values as per the django redirect shortcut
# https://docs.djangoproject.com/en/1.11/topics/http/shortcuts/#redirect
# - url names eg 'authentication:dashboard'
# - relative urls eg '/dashboard'
# - absolute urls eg 'http://example.com/dashboard'

# scopes required on new tokens when logging in. Cannot be blank.
LOGIN_TOKEN_SCOPES = ['publicData']

# number of days email verification links are valid for
ACCOUNT_ACTIVATION_DAYS = 1

ESI_API_URL = 'https://esi.evetech.net/'

# These are required for Django to function properly. Don't touch.
SECRET_KEY = '123456789abcd'

# This is where css/images will be placed for your webserver to read
STATIC_ROOT = "/var/www/testauth/static/"

# Change this to change the name of the auth site displayed
# in page titles and the site header.
SITE_NAME = 'testauth'

# Change this to enable/disable debug mode, which displays
# useful error messages but can leak sensitive data.
DEBUG = False

# Add any additional apps to this list.
INSTALLED_APPS += [
'corpstats',
]

# Enter credentials to use MySQL/MariaDB. Comment out to use sqlite3
"""
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'alliance_auth',
    'USER': '',
    'PASSWORD': '',
    'HOST': '127.0.0.1',
    'PORT': '3306',
    'OPTIONS': {'charset': 'utf8mb4'},
}
"""

# Register an application at https://developers.eveonline.com for Authentication
# & API Access and fill out these settings. Be sure to set the callback URL
# to https://example.com/sso/callback substituting your domain for example.com
# Logging in to auth requires the publicData scope (can be overridden through the
# LOGIN_TOKEN_SCOPES setting). Other apps may require more (see their docs).
ESI_SSO_CLIENT_ID = 'dummy'
ESI_SSO_CLIENT_SECRET = 'dummy'
ESI_SSO_CALLBACK_URL = 'http://localhost:8000'

# By default emails are validated before new users can log in.
# It's recommended to use a free service like SparkPost or Elastic Email to send email.
# https://www.sparkpost.com/docs/integrations/django/
# https://elasticemail.com/resources/settings/smtp-api/
# Set the default from email to something like 'noreply@example.com'
# Email validation can be turned off by uncommenting the line below. This can break some services.
REGISTRATION_VERIFY_EMAIL = False
EMAIL_HOST = ''
EMAIL_PORT = 587
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = ''

#######################################
# Add any custom settings below here. #
#######################################

