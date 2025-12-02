from django.db import models


class WorkplaceUserPlacement(models.Model):
    """Model which stores the workplace id for the user, and time when it was recorded"""
    workplace_id = models.CharField(max_length=100)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.workplace_id} - {self.created_at}"


class StudentGroup(models.Model):
    """Model for storing student groups"""
    name = models.CharField(max_length=200, unique=True, verbose_name="Назва групи")
    description = models.TextField(blank=True, verbose_name="Опис")
    students = models.ManyToManyField('auth.User', related_name='student_groups', blank=True, verbose_name="Учні")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        verbose_name = "Група учнів"
        verbose_name_plural = "Групи учнів"
        ordering = ['name']

    def __str__(self):
        return self.name

    def students_count(self):
        return self.students.count()
