from django.db import models


class ParkingSlot(models.Model):
    slot_number = models.CharField(max_length=10)
    status = models.CharField(
        max_length=20,
        default="available"
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.slot_number


class SensorData(models.Model):
    SENSOR_TYPES = [
        ('car', 'Car Detection'),
        ('temperature', 'Temperature'),
        ('humidity', 'Humidity'),
        ('fire', 'Fire Detection'),
    ]

    sensor_type = models.CharField(
        max_length=20,
        choices=SENSOR_TYPES
    )

    value = models.CharField(
        max_length=50
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.CASCADE
    )


class Booking(models.Model):
    user_name = models.CharField(
        max_length=100
    )

    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.CASCADE
    )

    booking_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )