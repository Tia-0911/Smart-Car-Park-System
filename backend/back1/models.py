from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
        ("backup", "Backup / Admin Reserved"),
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

    # These fields intentionally separate administrative availability,
    # physical occupancy, and booking reservation state. ``status`` remains
    # for compatibility with the existing dashboard and APIs.
    is_enabled = models.BooleanField(
        default=True
    )

    is_physically_occupied = models.BooleanField(
        default=False
    )

    is_under_maintenance = models.BooleanField(
        default=False
    )

    is_backup = models.BooleanField(
        default=False
    )

    is_booking_reserved = models.BooleanField(
        default=False
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

        ('entrance', 'Entrance Vehicle Sensor'),
        ('exit', 'Exit Vehicle Sensor'),
        ('parking', 'Parking Space Sensor'),
        ('emergency', 'Emergency Sensor'),

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


    CONNECTION_STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("error", "Error"),
    ]


    CONDITION_STATUS_CHOICES = [
        ("normal", "Normal"),
        ("abnormal", "Abnormal"),
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


    connection_status = models.CharField(
        max_length=20,
        choices=CONNECTION_STATUS_CHOICES,
        default="online"
    )


    condition_status = models.CharField(
        max_length=20,
        choices=CONDITION_STATUS_CHOICES,
        default="normal"
    )


    last_reading_at = models.DateTimeField(
        default=timezone.now
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


class SensorReadingHistory(models.Model):
    """Append-only audit record for a real sensor report received by Django."""

    sensor_id = models.CharField(max_length=50, db_index=True)
    sensor_type = models.CharField(max_length=20, choices=SensorData.SENSOR_TYPES)
    value = models.CharField(max_length=50)
    condition_status = models.CharField(
        max_length=20,
        choices=SensorData.CONDITION_STATUS_CHOICES,
        default="normal",
    )
    connection_status = models.CharField(
        max_length=20,
        choices=SensorData.CONNECTION_STATUS_CHOICES,
        default="online",
    )
    received_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["received_at", "id"]

    def __str__(self):
        return f"{self.sensor_id} at {self.received_at}"



# ==========================
# Booking
# ==========================

class Booking(models.Model):


    STATUS_CHOICES = [

        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("active", "Active"),
        ("parked", "Parked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("no_show", "No Show"),
        ("overtime", "Overtime"),

    ]


    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("outstanding", "Outstanding"),
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
        default="pending"
    )


    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )


    normal_parking_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )


    overstay_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )


    outstanding_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )


    confirmation_email_sent = models.BooleanField(
        default=False
    )


    reminder_email_sent = models.BooleanField(
        default=False
    )


    overstay_started_at = models.DateTimeField(
        null=True,
        blank=True
    )


    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    entrance_gate_opened_at = models.DateTimeField(null=True, blank=True)
    parking_left_at = models.DateTimeField(null=True, blank=True)
    exit_gate_opened_at = models.DateTimeField(null=True, blank=True)


    created_at = models.DateTimeField(
        auto_now_add=True
    )

    pending_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
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


    PAYMENT_CATEGORY_CHOICES = [
        ("normal", "Normal Parking Payment"),
        ("overstay", "Overstay Payment"),
        ("wallet_top_up", "Wallet Top Up"),
        ("refund", "Refund"),
    ]


    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("outstanding", "Outstanding"),
    ]


    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )


    booking = models.ForeignKey(
        "Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions"
    )


    transaction_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )


    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )


    payment_category = models.CharField(
        max_length=20,
        choices=PAYMENT_CATEGORY_CHOICES,
        default="normal"
    )


    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="paid"
    )


    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):

        return f"{self.user.username} - {self.transaction_type}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking"],
                condition=models.Q(
                    transaction_type="payment",
                    payment_category="normal",
                    payment_status="paid",
                ),
                name="one_paid_normal_transaction_per_booking",
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=models.Q(
                    transaction_type="penalty",
                    payment_category="overstay",
                    payment_status="paid",
                ),
                name="one_paid_overstay_transaction_per_booking",
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=models.Q(
                    transaction_type="refund",
                    payment_category="refund",
                    payment_status="paid",
                ),
                name="one_paid_normal_refund_per_booking",
            ),
        ]


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

    # Confirmed physical state reported by the Raspberry Pi.  This remains
    # independent from is_open, which is the backend's logical/desired state.
    is_physically_open = models.BooleanField(
        null=True,
        blank=True,
        default=None,
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return self.gate_name


class GateCommand(models.Model):
    ACTION_CHOICES = [
        ("open", "Open"),
        ("close", "Close"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("executing", "Executing"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]
    REQUESTED_VIA_CHOICES = [
        ("admin", "Admin"),
        ("customer", "Customer"),
        ("lifecycle", "Lifecycle"),
    ]

    gate = models.ForeignKey(
        Gate,
        on_delete=models.CASCADE,
        related_name="hardware_commands",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gate_commands",
    )
    requested_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_gate_commands",
    )
    requested_via = models.CharField(
        max_length=12,
        choices=REQUESTED_VIA_CHOICES,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["gate", "action"],
                condition=models.Q(status__in=["pending", "executing"]),
                name="one_unresolved_gate_action",
            )
        ]

    def __str__(self):
        return f"{self.gate.gate_type} {self.action} ({self.status})"


# ==========================
# System Event Log
# ==========================

class SystemEvent(models.Model):

    EVENT_TYPES = [
        ("vehicle_detected", "Vehicle Detected"),
        ("gate_opened", "Gate Opened"),
        ("gate_closed", "Gate Closed"),
        ("space_occupied", "Parking Space Occupied"),
        ("space_available", "Parking Space Available"),
        ("sensor_offline", "Sensor Offline"),
        ("sensor_online", "Sensor Online"),
        ("emergency", "Emergency"),
        ("admin_action", "Admin Action"),
        ("payment", "Payment"),
        ("other", "Other"),
    ]

    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPES,
        default="other"
    )

    source = models.CharField(
        max_length=100
    )

    description = models.TextField()

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_events"
    )

    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_events"
    )

    parking_slot = models.ForeignKey(
        ParkingSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_events"
    )

    sensor = models.ForeignKey(
        SensorData,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_events"
    )

    gate = models.ForeignKey(
        Gate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_events"
    )

    def __str__(self):
        return f"{self.timestamp} - {self.event_type}"


# ==========================
# Alert
# ==========================

class Alert(models.Model):

    ALERT_TYPES = [
        ("sensor_abnormal", "Sensor Abnormal"),
        ("sensor_offline", "Sensor Offline"),
        ("emergency", "Emergency"),
        ("other", "Other"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    alert_type = models.CharField(
        max_length=30,
        choices=ALERT_TYPES
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="warning"
    )

    message = models.TextField()

    sensor = models.ForeignKey(
        SensorData,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts"
    )

    acknowledged = models.BooleanField(
        default=False
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True
    )

    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    def __str__(self):
        return f"{self.severity}: {self.message[:50]}"


# ==========================
# Emergency Notification Record
# ==========================

class EmergencyNotification(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    emergency = models.ForeignKey(
        Emergency,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="emergency_notifications"
    )

    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_emergency_notifications"
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return f"{self.emergency} -> {self.recipient}"
