from django.contrib import admin

from roster.models import WorkplaceUserPlacement, StudentGroup, StudentGroupFeature


class StudentGroupFeatureInline(admin.TabularInline):
    model = StudentGroupFeature
    extra = 1


class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'students_count', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('students',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StudentGroupFeatureInline]


admin.site.register(WorkplaceUserPlacement)
admin.site.register(StudentGroup, StudentGroupAdmin)
admin.site.register(StudentGroupFeature)