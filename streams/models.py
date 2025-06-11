# models.py

import secrets
from django.db import models
from django.contrib.auth.models import User

import uuid

class APIKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_key')
    key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def regenerate_key(self):
        self.key = secrets.token_hex(20)
        self.save()

    def __str__(self):
        return f"{self.user.username}'s API Key"


def upload_to(instance, filename):
    return f"feedback_videos/{instance.unique_id}.mp4"

class Feedback(models.Model):
    unique_id = models.CharField(max_length=36, primary_key=True)  # Full UUID
    user_id = models.CharField(max_length=100)
    feedback_text = models.TextField()
    video_url = models.URLField()
    trimmed_video = models.FileField(upload_to=upload_to)
    start_time = models.CharField(max_length=20)
    end_time = models.CharField(max_length=20)
    feedback_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback {self.unique_id} by {self.user_id}"