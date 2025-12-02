from django.contrib import admin

from roster.models import WorkplaceUserPlacement, StudentGroup


class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'students_count', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('students',)
    readonly_fields = ('created_at', 'updated_at')


admin.site.register(WorkplaceUserPlacement)
admin.site.register(StudentGroup, StudentGroupAdmin)