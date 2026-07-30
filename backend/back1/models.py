from django.db import models
from django.utils import timezone
from django.urls import reverse


class SensorReading(models.Model):
    temperature = models.FloatField()
    humidity = models.FloatField()
    device_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.device_id} @ {self.created_at}"

    def get_absolute_url(self):
        return reverse(
            'back1:reading-detail',
            kwargs={'pk': self.pk}
        )