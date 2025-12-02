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
    path("logged_in/", views.logged_in, name='logged_in'),
    
    # Student Groups URLs
    path("groups/login/", views.groups_login, name='groups_login'),
    path("groups/logout/", views.groups_logout, name='groups_logout'),
    path("groups/", views.groups_list, name='groups_list'),
    path("groups/create/", views.group_create, name='group_create'),
    path("groups/<int:group_id>/", views.group_detail, name='group_detail'),
    path("groups/<int:group_id>/edit/", views.group_edit, name='group_edit'),
    path("groups/<int:group_id>/delete/", views.group_delete, name='group_delete'),
    path("groups/<int:group_id>/remove_student/<int:user_id>/", views.group_remove_student, name='group_remove_student'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
