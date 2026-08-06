from django.db import models
from django.contrib.auth.models import User


# ==========================
# Parking Slot
# ==========================

class ParkingSlot(models.Model):

    STATUS_CHOICES = [
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
        ("maintenance", "Maintenance"),
        ("disabled", "Disabled"),
    ]

    slot_number = models.CharField(
        max_length=10,
        unique=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="available"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
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


    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("error", "Error"),
    ]


    sensor_id = models.CharField(
    max_length=50,
    unique=True,
    null=True,
    blank=True
    )


    sensor_type = models.CharField(
        max_length=20,
        choices=SENSOR_TYPES
    )


    location = models.CharField(
        max_length=100,
        blank=True
    )


    value = models.CharField(
        max_length=50
    )


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )


    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return f"{self.sensor_id} - {self.sensor_type}"



# ==========================
# Booking
# ==========================

class Booking(models.Model):


    STATUS_CHOICES = [

        ("confirmed", "Confirmed"),
        ("parked", "Parked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
        ("overtime", "Overtime"),

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


    actual_arrival_time = models.DateTimeField(
        null=True,
        blank=True
    )


    actual_exit_time = models.DateTimeField(
        null=True,
        blank=True
    )


    overtime_minutes = models.IntegerField(
        default=0
    )


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed"
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return (
            f"{self.user.username} - "
            f"{self.parking_slot.slot_number}"
        )



# ==========================
# Wallet
# ==========================

class Wallet(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )


    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return self.user.username



# ==========================
# Transaction
# ==========================

class Transaction(models.Model):

    TYPE_CHOICES = [

        ("payment", "Payment"),
        ("refund", "Refund"),
        ("penalty", "Penalty"),

    ]


    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )


    transaction_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )


    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):

        return f"{self.user.username} - {self.transaction_type}"


# ==========================
# Parking Rate
# ==========================

class ParkingRate(models.Model):

    rate_per_hour = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00
    )

    overtime_rate_per_hour = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):
        return "Parking Rate"
    
# ==========================
# Emergency
# ==========================

class Emergency(models.Model):

    TYPE_CHOICES = [

        ("fire", "Fire"),
        ("sensor_error", "Sensor Error"),
        ("maintenance", "Maintenance"),

    ]


    STATUS_CHOICES = [

        ("active", "Active"),
        ("resolved", "Resolved"),

    ]


    emergency_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES
    )


    description = models.TextField()


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return self.emergency_type



# ==========================
# Gate
# ==========================

class Gate(models.Model):


    GATE_TYPES = [

        ("entrance", "Entrance"),

        ("exit", "Exit"),

    ]


    gate_name = models.CharField(
        max_length=50,
        default="Entrance Gate"
    )


    gate_type = models.CharField(
        max_length=20,
        choices=GATE_TYPES,
        default="entrance"
    )


    is_open = models.BooleanField(
        default=False
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return self.gate_name