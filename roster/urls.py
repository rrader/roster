from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("key_required/<int:uid>/", views.key_required, name="key_required"),
    path("search_users_ajax/", views.search_users_ajax, name='search_users_ajax'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
