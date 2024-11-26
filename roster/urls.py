from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("key_required/<int:uid>/", views.key_required, name="key_required"),
    path("search_users_ajax/", views.search_users_ajax, name='search_users_ajax'),
    path("classroom_workplace_login/<str:workplace_id>/", views.classroom_workplace_login, name='classroom_workplace_login'),
    path("classroom", views.classroom, name='classroom'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
