from django.db import models
from django.contrib.auth.models import User


# ==========================
# Parking Slot
# ==========================

class ParkingSlot(models.Model):

    slot_number = models.CharField(
        max_length=10
    )

    status = models.CharField(
        max_length=20,
        default="available"
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):
        return self.slot_number



# ==========================
# Sensor Data
# ==========================

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


    def __str__(self):

        return f"{self.sensor_type}: {self.value}"



# ==========================
# Booking
# ==========================

class Booking(models.Model):


    STATUS_CHOICES = [

        ("confirmed", "Confirmed"),

        ("cancelled", "Cancelled"),

    ]


    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )


    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.CASCADE
    )


    booking_date = models.DateField()



    start_time = models.TimeField()



    end_time = models.TimeField()



    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed"
    )



    created_at = models.DateTimeField(
        auto_now_add=True
    )



    def __str__(self):

        return (
            f"{self.user.username} - "
            f"{self.parking_slot.slot_number} - "
            f"{self.booking_date}"
        )




# ==========================
# Gate
# ==========================

class Gate(models.Model):


    gate_name = models.CharField(
        max_length=50,
        default="Entrance Gate"
    )


    is_open = models.BooleanField(
        default=False
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )



    def __str__(self):

        return self.gate_name