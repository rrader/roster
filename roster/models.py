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


class StudentGroupFeature(models.Model):
    """Model for storing features enabled for a student group"""
    FEATURE_CHOICES = [
        ('non_sequential', 'Не садити поруч (послідовні номери)'),
    ]

    group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='features')
    feature_key = models.CharField(max_length=50, choices=FEATURE_CHOICES, verbose_name="Функція")
    enabled = models.BooleanField(default=True, verbose_name="Увімкнено")
    parameters = models.JSONField(default=dict, blank=True, verbose_name="Параметри")

    class Meta:
        verbose_name = "Налаштування групи"
        verbose_name_plural = "Налаштування груп"
        unique_together = ['group', 'feature_key']

    def __str__(self):
        return f"{self.group.name} - {self.get_feature_key_display()}"



class Workplace(models.Model):
    """Model which represents a specific workplace"""
    workplace_number = models.IntegerField(unique=True, verbose_name="Номер робочого місця")
    
    class Meta:
        verbose_name = "Робоче місце"
        verbose_name_plural = "Робочі місця"
    
    def __str__(self):
        return f"W-{self.workplace_number}"


class WorkplaceScreenshot(models.Model):
    """Model which represents a historical screenshot"""
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE, related_name='screenshots')
    screenshot_filename = models.CharField(max_length=255, verbose_name="Ім'я файлу")
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='screenshots')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    reported_workplace = models.CharField(max_length=255, null=True, blank=True, verbose_name="Робоче місце (з запиту)")
    os_username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Користувач OS")
    window_titles = models.JSONField(default=list, blank=True, verbose_name="Заголовки вікон")
    image_deleted = models.BooleanField(default=False, verbose_name="Зображення видалено")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Скріншот"
        verbose_name_plural = "Скріншоти"
    
    def __str__(self):
        return f"Screenshot {self.workplace} - {self.created_at}"


class Classroom(models.Model):
    """Model for storing classroom-specific settings"""
    classroom_id = models.CharField(max_length=50, primary_key=True, verbose_name="ID кабінету")
    screenshots_enabled = models.BooleanField(default=True, verbose_name="Скріншоти увімкнені")
    screenshot_interval = models.IntegerField(default=60, verbose_name="Інтервал скріншотів (сек)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    
    class Meta:
        verbose_name = "Кабінет"
        verbose_name_plural = "Кабінети"
    
    def __str__(self):
        return f"Кабінет {self.classroom_id}"


class UserProfile(models.Model):
    """Extended user profile with additional settings"""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    use_google_login = models.BooleanField(
        default=False, 
        verbose_name="Використовувати Google Login",
        help_text="Дозволити студенту входити через Google акаунт"
    )
    
    class Meta:
        verbose_name = "Профіль користувача"
        verbose_name_plural = "Профілі користувачів"
    
    def __str__(self):
        return f"Profile: {self.user.get_full_name() or self.user.username}"
