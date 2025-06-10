# models.py

import secrets
from django.db import models
from django.contrib.auth.models import User

class APIKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_key')
    key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def regenerate_key(self):
        self.key = secrets.token_hex(20)
        self.save()

    def __str__(self):
        return f"{self.user.username}'s API Key"
