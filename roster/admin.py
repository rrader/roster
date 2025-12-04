from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from roster.models import WorkplaceUserPlacement, StudentGroup, StudentGroupFeature, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профіль'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


class StudentGroupFeatureInline(admin.TabularInline):
    model = StudentGroupFeature
    extra = 1


class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'students_count', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('students',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StudentGroupFeatureInline]


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.register(WorkplaceUserPlacement)
admin.site.register(StudentGroup, StudentGroupAdmin)
admin.site.register(StudentGroupFeature)