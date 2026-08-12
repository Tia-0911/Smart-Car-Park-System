from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Alert, Booking, Emergency, EmergencyNotification, Gate, GateCommand, ParkingRate, ParkingSlot, SensorData, SensorReadingHistory, SystemEvent, Transaction, Wallet

PENDING_HOLD_MINUTES = 15
CAPACITY_STATUSES = ("pending", "confirmed", "active", "parked")
SENSOR_OFFLINE_SECONDS = getattr(settings, "SENSOR_OFFLINE_SECONDS", 30)
LOGICAL_SENSORS = {
    "TEMPERATURE_01": ("temperature", "Environment", None),
    "HUMIDITY_01": ("humidity", "Environment", None),
    "FIRE_01": ("fire", "Safety", None),
    "ENTRANCE_01": ("entrance", "Entrance Gate", None),
    "EXIT_01": ("exit", "Exit Gate", None),
    "EMERGENCY_01": ("emergency", "Emergency", None),
    **{f"PARK_A0{i}": ("parking", f"Parking A0{i}", f"A0{i}") for i in range(1, 7)},
}
MONITORED_SENSOR_IDS = (
    "TEMPERATURE_01", "HUMIDITY_01", "FIRE_01",
    *(f"PARK_A0{i}" for i in range(1, 7)),
    "ENTRANCE_01", "EXIT_01",
)
SENSOR_PRESENTATION = {
    "TEMPERATURE_01": ("Temperature Sensor", "🌡", True),
    "HUMIDITY_01": ("Humidity Sensor", "💧", True),
    "FIRE_01": ("Fire Sensor", "🔥", True),
    "ENTRANCE_01": ("Entrance Sensor", "🚪", False),
    "EXIT_01": ("Exit Sensor", "🚪", False),
    **{f"PARK_A0{i}": (f"PARK_A0{i}", "🚗", False) for i in range(1, 7)},
}
TEMPERATURE_SAFE_MIN = Decimal("0")
TEMPERATURE_SAFE_MAX = Decimal("50")
HUMIDITY_SAFE_MIN = Decimal("20")
HUMIDITY_SAFE_MAX = Decimal("80")


def expire_gate_commands(*, now=None):
    """Make stale device commands permanently non-actionable."""
    now = now or timezone.now()
    return GateCommand.objects.filter(
        status__in=["pending", "executing"],
        expires_at__lte=now,
    ).update(status="expired", completed_at=now)


@transaction.atomic
def create_gate_command(
    *, gate, action, requested_via, booking=None, requested_by_user=None, now=None
):
    """Create one unresolved hardware command per gate/action."""
    now = now or timezone.now()
    expire_gate_commands(now=now)
    existing = GateCommand.objects.select_for_update().filter(
        gate=gate,
        action=action,
        status__in=["pending", "executing"],
        expires_at__gt=now,
    ).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            command = GateCommand.objects.create(
                gate=gate,
                action=action,
                booking=booking,
                requested_by_user=requested_by_user,
                requested_via=requested_via,
                expires_at=now + timedelta(
                    seconds=getattr(settings, "GATE_COMMAND_EXPIRY_SECONDS", 60)
                ),
            )
    except IntegrityError:
        command = GateCommand.objects.get(
            gate=gate,
            action=action,
            status__in=["pending", "executing"],
        )
        return command, False
    return command, True


@transaction.atomic
def claim_gate_command(*, command_id, now=None):
    now = now or timezone.now()
    expire_gate_commands(now=now)
    command = GateCommand.objects.select_for_update().select_related("gate").get(
        pk=command_id
    )
    if command.status != "pending" or command.expires_at <= now:
        raise ValueError("Gate command is not available for claiming.")
    command.status = "executing"
    command.acknowledged_at = now
    command.save(update_fields=["status", "acknowledged_at"])
    return command


@transaction.atomic
def acknowledge_gate_command(*, command_id, result_status, error_message="", now=None):
    now = now or timezone.now()
    command = GateCommand.objects.select_for_update().select_related("gate").get(
        pk=command_id
    )
    if command.status in ["succeeded", "failed"]:
        if command.status == result_status:
            return command, False
        raise ValueError("Gate command already has a different final result.")
    if command.status == "expired" or command.expires_at <= now:
        if command.status != "expired":
            command.status = "expired"
            command.completed_at = now
            command.save(update_fields=["status", "completed_at"])
        raise ValueError("Gate command has expired.")
    if command.status != "executing":
        raise ValueError("Gate command must be claimed before acknowledgement.")
    if result_status not in ["succeeded", "failed"]:
        raise ValueError("Acknowledgement status must be succeeded or failed.")

    command.status = result_status
    command.acknowledged_at = command.acknowledged_at or now
    command.completed_at = now
    command.error_message = str(error_message or "")[:255] if result_status == "failed" else ""
    command.save(update_fields=[
        "status", "acknowledged_at", "completed_at", "error_message"
    ])

    if result_status == "succeeded":
        command.gate.is_physically_open = command.action == "open"
        command.gate.save(update_fields=["is_physically_open", "updated_at"])
        physical_verb = "opened" if command.action == "open" else "closed"
        description = (
            f"Hardware confirmed {command.gate.gate_name} physically "
            f"{physical_verb} for command #{command.id}."
        )
    else:
        detail = f": {command.error_message}" if command.error_message else "."
        description = (
            f"Hardware failed to {command.action} {command.gate.gate_name} "
            f"for command #{command.id}{detail}"
        )
    SystemEvent.objects.create(
        event_type="gate_opened" if result_status == "succeeded" and command.action == "open" else (
            "gate_closed" if result_status == "succeeded" else "other"
        ),
        source="gate_hardware",
        description=description,
        user=command.requested_by_user,
        booking=command.booking,
        parking_slot=command.booking.parking_slot if command.booking else None,
        gate=command.gate,
        timestamp=now,
    )
    return command, True


def usable_parking_spaces(*, lock=False):
    """Return spaces allowed for normal customer bookings.

    Physical occupancy and time-specific Booking rows are deliberately not
    considered here. Those are separate concerns handled by availability.
    """
    queryset = ParkingSlot.objects.filter(
        is_enabled=True,
        is_under_maintenance=False,
        is_backup=False,
    ).order_by("slot_number")
    if lock:
        queryset = queryset.select_for_update()
    return queryset


def expire_stale_pending_bookings(*, now=None):
    now = now or timezone.now()
    return Booking.objects.filter(
        status="pending", payment_status="pending", pending_expires_at__lte=now
    ).update(status="expired")


def overlapping_bookings(booking_date, start_time, end_time):
    expire_stale_pending_bookings()
    return Booking.objects.filter(
        booking_date=booking_date,
        status__in=CAPACITY_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exclude(
        Q(status="pending", pending_expires_at__lte=timezone.now())
    )


def available_parking_spaces(booking_date, start_time, end_time, *, lock=False):
    if not booking_date or not start_time or not end_time or end_time <= start_time:
        return ParkingSlot.objects.none()
    occupied_ids = overlapping_bookings(
        booking_date, start_time, end_time
    ).values_list("parking_slot_id", flat=True)
    return usable_parking_spaces(lock=lock).filter(
        is_physically_occupied=False
    ).exclude(id__in=occupied_ids)


def availability(booking_date, start_time, end_time):
    usable_count = usable_parking_spaces().count()
    available_count = available_parking_spaces(
        booking_date, start_time, end_time
    ).count()
    return {
        "available": available_count > 0,
        "available_space_count": available_count,
        "total_usable_space_count": usable_count,
    }


def booking_duration_hours(start_time, end_time):
    start = datetime.combine(timezone.localdate(), start_time)
    end = datetime.combine(timezone.localdate(), end_time)
    seconds = Decimal(str((end - start).total_seconds()))
    if seconds <= 0:
        raise ValueError("End time must be after start time.")
    return seconds / Decimal("3600")


def calculate_normal_price(start_time, end_time):
    rate = ParkingRate.objects.order_by("id").first()
    if rate is None:
        rate = ParkingRate.objects.create(
            rate_per_hour=Decimal("2.00"),
            overtime_rate_per_hour=Decimal("20.00"),
        )
    return (booking_duration_hours(start_time, end_time) * rate.rate_per_hour).quantize(
        Decimal("0.01")
    )


@transaction.atomic
def create_pending_booking(*, user, booking_date, start_time, end_time):
    # Locking is effective on databases that support SELECT FOR UPDATE. SQLite
    # serializes writes but cannot provide row-level locking.
    assigned = available_parking_spaces(
        booking_date, start_time, end_time, lock=True
    ).first()
    if assigned is None:
        raise ValueError("No parking spaces are available for this time.")
    amount = calculate_normal_price(start_time, end_time)
    return Booking.objects.create(
        user=user,
        parking_slot=assigned,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        status="pending",
        payment_status="pending",
        normal_parking_amount=amount,
        outstanding_balance=amount,
        pending_expires_at=timezone.now() + timedelta(minutes=PENDING_HOLD_MINUTES),
    )


@transaction.atomic
def pay_booking(*, booking_id, user):
    booking = Booking.objects.select_for_update().select_related("parking_slot").get(
        pk=booking_id, user=user
    )
    if booking.payment_status == "paid":
        return booking, False
    if booking.status != "pending" or (
        booking.pending_expires_at and booking.pending_expires_at <= timezone.now()
    ):
        if booking.status == "pending":
            booking.status = "expired"
            booking.save(update_fields=["status", "updated_at"])
        raise ValueError("This pending reservation has expired. Please book again.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    amount = booking.normal_parking_amount
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance.")
    wallet.balance -= amount
    wallet.save(update_fields=["balance", "updated_at"])
    Transaction.objects.create(
        user=user,
        booking=booking,
        transaction_type="payment",
        amount=amount,
        payment_category="normal",
        payment_status="paid",
        paid_at=timezone.now(),
    )
    booking.status = "confirmed"
    booking.payment_status = "paid"
    booking.outstanding_balance = Decimal("0.00")
    booking.save(update_fields=[
        "status", "payment_status", "outstanding_balance", "updated_at"
    ])
    SystemEvent.objects.create(
        event_type="payment", source="booking_payment",
        description=f"Booking #{booking.id} confirmed after payment.",
        user=user, booking=booking, parking_slot=booking.parking_slot,
    )
    return booking, True


def send_booking_confirmation(booking):
    if booking.confirmation_email_sent or not booking.user.email:
        return False
    entrance = datetime.combine(booking.booking_date, booking.start_time) - timedelta(minutes=5)
    try:
        sent = send_mail(
            f"Booking #{booking.id} confirmed",
            (
                f"Your booking #{booking.id} is confirmed.\n"
                f"Date: {booking.booking_date}\n"
                f"Time: {booking.start_time:%H:%M}–{booking.end_time:%H:%M}\n"
                f"Parking space: {booking.parking_slot.slot_number}\n"
                f"Amount paid: £{booking.normal_parking_amount}\n"
                f"Entrance access begins at {entrance:%H:%M} (5 minutes before start time)."
            ),
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@smartcarpark.local"),
            [booking.user.email], fail_silently=False,
        )
    except Exception as exc:
        SystemEvent.objects.create(
            event_type="other", source="booking_email",
            description=f"Confirmation email failed for booking #{booking.id}: {exc}",
            user=booking.user, booking=booking, parking_slot=booking.parking_slot,
        )
        return False
    if sent:
        booking.confirmation_email_sent = True
        booking.save(update_fields=["confirmation_email_sent", "updated_at"])
        SystemEvent.objects.create(
            event_type="other", source="booking_email",
            description=f"Confirmation email sent for booking #{booking.id}.",
            user=booking.user, booking=booking, parking_slot=booking.parking_slot,
        )
        return True
    return False


def sensor_is_detected(sensor):
    return str(sensor.value).strip().lower() in {
        "1", "true", "detected", "occupied", "emergency", "active",
        "fire", "fire detected",
    }


def sensor_is_online(sensor, *, now=None):
    now = now or timezone.now()
    return (now - sensor.last_reading_at).total_seconds() <= SENSOR_OFFLINE_SECONDS


def _numeric_sensor_is_abnormal(sensor_type, value):
    try:
        numeric = Decimal(str(value))
    except Exception:
        return True
    if sensor_type == "temperature":
        return not (TEMPERATURE_SAFE_MIN <= numeric <= TEMPERATURE_SAFE_MAX)
    if sensor_type == "humidity":
        return not (HUMIDITY_SAFE_MIN <= numeric <= HUMIDITY_SAFE_MAX)
    return False


def sensor_condition_is_abnormal(sensor):
    if sensor.condition_status == "abnormal":
        return True
    if sensor.sensor_type in {"temperature", "humidity"}:
        return _numeric_sensor_is_abnormal(sensor.sensor_type, sensor.value)
    if sensor.sensor_type in {"fire", "emergency"}:
        return sensor_is_detected(sensor)
    return False


def monitored_sensor_status(*, now=None):
    """Return one presentation row per required device using shared health logic."""
    now = now or timezone.now()
    sensors = {
        sensor.sensor_id: sensor
        for sensor in SensorData.objects.filter(sensor_id__in=MONITORED_SENSOR_IDS)
    }
    rows = []
    for sensor_id in MONITORED_SENSOR_IDS:
        name, icon, show_value = SENSOR_PRESENTATION[sensor_id]
        sensor = sensors.get(sensor_id)
        online = bool(sensor and sensor_is_online(sensor, now=now))
        abnormal = bool(sensor and sensor_condition_is_abnormal(sensor))
        failed = not online or bool(sensor and sensor.connection_status == "error")
        if failed:
            health_label = "FAILED / OFFLINE"
        elif abnormal:
            health_label = "UNSAFE / DANGER"
        else:
            health_label = "SAFE" if show_value else "NORMAL"

        value_display = None
        if sensor and show_value:
            if sensor.sensor_type == "temperature":
                value_display = f"{sensor.value}°C"
            elif sensor.sensor_type == "humidity":
                value_display = f"{sensor.value}%"
            elif sensor.sensor_type == "fire":
                value_display = "Fire Detected" if sensor_is_detected(sensor) else "Normal"

        issue = None
        if failed:
            issue = f"{icon} {name} — Sensor Failed"
        elif abnormal:
            if sensor.sensor_type == "temperature":
                issue = f"{icon} {name} — Unsafe: {value_display}"
            elif sensor.sensor_type == "humidity":
                issue = f"{icon} {name} — Unsafe: {value_display}"
            elif sensor.sensor_type == "fire":
                issue = f"{icon} {name} — Fire Detected"
            else:
                issue = f"{icon} {name} — Unsafe / Danger"

        rows.append({
            "sensor_id": sensor_id,
            "name": name,
            "icon": icon,
            "show_value": show_value,
            "value_display": value_display,
            "last_update": sensor.last_reading_at if sensor else None,
            "online": online,
            "abnormal": abnormal,
            "failed": failed,
            "health_label": health_label,
            "issue": issue,
            "sensor_type": sensor.sensor_type if sensor else LOGICAL_SENSORS[sensor_id][0],
        })
    return rows


def booking_bounds(booking):
    start = timezone.make_aware(datetime.combine(booking.booking_date, booking.start_time))
    end = timezone.make_aware(datetime.combine(booking.booking_date, booking.end_time))
    return start, end


def booking_range_has_ended(booking_date, end_time, *, now=None):
    now = now or timezone.now()
    end = timezone.make_aware(datetime.combine(booking_date, end_time))
    return end <= now


def cancellation_quote(booking, *, now=None):
    now = now or timezone.now()
    start, _ = booking_bounds(booking)
    pending_still_valid = (
        booking.status != "pending"
        or booking.pending_expires_at is None
        or booking.pending_expires_at > now
    )
    can_cancel = (
        booking.status == "pending"
        and booking.payment_status == "pending"
        and pending_still_valid
    ) or (
        booking.status == "confirmed"
        and booking.payment_status == "paid"
        and now < start
    )
    refundable = (
        can_cancel
        and booking.status == "confirmed"
        and now <= start - timedelta(hours=24)
    )
    return {
        "can_cancel": can_cancel,
        "refundable": refundable,
        "refund_amount": booking.normal_parking_amount if refundable else Decimal("0.00"),
    }


@transaction.atomic
def cancel_customer_booking(*, booking_id, user, now=None):
    now = now or timezone.now()
    booking = Booking.objects.select_for_update().select_related("parking_slot").get(
        pk=booking_id, user=user
    )
    existing_refund = Transaction.objects.filter(
        booking=booking,
        transaction_type="refund",
        payment_category="refund",
        payment_status="paid",
    ).first()
    if booking.status == "cancelled":
        return booking, existing_refund, False

    quote = cancellation_quote(booking, now=now)
    if not quote["can_cancel"]:
        raise ValueError("This booking can no longer be cancelled.")

    refund = None
    if quote["refundable"]:
        normal_payment = Transaction.objects.filter(
            booking=booking,
            transaction_type="payment",
            payment_category="normal",
            payment_status="paid",
        ).order_by("paid_at", "id").first()
        if normal_payment is None:
            raise ValueError("The original normal parking payment could not be verified.")
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        wallet.balance += normal_payment.amount
        wallet.save(update_fields=["balance", "updated_at"])
        refund = Transaction.objects.create(
            user=user,
            booking=booking,
            transaction_type="refund",
            amount=normal_payment.amount,
            payment_category="refund",
            payment_status="paid",
            paid_at=now,
        )

    booking.status = "cancelled"
    booking.save(update_fields=["status", "updated_at"])
    SystemEvent.objects.create(
        event_type="other",
        source="booking_cancellation",
        description=(
            f"Booking #{booking.id} cancelled with a full refund of £{refund.amount}."
            if refund else f"Booking #{booking.id} cancelled without refund."
        ),
        user=user,
        booking=booking,
        parking_slot=booking.parking_slot,
    )
    return booking, refund, True


def entrance_access_allowed(booking, *, now=None):
    now = now or timezone.now()
    start, end = booking_bounds(booking)
    return start - timedelta(minutes=5) <= now <= end


def _event(
    description, *, event_type="other", sensor=None, booking=None, slot=None,
    gate=None, source="device_sensor", user=None, timestamp=None,
):
    return SystemEvent.objects.create(
        event_type=event_type, source=source, description=description,
        sensor=sensor, booking=booking, parking_slot=slot,
        gate=gate, timestamp=timestamp or timezone.now(),
        user=user or (booking.user if booking else None),
    )


@transaction.atomic
def update_logical_sensor(*, sensor_id, value, condition_status=None, now=None):
    if sensor_id not in LOGICAL_SENSORS:
        raise ValueError("Unknown sensor identifier.")
    now = now or timezone.now()
    sensor_type, location, slot_number = LOGICAL_SENSORS[sensor_id]
    slot = ParkingSlot.objects.get(slot_number=slot_number) if slot_number else None
    sensor, _ = SensorData.objects.select_for_update().get_or_create(
        sensor_id=sensor_id,
        defaults={"sensor_type": sensor_type, "location": location, "parking_slot": slot, "value": "clear"},
    )
    previous = sensor_is_detected(sensor)
    previous_abnormal = sensor_condition_is_abnormal(sensor)
    if sensor_type in {"temperature", "humidity"}:
        try:
            Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"{sensor_type.title()} value must be numeric.") from exc
        normalized = str(value).strip()
    else:
        normalized = "detected" if str(value).strip().lower() in {
            "1", "true", "detected", "occupied", "emergency", "active",
            "fire", "fire detected",
        } else "clear"
    current = normalized == "detected"
    sensor.sensor_type = sensor_type
    sensor.location = location
    sensor.parking_slot = slot
    sensor.value = normalized
    sensor.status = "active"
    sensor.connection_status = "online"
    if condition_status in {"normal", "abnormal"}:
        sensor.condition_status = condition_status
    elif sensor_type in {"temperature", "humidity"}:
        sensor.condition_status = "abnormal" if _numeric_sensor_is_abnormal(sensor_type, normalized) else "normal"
    elif sensor_type in {"fire", "emergency"}:
        sensor.condition_status = "abnormal" if current else "normal"
    else:
        sensor.condition_status = "normal"
    sensor.last_reading_at = now
    sensor.save()
    SensorReadingHistory.objects.create(
        sensor_id=sensor.sensor_id,
        sensor_type=sensor.sensor_type,
        value=sensor.value,
        condition_status=sensor.condition_status,
        connection_status=sensor.connection_status,
        received_at=now,
    )
    sync_sensor_alerts(sensor, now=now)

    # Reconcile the denormalized physical flag on every parking-sensor
    # reading. This repairs stale/inconsistent slot state even when a device
    # repeats the same value, while events remain transition-only below.
    if sensor_type == "parking" and slot.is_physically_occupied != current:
        slot.is_physically_occupied = current
        if current:
            slot.status = "occupied"
        elif not slot.is_enabled:
            slot.status = "disabled"
        elif slot.is_under_maintenance:
            slot.status = "maintenance"
        elif slot.is_backup:
            slot.status = "backup"
        else:
            slot.status = "reserved" if slot.is_booking_reserved else "available"
        slot.save(update_fields=["is_physically_occupied", "status", "updated_at"])

    if previous == current:
        return sensor, False

    if sensor_type == "entrance":
        _event(
            "Vehicle arrived at Entrance." if current else "Vehicle cleared Entrance.",
            event_type="vehicle_detected", sensor=sensor,
            source="entrance_sensor", timestamp=now,
        )
        if not current:
            gate = Gate.objects.filter(gate_type="entrance").first()
            booking = Booking.objects.filter(
                entrance_gate_opened_at__isnull=False,
                status__in=["confirmed", "active"],
            ).order_by("-entrance_gate_opened_at").first()
            if gate and gate.is_open:
                gate.is_open = False; gate.save(update_fields=["is_open", "updated_at"])
                create_gate_command(
                    gate=gate,
                    action="close",
                    requested_via="lifecycle",
                    booking=booking,
                    now=now,
                )
                _event(
                    "Entrance Gate closed after vehicle passage.",
                    event_type="gate_closed", sensor=sensor, booking=booking,
                    slot=booking.parking_slot if booking else None, gate=gate,
                    source="gate_lifecycle", timestamp=now,
                )
    elif sensor_type == "exit":
        _event(
            "Vehicle arrived at Exit." if current else "Vehicle cleared Exit.",
            event_type="vehicle_detected", sensor=sensor,
            source="exit_sensor", timestamp=now,
        )
        if not current:
            gate = Gate.objects.filter(gate_type="exit").first()
            booking = Booking.objects.filter(
                exit_gate_opened_at__isnull=False, status__in=["active", "parked", "overtime"]
            ).order_by("-exit_gate_opened_at").first()
            if gate and gate.is_open:
                gate.is_open = False; gate.save(update_fields=["is_open", "updated_at"])
                create_gate_command(
                    gate=gate,
                    action="close",
                    requested_via="lifecycle",
                    booking=booking,
                    now=now,
                )
                _event(
                    "Exit Gate closed after vehicle passage.",
                    event_type="gate_closed", sensor=sensor, booking=booking,
                    slot=booking.parking_slot if booking else None, gate=gate,
                    source="gate_lifecycle", timestamp=now,
                )
            if booking:
                booking.status = "completed"; booking.completed_at = now; booking.actual_exit_time = now
                booking.save(update_fields=["status", "completed_at", "actual_exit_time", "updated_at"])
                _event(
                    f"Vehicle exited the car park and Booking #{booking.id} was completed.",
                    sensor=sensor, booking=booking, slot=booking.parking_slot,
                    source="booking_lifecycle", timestamp=now,
                )
    elif sensor_type == "parking":
        slot.is_physically_occupied = current
        slot.status = "occupied" if current else ("reserved" if slot.is_booking_reserved else "available")
        slot.save(update_fields=["is_physically_occupied", "status", "updated_at"])
        booking = Booking.objects.filter(
            parking_slot=slot, booking_date=timezone.localdate(now), status__in=["confirmed", "active", "parked", "overtime"]
        ).order_by("start_time").first()
        _event(
            f"Vehicle occupied {slot.slot_number}." if current else f"Vehicle left {slot.slot_number}.",
            event_type="space_occupied" if current else "space_available",
            sensor=sensor, booking=booking, slot=slot,
            source="parking_sensor", timestamp=now,
        )
        if current and booking and booking.status == "confirmed":
            booking.status = "active"; booking.actual_arrival_time = booking.actual_arrival_time or now
            booking.save(update_fields=["status", "actual_arrival_time", "updated_at"])
        elif not current and booking:
            booking.parking_left_at = now
            booking.save(update_fields=["parking_left_at", "updated_at"])
            finalize_overstay(booking, now=now)
    elif sensor_type == "emergency":
        _event("Emergency sensor activated." if current else "Emergency sensor returned to normal.", sensor=sensor)
        if current:
            Emergency.objects.get_or_create(
                emergency_type="sensor_error", status="active",
                defaults={"description": "Emergency sensor EMERGENCY_01 activated."},
            )
    elif sensor_type == "fire" and previous != current:
        _event("Fire detected." if current else "Fire sensor returned to normal.", sensor=sensor, source="sensor_safety")
    elif sensor_type in {"temperature", "humidity"} and previous_abnormal != sensor_condition_is_abnormal(sensor):
        state = "unsafe" if sensor_condition_is_abnormal(sensor) else "safe"
        _event(f"{sensor.location} {sensor_type} sensor became {state}.", sensor=sensor, source="sensor_environment")
    return sensor, True


def sync_sensor_alerts(sensor, *, now=None):
    now = now or timezone.now()
    conditions = []
    if not sensor_is_online(sensor, now=now):
        conditions.append(("sensor_offline", "warning", f"{sensor.sensor_id} is offline."))
    if sensor.connection_status == "error":
        conditions.append(("sensor_abnormal", "warning", f"{sensor.sensor_id} reported a connection error."))
    if sensor_condition_is_abnormal(sensor):
        severity = "critical" if sensor.sensor_type in {"emergency", "fire"} else "warning"
        alert_type = "emergency" if sensor.sensor_type in {"emergency", "fire"} else "sensor_abnormal"
        conditions.append((alert_type, severity, f"{sensor.sensor_id} is abnormal."))
    active_types = {kind for kind, _, _ in conditions}
    for kind, severity, message in conditions:
        alert, created = Alert.objects.get_or_create(
            sensor=sensor, alert_type=kind, acknowledged=False,
            defaults={"severity": severity, "message": message},
        )
        if created:
            _event(message, sensor=sensor, source="sensor_alert")
    recovered = Alert.objects.filter(sensor=sensor, acknowledged=False).exclude(alert_type__in=active_types)
    for alert in recovered:
        alert.acknowledged = True; alert.acknowledged_at = now
        alert.save(update_fields=["acknowledged", "acknowledged_at"])
        _event(f"{sensor.sensor_id} recovered from {alert.get_alert_type_display()}.", sensor=sensor, source="sensor_recovery")
    return Alert.objects.filter(sensor=sensor, acknowledged=False)


def process_sensor_alerts(*, now=None):
    now = now or timezone.now()
    for sensor in SensorData.objects.all():
        sync_sensor_alerts(sensor, now=now)


def send_emergency_notifications(*, emergency, admin, message):
    now = timezone.now()
    recipients = User.objects.filter(
        is_staff=False, is_active=True,
    ).filter(
        Q(booking__status__in=["active", "parked", "overtime"])
        | Q(
            booking__status="confirmed",
            booking__booking_date=timezone.localdate(now),
            booking__start_time__lte=timezone.localtime(now).time(),
            booking__end_time__gte=timezone.localtime(now).time(),
        )
    ).distinct()
    results = []
    for recipient in recipients:
        notification = EmergencyNotification.objects.create(
            emergency=emergency, recipient=recipient, sent_by=admin,
            message=message, status="pending",
        )
        try:
            sent = send_mail(
                "Smart Car Park Emergency Notice", message,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@smartcarpark.local"),
                [recipient.email], fail_silently=False,
            )
        except Exception:
            sent = 0
        notification.status = "sent" if sent else "failed"
        notification.sent_at = now if sent else None
        notification.save(update_fields=["status", "sent_at"])
        results.append(notification)
    _event(f"Admin sent emergency notification for incident #{emergency.id}.", source="emergency_notification", user=admin)
    return results


@transaction.atomic
def request_customer_gate(*, booking_id, user, gate_type, now=None):
    now = now or timezone.now()
    booking = Booking.objects.select_for_update().select_related("parking_slot").get(pk=booking_id, user=user)
    sensor_id = "ENTRANCE_01" if gate_type == "entrance" else "EXIT_01"
    sensor = SensorData.objects.filter(sensor_id=sensor_id).first()
    if gate_type == "entrance":
        if booking.status not in ["confirmed", "active"]:
            raise ValueError("No valid confirmed booking found.")
        if not entrance_access_allowed(booking, now=now):
            raise ValueError("Gate access is available from 5 minutes before your booking.")
        if not sensor or not sensor_is_detected(sensor):
            raise ValueError("No vehicle detected at the entrance.")
    else:
        if booking.status not in ["active", "parked", "overtime"]:
            raise ValueError("This parking session is not eligible for exit.")
        if not sensor or not sensor_is_detected(sensor):
            raise ValueError("No vehicle detected at the exit.")
        finalize_overstay(booking, now=booking.parking_left_at or now)
        booking.refresh_from_db()
        if booking.outstanding_balance > 0:
            raise ValueError("Outstanding payment must be paid before exit.")
    gate = Gate.objects.select_for_update().get(gate_type=gate_type)
    if gate.is_open:
        return booking, gate, False
    gate.is_open = True; gate.save(update_fields=["is_open", "updated_at"])
    field = "entrance_gate_opened_at" if gate_type == "entrance" else "exit_gate_opened_at"
    setattr(booking, field, now); booking.save(update_fields=[field, "updated_at"])
    create_gate_command(
        gate=gate,
        action="open",
        requested_via="customer",
        booking=booking,
        requested_by_user=user,
        now=now,
    )
    _event(
        f"Customer opened {gate.get_gate_type_display()} Gate for Booking #{booking.id}.",
        event_type="gate_opened", booking=booking, slot=booking.parking_slot,
        gate=gate, source="customer_gate", timestamp=now,
    )
    return booking, gate, True


def process_booking_reminders(*, now=None):
    now = now or timezone.now()
    sent_count = 0
    for booking in Booking.objects.select_related("user", "parking_slot").filter(
        status__in=["confirmed", "active"], reminder_email_sent=False
    ):
        _, end = booking_bounds(booking)
        if not (end - timedelta(minutes=15) <= now < end):
            continue
        try:
            sent = send_mail(
                f"Booking #{booking.id} ends soon",
                f"Booking #{booking.id} in {booking.parking_slot.slot_number} ends at {booking.end_time:%H:%M}. Please remove your vehicle. Overstay is charged at £20/hour.",
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@smartcarpark.local"), [booking.user.email], fail_silently=False,
            )
        except Exception:
            continue
        if sent:
            booking.reminder_email_sent = True; booking.save(update_fields=["reminder_email_sent", "updated_at"])
            _event(f"15-minute reminder email sent for Booking #{booking.id}.", booking=booking, slot=booking.parking_slot, source="booking_reminder")
            sent_count += 1
    return sent_count


def finalize_overstay(booking, *, now=None):
    now = now or timezone.now()
    _, end = booking_bounds(booking)
    if now <= end or not booking.parking_slot.is_physically_occupied and not booking.parking_left_at:
        return Decimal("0.00")
    rate = ParkingRate.objects.order_by("id").first().overtime_rate_per_hour
    elapsed_seconds = max(0, Decimal(str((now - end).total_seconds())))
    minutes = int(elapsed_seconds // Decimal("60"))
    started_hours = int(
        (elapsed_seconds / Decimal("3600")).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    amount = (Decimal(started_hours) * rate).quantize(Decimal("0.01"))
    first = booking.overstay_started_at is None and amount > 0
    booking.overstay_started_at = booking.overstay_started_at or end
    booking.overtime_minutes = minutes
    booking.overstay_amount = amount
    overstay_paid = Transaction.objects.filter(
        booking=booking,
        transaction_type="penalty",
        payment_category="overstay",
        payment_status="paid",
    ).exists()
    booking.outstanding_balance = Decimal("0.00") if overstay_paid else amount
    if amount > 0:
        booking.status = "overtime"
        booking.payment_status = "paid" if overstay_paid else "outstanding"
    booking.save(update_fields=["overstay_started_at", "overtime_minutes", "overstay_amount", "outstanding_balance", "status", "payment_status", "updated_at"])
    if first:
        _event(f"Overstay started for Booking #{booking.id}.", booking=booking, slot=booking.parking_slot, source="overstay")
    return amount


def process_overstays(*, now=None):
    now = now or timezone.now()
    count = 0
    for booking in Booking.objects.select_related("parking_slot").filter(
        status__in=["active", "parked", "overtime"], parking_slot__is_physically_occupied=True
    ):
        _, end = booking_bounds(booking)
        if now > end:
            finalize_overstay(booking, now=now)
            count += 1
    return count


@transaction.atomic
def pay_overstay(*, booking_id, user):
    booking = Booking.objects.select_for_update().get(pk=booking_id, user=user)
    existing = Transaction.objects.filter(booking=booking, transaction_type="penalty", payment_category="overstay", payment_status="paid").exists()
    if existing or booking.outstanding_balance == 0:
        return booking, False
    amount = booking.outstanding_balance
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance.")
    wallet.balance -= amount; wallet.save(update_fields=["balance", "updated_at"])
    Transaction.objects.create(user=user, booking=booking, transaction_type="penalty", amount=amount, payment_category="overstay", payment_status="paid", paid_at=timezone.now())
    booking.outstanding_balance = Decimal("0.00"); booking.payment_status = "paid"
    booking.save(update_fields=["outstanding_balance", "payment_status", "updated_at"])
    _event(f"Overstay payment completed for Booking #{booking.id}.", booking=booking, slot=booking.parking_slot, source="overstay_payment")
    return booking, True
