from pathlib import Path
from decouple import config, Csv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'trading',
    'sass_processor',
    'livereload',
    'compressor',
    'channels',
    'paypal.standard.ipn',
    'widget_tweaks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'sass_processor.finders.CssFinder',
    'compressor.finders.CompressorFinder',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Channels configuration
ASGI_APPLICATION = 'core.asgi.application'

# In-memory channel layer configuration for development
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# SASS processor settings
SASS_PROCESSOR_ROOT = BASE_DIR / 'static'
SASS_PROCESSOR_INCLUDE_DIRS = [
    BASE_DIR / 'static/sass',
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Django Compressor settings
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True  # Enable offline compression
COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

# This is optional, but it can speed up local development
SASS_PROCESSOR_ENABLED = True
SASS_PROCESSOR_AUTO_INCLUDE = False

# Where the compiled CSS will be stored
SASS_OUTPUT_STYLE = 'compressed'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_REDIRECT_URL = '/trading/dashboard/'
LOGIN_URL = '/login/'
LOGOUT_REDIRECT_URL = '/'

# PayPal settings
PAYPAL_RECEIVER_EMAIL = os.getenv('PAYPAL_RECEIVER_EMAIL', 'your-paypal-business-email@example.com')
PAYPAL_TEST = False  # Using live PayPal for real money transactions
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')  # Your PayPal client ID

# PayPal Live Settings
PAYPAL_BUY_BUTTON_IMAGE = 'https://www.paypalobjects.com/webstatic/en_US/i/buttons/buy-logo-medium.png'
PAYPAL_SUBSCRIPTION_BUTTON_IMAGE = 'https://www.paypalobjects.com/webstatic/en_US/i/buttons/subscribe-logo-medium.png'
PAYPAL_DONATION_BUTTON_IMAGE = 'https://www.paypalobjects.com/webstatic/en_US/i/buttons/donate-logo-medium.png'

# Bank Transfer Settings
BANK_NAME = os.getenv('BANK_NAME', 'Example Bank')
BANK_ACCOUNT_NUMBER = os.getenv('BANK_ACCOUNT_NUMBER', '1234567890')

# Cryptocurrency Settings
CRYPTO_WALLET_ADDRESS = os.getenv('CRYPTO_WALLET_ADDRESS', 'your-crypto-wallet-address')

# Logging settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/trading.log',
        },
    },
    'loggers': {
        # 'django': {
        #     'handlers': ['file'],
        #     'level': 'DEBUG',
        #     'propagate': True,
        # },
        'trading': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}