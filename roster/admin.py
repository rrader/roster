from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from roster.models import (
    WorkplaceUserPlacement,
    StudentGroup,
    StudentGroupFeature,
    UserProfile,
    Workplace,
    WorkplaceScreenshot,
    Classroom
)


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


class WorkplaceScreenshotAdmin(admin.ModelAdmin):
    list_display = ('screenshot_preview', 'workplace', 'user', 'os_username', 'reported_workplace', 'created_at', 'image_deleted')
    list_filter = ('workplace', 'image_deleted', 'created_at')
    search_fields = ('os_username', 'reported_workplace', 'user__username', 'user__last_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('screenshot_preview',)

    def screenshot_preview(self, obj):
        from django.utils.safestring import mark_safe
        if obj.screenshot_filename and not obj.image_deleted:
            # Using the same API endpoint we use in the frontend
            url = f"/api/classrooms/329/workplaces/{obj.workplace.workplace_number}/screenshots/{obj.screenshot_filename}/?thumb=1"
            return mark_safe(f'<img src="{url}" style="width: 100px; height: auto; border: 1px solid #ccc; border-radius: 4px;" />')
        return "Немає зображення"
    
    screenshot_preview.short_description = 'Прев\'ю'


class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('classroom_id', 'screenshots_enabled', 'screenshot_interval', 'updated_at')


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.register(WorkplaceUserPlacement)
admin.site.register(StudentGroup, StudentGroupAdmin)
admin.site.register(StudentGroupFeature)
admin.site.register(Workplace)
admin.site.register(WorkplaceScreenshot, WorkplaceScreenshotAdmin)
admin.site.register(Classroom, ClassroomAdmin)