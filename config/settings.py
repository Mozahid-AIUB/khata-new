import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key-for-dev')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ADMIN_URL = os.getenv('ADMIN_URL', 'secret-admin-2024')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',   # 4.2 Sitemap support
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': False,  # ← এটা রাখুন
        'OPTIONS': {
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',  # ✅ এটা যোগ করুন
            ],
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.cart_count',
                'core.context_processors.site_settings',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# ── AI Keys ──────────────────────────
OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL        = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY', '')
HUGGINGFACE_MODEL   = os.getenv('HUGGINGFACE_MODEL', 'google/flan-t5-small')

# ── SSLCommerz Payment Gateway ───────
# Sandbox: https://sandbox.sslcommerz.com → Developer Dashboard এ account খোলো
# Live:    https://merchant.sslcommerz.com
SSLCOMMERZ_STORE_ID   = os.getenv('SSLCOMMERZ_STORE_ID', '')
SSLCOMMERZ_STORE_PASS = os.getenv('SSLCOMMERZ_STORE_PASS', '')
SSLCOMMERZ_IS_SANDBOX = os.getenv('SSLCOMMERZ_IS_SANDBOX', 'True') == 'True'

# ── Google Analytics ─────────────────
GA_MEASUREMENT_ID = os.getenv('GA_MEASUREMENT_ID', '')  # e.g. G-XXXXXXXXXX

# ── Rate Limiting ─────────────────────
# Max requests per window for sensitive endpoints
RATE_LIMIT_CHECKOUT   = int(os.getenv('RATE_LIMIT_CHECKOUT', '5'))    # 5 per window
RATE_LIMIT_WINDOW_SEC = int(os.getenv('RATE_LIMIT_WINDOW_SEC', '60')) # 60 seconds

# ── Cache (default: in-memory locmem, upgrade to Redis in prod) ──
# For Redis: pip install django-redis
# Then set: CACHE_BACKEND=django_redis.cache.RedisCache
# And:      REDIS_URL=redis://127.0.0.1:6379/1
_cache_backend = os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache')
_redis_url     = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')

if 'redis' in _cache_backend.lower():
    CACHES = {
        'default': {
            'BACKEND': _cache_backend,
            'LOCATION': _redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'IGNORE_EXCEPTIONS': True,  # graceful degradation if Redis is down
            },
            'KEY_PREFIX': 'pk',
            'TIMEOUT': 300,  # 5 min default
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': _cache_backend,
            'LOCATION': 'practical-khata-cache',
            'TIMEOUT': 300,
        }
    }

# ── Site ID (for django.contrib.sitemaps) ──
SITE_ID = 1

# ── Admin 2FA (django-otp + django-two-factor-auth) ──────────
# ACTIVATE:
#   pip install django-otp django-two-factor-auth qrcode[pil]
# Then add to INSTALLED_APPS:
#   'django_otp', 'django_otp.plugins.otp_totp', 'two_factor',
# And add to MIDDLEWARE (right after AuthenticationMiddleware):
#   'django_otp.middleware.OTPMiddleware',
# And change admin URL to use two-factor admin:
#   from two_factor.admin import AdminSiteOTPRequired
#   admin.site.__class__ = AdminSiteOTPRequired
# Then run: python manage.py migrate
ADMIN_2FA_ENABLED = os.getenv('ADMIN_2FA_ENABLED', 'False') == 'True'

if ADMIN_2FA_ENABLED:
    try:
        import django_otp  # noqa
        INSTALLED_APPS += [
            'django_otp',
            'django_otp.plugins.otp_totp',
            'django_otp.plugins.otp_static',
            'two_factor',
        ]
        # Insert OTP middleware after AuthenticationMiddleware
        _auth_idx = MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        MIDDLEWARE.insert(_auth_idx + 1, 'django_otp.middleware.OTPMiddleware')

        TWO_FACTOR_FORCE_OTP_ADMIN = True
        TWO_FACTOR_PATCH_ADMIN     = True
    except ImportError:
        pass  # Package not installed — 2FA silently disabled

# ── Security (Production) ────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER      = True
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    X_FRAME_OPTIONS                = 'DENY'
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True