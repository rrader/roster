from django.db import models


class WorkplaceUserPlacement(models.Model):
    """Model which stores the workplace id for the user, and time when it was recorded"""
    workplace_id = models.CharField(max_length=100)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.workplace_id} - {self.created_at}"
