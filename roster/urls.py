from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    # path("fill_data/<int:uid>/", views.fill_data, name="fill_data"),
    path("search_users_ajax/", views.search_users_ajax, name='search_users_ajax'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
