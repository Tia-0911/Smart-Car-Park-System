from django.contrib import admin
from .models import SensorReading

@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ("device_id", "temperature", "humidity", "created_at")
    list_filter = ("device_id",)
