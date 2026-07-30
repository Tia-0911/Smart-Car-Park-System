from django.db import models
from django.utils import timezone
from django.urls import reverse


class ParkingSlot(models.Model):
    slot_number = models.CharField(max_length=10)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.slot_number


class Booking(models.Model):
    user_name = models.CharField(max_length=100)

    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.CASCADE
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    qr_code = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )


    def __str__(self):
        return f"{self.user_name} - {self.parking_slot}"


class Gate(models.Model):
    gate_name = models.CharField(
        max_length=50,
        default="Entrance Gate"
    )

    is_open = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.gate_name