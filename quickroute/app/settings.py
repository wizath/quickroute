"""
Settings module for QuickRoute

Provides configuration patterns with environment variable support.
"""

import os
from typing import List, Dict, Any


class BaseSettings:
    """
    Base settings class with environment variable support.
    """

    SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-me')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    INSTALLED_APPS = [
        'app.routers.auth',
        'app.routers.users',
    ]

    MIDDLEWARE = [
        'app.middleware.RequestIDMiddleware',
        'app.middleware.LoggingMiddleware',
        'app.middleware.SecurityHeadersMiddleware',
        'app.middleware.TimingMiddleware',
        'app.middleware.UserMiddleware',
        'app.middleware.SessionMiddleware',
        'starlette.middleware.cors.CORSMiddleware',
    ]

    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./db.sqlite')

    # Templates
    TEMPLATES = {
        'BACKEND': 'jinja2',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'app.context_processors.debug',
                'app.context_processors.request',
                'app.context_processors.auth',
            ],
        },
    }

  # Static files
    STATIC_URL = '/static/'
    STATIC_ROOT = 'staticfiles'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = 'media'

  # Internationalization
    LANGUAGE_CODE = 'en-us'
    TIME_ZONE = 'UTC'
    USE_I18N = True
    USE_TZ = True

    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '*').split(',')

    QUICKROUTE_TITLE = 'QuickRoute'
    QUICKROUTE_DESCRIPTION = 'Async Web Framework'
    QUICKROUTE_VERSION = '1.0.0'

    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', '8000'))

    ENABLE_ADMIN = os.getenv('ENABLE_ADMIN', 'True').lower() == 'true'
    ADMIN_URL = os.getenv('ADMIN_URL', '/admin')
    ADMIN_TITLE = os.getenv('ADMIN_TITLE', f'{QUICKROUTE_TITLE} Admin')
    ADMIN_LOGIN_URL = os.getenv('ADMIN_LOGIN_URL', '/admin/login')
    ADMIN_LOGOUT_URL = os.getenv('ADMIN_LOGOUT_URL', '/admin/logout')

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '30'))

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': 'fastdjango.log',
                'formatter': 'verbose',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'loggers': {
            'app': {
                'handlers': ['console', 'file'],
                'level': os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO'),
                'propagate': False,
            },
        },
    }

    DATABASES = {
        'default': {
            'ENGINE': 'sqlalchemy',
            'NAME': DATABASE_URL,
            'OPTIONS': {
                'echo': DEBUG,
                'pool_size': 5,
                'max_overflow': 10,
            }
        }
    }

    # Cache settings
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

    # Email settings
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

    # Session settings
    SESSION_COOKIE_AGE = 1209600  # 2 weeks
    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # CSRF settings
    CSRF_COOKIE_SECURE = not DEBUG
    CSRF_COOKIE_HTTPONLY = True
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else []

    # Plugin System
    INSTALLED_PLUGINS = [
        'quickroute.plugins.celery',
    ]

    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_SETTINGS_MODULE = os.getenv('CELERY_SETTINGS_MODULE', None)
    CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
    CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))
    CELERY_TASK_ACKS_LATE = os.getenv('CELERY_TASK_ACKS_LATE', 'True').lower() == 'true'

    WEBSOCKET_REQUIRE_AUTH = os.getenv('WEBSOCKET_REQUIRE_AUTH', 'False').lower() == 'true'
    WEBSOCKET_RATE_LIMIT = os.getenv('WEBSOCKET_RATE_LIMIT', 'True').lower() == 'true'
    WEBSOCKET_MAX_CONNECTIONS = int(os.getenv('WEBSOCKET_MAX_CONNECTIONS', '100'))
    WEBSOCKET_MAX_MESSAGES_PER_MINUTE = int(os.getenv('WEBSOCKET_MAX_MESSAGES_PER_MINUTE', '60'))
    WEBSOCKET_ALLOWED_ORIGINS = os.getenv('WEBSOCKET_ALLOWED_ORIGINS', '*').split(',') if os.getenv('WEBSOCKET_ALLOWED_ORIGINS') else ['*']


class DevelopmentSettings(BaseSettings):
    """Development environment settings"""

    DEBUG = True
    DATABASE_URL = 'sqlite+aiosqlite:///./db.sqlite'

    def __init__(self):
        super().__init__()
        self.LOGGING['loggers']['app']['level'] = 'DEBUG'

    SERVE_STATIC_FILES = True
    SERVE_MEDIA_FILES = True


class TestingSettings(BaseSettings):
    """Testing environment settings"""

    DEBUG = True
    DATABASE_URL = 'sqlite+aiosqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret'

    def __init__(self):
        super().__init__()
        self.LOGGING['loggers']['app']['level'] = 'WARNING'

    EMAIL_BACKEND = 'app.mail.backends.locmem.EmailBackend'


class ProductionSettings(BaseSettings):
    """Production environment settings"""

    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    def __init__(self):
        super().__init__()
        self.LOGGING['loggers']['app']['level'] = 'WARNING'

    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# Environment-based settings selection
def get_settings() -> BaseSettings:
    """
    Get settings class based on DJANGO_SETTINGS_MODULE environment variable.

    Similar to traditional frameworks's settings module loading.
    """
    settings_module = os.getenv('DJANGO_SETTINGS_MODULE', 'Development')

    settings_map = {
        'Development': DevelopmentSettings,
        'Testing': TestingSettings,
        'Production': ProductionSettings,
        'app.settings.Development': DevelopmentSettings,
        'app.settings.Testing': TestingSettings,
        'app.settings.Production': ProductionSettings,
    }

    settings_class = settings_map.get(settings_module, DevelopmentSettings)
    return settings_class()


# Global settings object
settings = get_settings()


# utility functions
def get_setting(name: str, default: Any = None) -> Any:
    """
    Get setting value with default fallback.

    Similar to getattr(settings, 'NAME', default) in Django.
    """
    return getattr(settings, name, default)


def configure_settings(**kwargs):
    """
    Override settings at runtime.

    Similar to traditional frameworks's settings.configure() for testing.
    """
    for key, value in kwargs.items():
        setattr(settings, key, value)


def validate_settings():
    """
    Validate critical settings are properly configured.

    Raises ValueError if required settings are missing.
    """
    critical_settings = [
        'SECRET_KEY',
        'DATABASE_URL',
        'JWT_SECRET_KEY',
    ]

    missing_settings = []
    for setting_name in critical_settings:
        setting_value = getattr(settings, setting_name, None)

        if (setting_value is None or
            setting_value == '' or
            'change-me' in str(setting_value).lower() or
            'insecure' in str(setting_value).lower() and not settings.DEBUG):
            missing_settings.append(setting_name)

    if missing_settings:
        raise ValueError(
            f"Critical settings must be configured for production: {', '.join(missing_settings)}. "
            f"Set environment variables or update your settings."
        )


# Auto-validate in production
if not settings.DEBUG:
    try:
        validate_settings()
    except ValueError as e:
        import warnings
        warnings.warn(f"Settings validation failed: {e}", RuntimeWarning)


# settings context manager
class override_settings:
    """
    Temporarily override settings for testing.

    Usage:
        with override_settings(DEBUG=True, SECRET_KEY='test'):
            # settings.DEBUG is True here
            pass
        # settings.DEBUG is back to original value here
    """

    def __init__(self, **kwargs):
        self.overrides = kwargs
        self.original_values = {}

    def __enter__(self):
        for key, value in self.overrides.items():
            self.original_values[key] = getattr(settings, key, None)
            setattr(settings, key, value)
        return settings

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original values
        for key, value in self.original_values.items():
            if value is None:
                delattr(settings, key)
            else:
                setattr(settings, key, value)


# template context processors
def context_processors(request):
    """Default template context processors like Django"""
    return {
        'DEBUG': settings.DEBUG,
        'request': request,
        'settings': settings,
    }