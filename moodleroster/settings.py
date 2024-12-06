"""
Django settings for moodleroster project.

Generated by 'django-admin startproject' using Django 4.2.16.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""
import os
from datetime import time
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-f@ma$_^0@^7)edrprt@ig-qra+()0en7@qxelp)yox*eskb&m8'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

BASE_DOMAIN = 'rmn.pp.ua'
CLASSROOM_URL = 'https://class.rmn.pp.ua/lesson'
ALLOWED_HOSTS = [f'students.{BASE_DOMAIN}', '127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = [f'https://students.{BASE_DOMAIN}', f'https://class.{BASE_DOMAIN}']
CSRF_COOKIE_DOMAIN = f'.{BASE_DOMAIN}'
CSRF_COOKIE_NAME = 'csrftoken_2'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap5',
    'roster',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'roster.middleware.MoodleLogoutMiddleware',
    'roster.middleware.CSPMiddleware',
]

ROOT_URLCONF = 'moodleroster.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'moodleroster.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Kyiv'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

X_FRAME_OPTIONS = "ALLOW"

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SAMESITE = 'None'

LESSONS_SCHEDULE = {
    0: {
        'start': time(8, 0),
        'end': time(8, 30),
    },
    1: {
        'start': time(9, 0),
        'end': time(9, 45),
    },
    2: {
        'start': time(9, 55),
        'end': time(10, 40),
    },
    3: {
        'start': time(10, 50),
        'end': time(11, 35),
    },
    4: {
        'start': time(11, 55),
        'end': time(12, 40),
    },
    5: {
        'start': time(13, 0),
        'end': time(13, 45),
    },
    6: {
        'start': time(13, 55),
        'end': time(14, 40),
    },
    7: {
        'start': time(14, 50),
        'end': time(15, 35),
    },
    8: {
        'start': time(15, 45),
        'end': time(16, 30),
    },
    9: {
        'start': time(23, 59),
        'end': time(23, 59),
    },
}