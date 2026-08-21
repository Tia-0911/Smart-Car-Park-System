# ==========================
# IMPORTS
# ==========================

from decimal import Decimal
from datetime import time, timedelta
import secrets
import re
from django.conf import settings
from django.db.models import Count, Max, Q, Sum
from django.core.paginator import Paginator

from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseNotAllowed
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views import View
from django.views.generic import ListView
from django.urls import reverse, reverse_lazy


from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status




from .models import (
    ParkingSlot,
    SensorData,
    SensorReadingHistory,
    Booking,
    Gate,
    GateCommand,
    Wallet,
    Transaction,
    Emergency,
    SystemEvent,
    ParkingRate,
    Alert,
    ParkingLED,
    LEDCommand,
    EmergencyNotification,
)


from .serializers import (
    ParkingSlotSerializer,
    BookingSerializer,
    GateSerializer,
    SensorDataSerializer,
    WalletSerializer,
    TransactionSerializer,
    EmergencySerializer
)

from .forms import (
    BookingForm,
    AdminBookingForm,
    AdminCustomerForm,
    CustomerProfileForm,
    CustomerRegistrationForm,
)
from .services import (
    CAPACITY_STATUSES,
    MONITORED_SENSOR_IDS,
    SENSOR_PRESENTATION,
    availability,
    available_parking_spaces,
    booking_bounds,
    create_pending_booking,
    expire_stale_pending_bookings,
    pay_booking,
    send_booking_confirmation,
    pay_overstay,
    request_customer_gate,
    sensor_is_detected,
    sensor_is_online,
    monitored_sensor_status,
    update_logical_sensor,
    process_sensor_alerts,
    send_emergency_notifications,
    usable_parking_spaces,
    cancellation_quote,
    cancel_customer_booking,
    booking_range_has_ended,
    acknowledge_gate_command,
    claim_gate_command,
    create_gate_command,
    expire_gate_commands,
)


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _require_admin(request):
    if not _is_admin(request.user):
        raise PermissionDenied


def _require_customer(request):
    if _is_admin(request.user):
        return redirect("back1:admin-dashboard")
    return None


def _device_api_key_is_valid(request):
    supplied = request.headers.get("X-Device-API-Key", "")
    expected = settings.SENSOR_DEVICE_API_KEY
    return bool(
        supplied and expected and secrets.compare_digest(supplied, expected)
    )


def _viewing_date_context(request):
    today = timezone.localdate()
    selected = parse_date(request.GET.get("date", "")) or today
    return {
        "viewing_date": selected,
        "viewing_previous_date": selected - timedelta(days=1),
        "viewing_next_date": selected + timedelta(days=1),
        "viewing_is_today": selected == today,
    }


def _daily_revenue(selected_date):
    parking_transactions = Transaction.objects.filter(
        transaction_type="payment",
        payment_category="normal",
        payment_status="paid",
        paid_at__date=selected_date,
    )
    penalty_transactions = Transaction.objects.filter(
        transaction_type="penalty",
        payment_category="overstay",
        payment_status="paid",
        paid_at__date=selected_date,
    )
    parking_revenue = parking_transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    penalty_revenue = penalty_transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return {
        "parking_transactions": parking_transactions,
        "penalty_transactions": penalty_transactions,
        "parking_revenue": parking_revenue,
        "penalty_revenue": penalty_revenue,
        "total_revenue": parking_revenue + penalty_revenue,
    }


def _get_authorized_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return None

    if not _is_admin(request.user) and booking.user_id != request.user.id:
        raise PermissionDenied
    return booking


class RoleAwareLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        if _is_admin(self.request.user):
            return reverse("back1:admin-dashboard")
        return reverse("back1:customer-dashboard")


def root_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if _is_admin(request.user):
        return redirect("back1:admin-dashboard")
    return redirect("back1:customer-dashboard")


def register(request):
    if request.user.is_authenticated:
        return root_redirect(request)

    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your customer account has been created.")
            return redirect("back1:customer-dashboard")
    else:
        form = CustomerRegistrationForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def customer_dashboard(request):
    admin_redirect = _require_customer(request)
    if admin_redirect:
        return admin_redirect

    expire_stale_pending_bookings()
    upcoming_booking = Booking.objects.filter(
        user=request.user,
        status__in=["pending", "confirmed", "active", "parked", "overtime"],
        booking_date__gte=timezone.localdate(),
    ).order_by("booking_date", "start_time").first()

    entrance_available_from = None
    ending_soon = False
    if upcoming_booking:
        start_dt, end_dt = booking_bounds(upcoming_booking)
        entrance_available_from = start_dt - timedelta(minutes=5)
        ending_soon = end_dt - timedelta(minutes=15) <= timezone.now() < end_dt

    return render(
        request,
        "back1/customer_dashboard.html",
        {"upcoming_booking": upcoming_booking, "entrance_available_from": entrance_available_from, "ending_soon": ending_soon},
    )


@login_required
def profile(request):
    admin_redirect = _require_customer(request)
    if admin_redirect:
        return admin_redirect

    if request.method == "POST":
        form = CustomerProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("back1:profile")
    else:
        form = CustomerProfileForm(instance=request.user)

    return render(request, "back1/profile.html", {"form": form})


@login_required
def my_bookings(request):
    admin_redirect = _require_customer(request)
    if admin_redirect:
        return admin_redirect

    expire_stale_pending_bookings()
    bookings = list(Booking.objects.filter(user=request.user).select_related(
        "parking_slot"
    ).order_by("-booking_date", "-start_time"))

    for booking in bookings:
        quote = cancellation_quote(booking)
        booking.can_customer_cancel = quote["can_cancel"]
        booking.refund_eligible = quote["refundable"]
        if booking.status == "pending":
            booking.cancellation_message = "Cancel this unpaid booking? No refund is needed because it has not been paid."
        elif quote["refundable"]:
            booking.cancellation_message = f"Cancel this booking? You are eligible for a full refund of £{quote['refund_amount']}."
        else:
            booking.cancellation_message = "Cancel this booking? This booking is within 24 hours of the start time and is non-refundable."

    today = timezone.localdate()
    context = {
        "upcoming_bookings": [b for b in bookings if b.booking_date >= today and b.status in ["pending", "confirmed"]],
        "active_bookings": [b for b in bookings if b.status in ["active", "parked"]],
        "past_bookings": [b for b in bookings if b.status in ["completed", "expired", "no_show", "overtime"]],
        "cancelled_bookings": [b for b in bookings if b.status == "cancelled"],
    }
    return render(request, "back1/my_bookings.html", context)


@login_required
def admin_bookings(request):
    _require_admin(request)
    date_context = _viewing_date_context(request)
    queryset = Booking.objects.filter(booking_date=date_context["viewing_date"]).select_related("user", "parking_slot").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(Q(user__username__icontains=query) | Q(user__email__icontains=query))
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    return render(request, "back1/admin_bookings.html", {"bookings": queryset[:100], "status_choices": Booking.STATUS_CHOICES, **date_context})


@login_required
def admin_booking_edit(request, booking_id):
    _require_admin(request)
    booking = get_object_or_404(Booking, pk=booking_id)
    form = AdminBookingForm(request.POST or None, instance=booking)
    if request.method == "POST" and form.is_valid():
        form.save()
        SystemEvent.objects.create(event_type="admin_action", source="admin_booking", description=f"Admin edited Booking #{booking.id}.", user=request.user, booking=booking, parking_slot=booking.parking_slot)
        messages.success(request, "Booking updated.")
        return redirect("back1:admin-bookings")
    return render(request, "back1/admin_form.html", {"title": f"Edit Booking #{booking.id}", "form": form, "object": booking})


@login_required
def admin_booking_delete(request, booking_id):
    _require_admin(request)
    booking = get_object_or_404(Booking, pk=booking_id)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    has_history = booking.transactions.exists() or booking.system_events.exists()
    if has_history:
        booking.status = "cancelled"; booking.save(update_fields=["status", "updated_at"])
        description = f"Admin cancelled Booking #{booking.id}; history preserved."
    else:
        description = f"Admin deleted Booking #{booking.id}."
        booking.delete()
        booking = None
    SystemEvent.objects.create(event_type="admin_action", source="admin_booking", description=description, user=request.user, booking=booking)
    return redirect("back1:admin-bookings")


@login_required
def admin_customers(request):
    _require_admin(request)
    customers = User.objects.filter(is_staff=False, is_superuser=False).annotate(booking_count=Count("booking")).order_by("username")
    return render(request, "back1/admin_customers.html", {"customers": customers})


@login_required
def admin_customer_edit(request, user_id):
    _require_admin(request)
    customer = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    form = AdminCustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        SystemEvent.objects.create(event_type="admin_action", source="admin_customer", description=f"Admin updated customer account #{customer.id}.", user=request.user)
        return redirect("back1:admin-customers")
    return render(request, "back1/admin_form.html", {"title": f"Edit Customer {customer.username}", "form": form, "object": customer})


@login_required
def admin_customer_delete(request, user_id):
    _require_admin(request)
    customer = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if customer.booking_set.exists() or Transaction.objects.filter(user=customer).exists():
        customer.is_active = False; customer.save(update_fields=["is_active"])
        action = "deactivated"
    else:
        customer.delete(); action = "deleted"
    SystemEvent.objects.create(event_type="admin_action", source="admin_customer", description=f"Admin {action} customer account #{user_id}.", user=request.user)
    return redirect("back1:admin-customers")


@login_required
def admin_events(request):
    _require_admin(request)
    date_context = _viewing_date_context(request)
    query = request.GET.get("q", "").strip()
    selected_type = request.GET.get("type", "")
    selected_source = request.GET.get("source", "")

    type_filters = {
        "vehicle": Q(event_type="vehicle_detected") | Q(source="booking_lifecycle") | Q(source="device_sensor", sensor__sensor_type__in=["entrance", "exit"]),
        "gate": Q(event_type__in=["gate_opened", "gate_closed"]) | Q(source__in=["customer_gate", "admin_gate", "gate_lifecycle"]),
        "parking": Q(event_type__in=["space_occupied", "space_available"]) | Q(source="parking_sensor") | Q(source="device_sensor", sensor__sensor_type="parking"),
        "booking": Q(source__in=["booking_email", "booking_cancellation", "booking_reminder", "admin_booking"]),
        "payment": Q(event_type="payment") | Q(source__in=["booking_payment", "overstay_payment", "overstay"]) | Q(description__icontains="refund"),
        "emergency": Q(event_type="emergency") | Q(source__in=["admin_emergency", "emergency_notification"]),
        "sensor": Q(event_type__in=["sensor_offline", "sensor_online"]) | Q(source__in=["sensor_alert", "sensor_environment", "sensor_recovery", "sensor_safety"]),
    }
    source_filters = {
        "entrance_sensor": Q(source="entrance_sensor"),
        "exit_sensor": Q(source="exit_sensor"),
        "parking_sensor": Q(source="parking_sensor"),
        "customer_gate": Q(source="customer_gate"),
        "admin_gate": Q(source="admin_gate"),
        "gate_lifecycle": Q(source="gate_lifecycle"),
        "booking_system": Q(source__in=["booking_email", "booking_cancellation", "booking_reminder", "admin_booking", "booking_lifecycle"]),
        "payment_system": Q(source__in=["booking_payment", "overstay_payment", "overstay"]) | Q(event_type="payment"),
        "emergency_system": Q(source__in=["admin_emergency", "emergency_notification"]) | Q(event_type="emergency"),
        "sensor_system": Q(source__in=["sensor_alert", "sensor_environment", "sensor_recovery", "sensor_safety", "device_sensor"]),
    }
    if selected_type not in type_filters:
        selected_type = ""
    if selected_source not in source_filters:
        selected_source = ""

    daily_events = SystemEvent.objects.filter(timestamp__date=date_context["viewing_date"])
    has_events_for_date = daily_events.exists()
    if query:
        search_filter = (
            Q(description__icontains=query)
            | Q(booking__user__username__icontains=query)
            | Q(booking__user__email__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )
        booking_match = re.search(r"(?:booking\s*#?\s*)?(\d+)$", query, re.IGNORECASE)
        if booking_match:
            search_filter |= Q(booking_id=int(booking_match.group(1)))
        daily_events = daily_events.filter(search_filter)
    if selected_type:
        daily_events = daily_events.filter(type_filters[selected_type])
    if selected_source:
        daily_events = daily_events.filter(source_filters[selected_source])

    page = Paginator(
        daily_events.select_related("booking__user", "user", "parking_slot", "sensor", "gate").order_by("-timestamp"),
        50,
    ).get_page(request.GET.get("page"))
    return render(request, "back1/admin_events.html", {
        "page_obj": page,
        "event_query": query,
        "selected_event_type": selected_type,
        "selected_event_source": selected_source,
        "has_events_for_date": has_events_for_date,
        "event_type_choices": [
            ("vehicle", "Vehicle"), ("gate", "Gate"), ("parking", "Parking"),
            ("booking", "Booking"), ("payment", "Payment"),
            ("emergency", "Emergency"), ("sensor", "Sensor"),
        ],
        "event_source_choices": [
            ("entrance_sensor", "Entrance Sensor"), ("exit_sensor", "Exit Sensor"),
            ("parking_sensor", "Parking Sensor"), ("customer_gate", "Customer Gate"),
            ("admin_gate", "Admin Gate"), ("gate_lifecycle", "Gate Lifecycle"),
            ("booking_system", "Booking System"), ("payment_system", "Payment System"),
            ("emergency_system", "Emergency System"), ("sensor_system", "Sensor System"),
        ],
        **date_context,
    })


@login_required
def admin_alerts(request):
    _require_admin(request)
    alerts = Alert.objects.select_related("sensor", "acknowledged_by").order_by("acknowledged", "-created_at")
    return render(request, "back1/admin_alerts.html", {"alerts": alerts})


@login_required
def admin_sensors(request):
    _require_admin(request)
    process_sensor_alerts()
    date_context = _viewing_date_context(request)
    selected_sensor_id = request.GET.get("sensor", "TEMPERATURE_01")
    if selected_sensor_id not in MONITORED_SENSOR_IDS:
        selected_sensor_id = "TEMPERATURE_01"

    readings = SensorReadingHistory.objects.filter(
        received_at__date=date_context["viewing_date"],
        sensor_id__in=MONITORED_SENSOR_IDS,
    ).order_by("received_at", "id")
    latest_by_sensor = {}
    for reading in readings:
        latest_by_sensor[reading.sensor_id] = reading

    def history_display(reading, sensor_id):
        name, icon, show_value = SENSOR_PRESENTATION[sensor_id]
        if reading is None:
            return {
                "sensor_id": sensor_id, "name": name, "icon": icon,
                "value_display": "—", "last_update": None,
                "health_label": "NO DATA", "problem": False,
            }
        if reading.sensor_type == "temperature":
            value_display = f"{reading.value}°C"
        elif reading.sensor_type == "humidity":
            value_display = f"{reading.value}%"
        elif reading.sensor_type == "fire":
            value_display = "Fire Detected" if sensor_is_detected(reading) else "Normal"
        else:
            value_display = reading.value.title()
        failed = reading.connection_status != "online"
        abnormal = reading.condition_status == "abnormal"
        if failed:
            health_label = "FAILED"
        elif abnormal:
            health_label = "DANGER" if reading.sensor_type == "fire" else "UNSAFE"
        else:
            health_label = "SAFE" if show_value else "NORMAL"
        return {
            "sensor_id": sensor_id, "name": name, "icon": icon,
            "value_display": value_display, "last_update": reading.received_at,
            "health_label": health_label, "problem": failed or abnormal,
        }

    historical_sensor_rows = [
        history_display(latest_by_sensor.get(sensor_id), sensor_id)
        for sensor_id in MONITORED_SENSOR_IDS
    ]
    selected_readings = [
        history_display(reading, selected_sensor_id)
        for reading in readings if reading.sensor_id == selected_sensor_id
    ]
    return render(
        request,
        "back1/admin_sensors.html",
        {
            "sensor_rows": historical_sensor_rows,
            "selected_sensor_id": selected_sensor_id,
            "selected_sensor_name": SENSOR_PRESENTATION[selected_sensor_id][0],
            "sensor_choices": [
                (sensor_id, SENSOR_PRESENTATION[sensor_id][0])
                for sensor_id in MONITORED_SENSOR_IDS
            ],
            "selected_readings": selected_readings,
            **date_context,
        },
    )


@login_required
def admin_revenue(request):
    _require_admin(request)
    date_context = _viewing_date_context(request)
    selected_type = request.GET.get("type", "all")
    if selected_type not in {"all", "parking", "penalty"}:
        selected_type = "all"

    revenue = _daily_revenue(date_context["viewing_date"])
    if selected_type == "parking":
        transactions = revenue["parking_transactions"]
    elif selected_type == "penalty":
        transactions = revenue["penalty_transactions"]
    else:
        transactions = revenue["parking_transactions"] | revenue["penalty_transactions"]

    return render(request, "back1/admin_revenue.html", {
        **date_context,
        **revenue,
        "selected_type": selected_type,
        "transactions": transactions.select_related("booking", "user").order_by("-paid_at", "-id"),
    })


@api_view(["POST"])
@permission_classes([IsAdminUser])
def acknowledge_alert(request, alert_id):
    alert = get_object_or_404(Alert, pk=alert_id)
    if not alert.acknowledged:
        alert.acknowledged = True; alert.acknowledged_at = timezone.now(); alert.acknowledged_by = request.user
        alert.save(update_fields=["acknowledged", "acknowledged_at", "acknowledged_by"])
        SystemEvent.objects.create(event_type="admin_action", source="alert", description=f"Admin acknowledged Alert #{alert.id}.", user=request.user, sensor=alert.sensor)
    return Response({"message": "Alert acknowledged."})


@login_required
def emergency_notify(request, emergency_id):
    _require_admin(request)
    emergency = get_object_or_404(Emergency, pk=emergency_id)
    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        if message:
            send_emergency_notifications(emergency=emergency, admin=request.user, message=message)
            messages.success(request, "Emergency notifications processed.")
        return redirect("back1:admin-dashboard")
    return render(request, "back1/emergency_notify.html", {"emergency": emergency})





# ==========================
# DASHBOARD VIEW
# ==========================


@login_required
def dashboard(request):

    _require_admin(request)
    process_sensor_alerts()
    date_context = _viewing_date_context(request)
    selected_date = date_context["viewing_date"]


    # ----------------------
    # Parking Summary
    # ----------------------

    total_slots = ParkingSlot.objects.count()
    parking_slots = ParkingSlot.objects.order_by("slot_number")
    now = timezone.localtime()
    current_time = now.time().replace(tzinfo=None)
    next_moment = now + timedelta(seconds=1)
    availability_end = (
        next_moment.time().replace(tzinfo=None)
        if next_moment.date() == now.date()
        else time.max
    )
    available_slots = available_parking_spaces(
        now.date(), current_time, availability_end
    ).count()


    occupied_slots = ParkingSlot.objects.filter(
        is_physically_occupied=True
    ).count()


    if total_slots > 0:

        occupancy_percentage = int(
            (occupied_slots / total_slots) * 100
        )

    else:

        occupancy_percentage = 0
    availability_percentage = int((available_slots / total_slots) * 100) if total_slots else 0





    # ----------------------
    # Latest Sensor
    # ----------------------

    latest_sensor = SensorData.objects.order_by(
        "-created_at"
    ).first()



    sensor_history = SensorData.objects.order_by(
        "-created_at"
    )[:10]






    # ----------------------
    # Booking
    # ----------------------

    latest_bookings = Booking.objects.filter(booking_date=selected_date).order_by(
        "-created_at"
    )[:5]
    
    
    expire_stale_pending_bookings(now=now)
    booking_count = Booking.objects.filter(
        booking_date=selected_date, status__in=CAPACITY_STATUSES
    ).count()



    # ----------------------
    # Gate
    # ----------------------

    entrance_gate = Gate.objects.filter(
        gate_type="entrance"
    ).first()



    exit_gate = Gate.objects.filter(
        gate_type="exit"
    ).first()





    # ----------------------
    # Emergency
    # ----------------------

    emergency_alerts = Emergency.objects.filter(
        status="active"
    ).order_by(
        "-created_at"
    )[:5]
    
    
    parking_slots = ParkingSlot.objects.all()


    revenue = _daily_revenue(selected_date)
    parking_revenue = revenue["parking_revenue"]
    penalty_revenue = revenue["penalty_revenue"]
    total_revenue = revenue["total_revenue"]
    
    
    # ----------------------
    # Recently Activity
    # ----------------------

    recent_activities = SystemEvent.objects.filter(timestamp__date=selected_date).select_related("booking", "parking_slot", "sensor").order_by("-timestamp")[:10]
    active_alerts = Alert.objects.filter(acknowledged=False).select_related("sensor").order_by("-created_at")
    active_emergency = Emergency.objects.filter(status="active").order_by("-created_at").first()
    sensor_rows = monitored_sensor_status()
    latest_emergency_sync = SensorData.objects.filter(
        sensor_id__in=["TEMPERATURE_01", "HUMIDITY_01", "FIRE_01"]
    ).aggregate(latest=Max("last_reading_at"))["latest"]
    sensor_issues = [row["issue"] for row in sensor_rows if row["issue"]]
    failed_sensors = [row for row in sensor_rows if row["failed"]]
    fire_sensor = next(row for row in sensor_rows if row["sensor_id"] == "FIRE_01")
    failed_gate_sensors = [row for row in failed_sensors if row["sensor_id"] in {"ENTRANCE_01", "EXIT_01"}]


    context = {


        "total_slots":
        total_slots,


        "occupied_slots":
        occupied_slots,


        "available_slots":
        available_slots,


        "occupancy_percentage":
        occupancy_percentage,
        "availability_percentage": availability_percentage,


        "latest_sensor":
        latest_sensor,


        "sensor_history":
        sensor_history,


        "latest_bookings":
        latest_bookings,
        
        "booking_count":
        booking_count,


        "parking_slots":
        parking_slots,


        "total_revenue":
        total_revenue,


        "parking_revenue":
        parking_revenue,


        "penalty_revenue":
        penalty_revenue,


        "entrance_gate":
        entrance_gate,


        "exit_gate":
        exit_gate,


        "emergency_alerts":
        emergency_alerts,


        "recent_bookings":
        latest_bookings,


        "recent_activities":
        recent_activities,
        "active_alerts": active_alerts,
        "active_alert_count": active_alerts.count(),
        "active_emergency": active_emergency,
        "sensor_issues": sensor_issues,
        "sensor_issue_count": len(sensor_issues),
        "sensor_rows": sensor_rows,
        **date_context,
        "latest_emergency_sync": latest_emergency_sync,
        "fire_detection_status": "FIRE DETECTED" if fire_sensor["abnormal"] and not fire_sensor["failed"] else "Normal",
        "sensor_failure_status": f"{len(failed_sensors)} Sensor Failed" if failed_sensors else "No Issue",
        "gate_failure_status": ", ".join(f'{row["name"]} Issue' for row in failed_gate_sensors) if failed_gate_sensors else "No Issue",
        "maintenance_slots": ParkingSlot.objects.filter(is_under_maintenance=True).count(),
        "disabled_slots": ParkingSlot.objects.filter(is_enabled=False).count(),
        "backup_slots": ParkingSlot.objects.filter(is_backup=True).count(),
        "upcoming_booking_count": Booking.objects.filter(booking_date__gte=timezone.localdate(), status__in=["pending", "confirmed"]).count(),

    }



    return render(

        request,

        "back1/dashboard.html",

        context

    )






# ==========================
# SENSOR STATUS API
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_sensor_status(request):


    sensors = SensorData.objects.all().order_by(
        "-updated_at"
    )



    sensor_list = []

    online = 0

    error = 0



    for sensor in sensors:


        derived_online = sensor_is_online(sensor)
        if derived_online:

            online += 1


        elif sensor.status == "error":

            error += 1





        sensor_list.append({

            "sensor_id":
            sensor.sensor_id,


            "type":
            sensor.sensor_type,


            "location":
            sensor.location,


            "value":
            sensor.value,


            "status": "online" if derived_online else "offline",

            "detected": sensor_is_detected(sensor),


            "updated_at":
            sensor.updated_at

        })




    rows = monitored_sensor_status()
    dashboard_rows = []
    for row in rows:
        if row["sensor_type"] == "parking":
            continue
        no_data = row["last_update"] is None
        if no_data and row["sensor_type"] in {"temperature", "humidity", "fire"}:
            display_status = "NO DATA"
        elif row["sensor_type"] in {"temperature", "humidity"}:
            display_status = "UNSAFE" if row["failed"] or row["abnormal"] else "SAFE"
        elif row["sensor_type"] == "fire":
            display_status = "FAILED" if row["failed"] else ("DANGER" if row["abnormal"] else "SAFE")
        else:
            display_status = "FAILED" if row["failed"] or row["abnormal"] else "NORMAL"
        dashboard_rows.append({
            "sensor_id": row["sensor_id"],
            "value": row["value_display"] or "—",
            "display_status": display_status,
            "problem": display_status in {"UNSAFE", "DANGER", "FAILED", "NO DATA"},
        })
    parking_rows = [row for row in rows if row["sensor_type"] == "parking"]
    parking_failed_count = sum(bool(row["failed"] or row["abnormal"]) for row in parking_rows)
    issue_count = sum(bool(row["issue"]) for row in rows)
    emergency_updates = [
        row["last_update"] for row in rows
        if row["sensor_id"] in {"TEMPERATURE_01", "HUMIDITY_01", "FIRE_01"} and row["last_update"]
    ]
    latest_sync = max(emergency_updates, default=None)

    return Response({

        "total":
        sensors.count(),


        "online":
        online,


        "error":
        error,


        "data": sensor_list,
        "gates": [
            {"gate_type": gate.gate_type, "is_open": gate.is_open, "updated_at": gate.updated_at}
            for gate in Gate.objects.order_by("gate_type")
        ],
        "server_time": timezone.now(),
        "dashboard": {
            "issue_count": issue_count,
            "banner": f"🔴 {issue_count} Active Issue{'s' if issue_count != 1 else ''}" if issue_count else "🟢 No Active Emergency",
            "sensors": dashboard_rows,
            "parking_failed_count": parking_failed_count,
            "latest_sync": latest_sync,
            "latest_sync_time": timezone.localtime(latest_sync).strftime("%I:%M %p") if latest_sync else None,
            "latest_sync_date": timezone.localtime(latest_sync).strftime("%d %b %Y") if latest_sync else None,
        },

    })
# ==========================
# PARKING SLOT API
# ==========================


@api_view(["GET"])
def parking_slots(request):


    slots = ParkingSlot.objects.all().order_by(
        "slot_number"
    )


    data = []


    for slot in slots:


        data.append({

            "slot_number":
            slot.slot_number,


            "status":
            slot.status,


            "updated_at":
            slot.updated_at

        })



    return Response({

        "total":
        slots.count(),


        "slots":
        data

    })


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_set_parking_state(request, slot_id):
    try:
        slot = ParkingSlot.objects.get(id=slot_id)
    except ParkingSlot.DoesNotExist:
        return Response({"error": "Parking slot not found"}, status=404)

    requested_state = request.data.get("state")
    state_fields = {
        "normal": {
            "is_enabled": True,
            "is_under_maintenance": False,
            "is_backup": False,
        },
        "disabled": {
            "is_enabled": False,
            "is_under_maintenance": False,
            "is_backup": False,
        },
        "maintenance": {
            "is_enabled": True,
            "is_under_maintenance": True,
            "is_backup": False,
        },
        "backup": {
            "is_enabled": True,
            "is_under_maintenance": False,
            "is_backup": True,
        },
    }
    if requested_state not in state_fields:
        return Response({"error": "Invalid parking state"}, status=400)

    for field, value in state_fields[requested_state].items():
        setattr(slot, field, value)

    if requested_state == "normal":
        if slot.is_physically_occupied:
            slot.status = "occupied"
        elif slot.is_booking_reserved:
            slot.status = "reserved"
        else:
            slot.status = "available"
    else:
        slot.status = requested_state

    slot.save(update_fields=[
        "is_enabled",
        "is_under_maintenance",
        "is_backup",
        "status",
        "updated_at",
    ])

    SystemEvent.objects.create(
        event_type="admin_action",
        source="admin_parking_management",
        description=f"Admin set {slot.slot_number} to {requested_state.title()}.",
        user=request.user,
        parking_slot=slot,
    )

    return Response({
        "slot_number": slot.slot_number,
        "state": requested_state,
        "is_enabled": slot.is_enabled,
        "is_under_maintenance": slot.is_under_maintenance,
        "is_backup": slot.is_backup,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_availability(request):
    booking_date = parse_date(request.query_params.get("date", ""))
    start_time = parse_time(request.query_params.get("start_time", ""))
    end_time = parse_time(request.query_params.get("end_time", ""))
    if not booking_date or not start_time or not end_time or end_time <= start_time:
        return Response({"error": "Valid date and start/end times are required."}, status=400)
    if booking_date < timezone.localdate() or booking_range_has_ended(booking_date, end_time):
        return Response({"error": "This booking time has already ended."}, status=400)
    return Response(availability(booking_date, start_time, end_time))







# ==========================
# BOOKING API
# ==========================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_list(request):

    bookings = Booking.objects.all()
    if not _is_admin(request.user):
        bookings = bookings.filter(user=request.user)

    bookings = bookings.order_by(
        "-created_at"
    )[:10]



    data = []



    for booking in bookings:


        data.append({

            "id":
            booking.id,


            "user":
            booking.user.username,


            "slot":
            booking.parking_slot.slot_number,


            "date":
            booking.booking_date,


            "start_time":
            booking.start_time,


            "end_time":
            booking.end_time,


            "status":
            booking.status

        })




    return Response({

        "total":
        bookings.count(),


        "bookings":
        data

    })







# ==========================
# GATE CONTROL API
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def gate_status(request):


    gates = Gate.objects.all()



    data = []



    for gate in gates:


        data.append({

            "id":
            gate.id,


            "name":
            gate.gate_name,


            "type":
            gate.gate_type,


            "is_open":
            gate.is_open,


            "status":
            "Open" if gate.is_open else "Closed"

        })




    return Response({

        "gates":
        data

    })







@api_view(["POST"])
@permission_classes([IsAdminUser])
def gate_control(request, gate_id):


    try:

        gate = Gate.objects.get(
            id=gate_id
        )


    except Gate.DoesNotExist:


        return Response(

            {
                "error":
                "Gate not found"
            },

            status=status.HTTP_404_NOT_FOUND

        )





    action = request.data.get(
        "action"
    )




    if action == "open":


        gate.is_open = True


    elif action == "close":


        gate.is_open = False


    else:


        return Response(

            {
                "error":
                "Invalid action"
            },

            status=status.HTTP_400_BAD_REQUEST

        )




    gate.save()



    return Response({

        "message":
        f"{gate.gate_name} {action}ed",


        "status":
        gate.is_open

    })






# ==========================
# EMERGENCY API
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def emergency_status(request):


    emergencies = Emergency.objects.filter(
        status="active"
    ).order_by(
        "-created_at"
    )



    data = []



    for emergency in emergencies:


        data.append({

            "type":
            emergency.emergency_type,


            "description":
            emergency.description,


            "status":
            emergency.status,


            "created_at":
            emergency.created_at

        })




    return Response({

        "active_alerts":
        emergencies.count(),


        "data":
        data

    })
# ==========================
# SENSOR DATA FROM RASPBERRY PI
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def latest_sensor(request):


    sensor = SensorData.objects.order_by(
        "-created_at"
    ).first()



    if not sensor:


        return Response({

            "message":
            "No sensor data available"

        })




    serializer = SensorDataSerializer(
        sensor
    )


    return Response(
        serializer.data
    )







@api_view(["GET"])
@permission_classes([IsAdminUser])
def sensor_history(request):


    sensors = SensorData.objects.order_by(
        "-created_at"
    )[:50]



    serializer = SensorDataSerializer(

        sensors,

        many=True

    )



    return Response(
        serializer.data
    )








# ==========================
# RASPBERRY PI UPDATE SENSOR
# ==========================


@api_view(["POST"])
@permission_classes([AllowAny])
def update_sensor(request):

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    is_device = _device_api_key_is_valid(request)

    if not is_device and not _is_admin(request.user):

        return Response(
            {
                "error": "Valid device authentication is required."
            },
            status=401 if not request.user.is_authenticated else 403
        )

    # ============================================================
    # UPDATE SENSOR
    # ============================================================

    try:

        sensor_id = request.data.get(
            "sensor_id",
            ""
        )

        value = request.data.get(
            "value",
            ""
        )

        sensor, changed = update_logical_sensor(
            sensor_id=sensor_id,
            value=value,
            condition_status=request.data.get(
                "condition_status"
            ),
        )

    except ValueError as exc:

        sensor_type = request.data.get("sensor_type")

        sensor_id = request.data.get("sensor_id")

        value = request.data.get("value", "")


        # ========================================================
        # AUTOMATIC DEVICE SENSOR REGISTRATION
        # ========================================================
        #
        # Raspberry Pi sends a sensor that does not exist yet.
        #
        # Example:
        #
        # FLAME_01
        # sensor_type = fire
        #
        # The backend automatically creates it.
        #
        # This is especially useful when moving to Azure/cloud.
        # ========================================================

        if is_device and sensor_id and sensor_type:

            sensor, created = SensorData.objects.get_or_create(

                sensor_id=sensor_id,

                defaults={

                    "sensor_type":
                    sensor_type,

                    "location":
                    request.data.get(
                        "location",
                        ""
                    ),

                    "value":
                    value,

                    "status":
                    request.data.get(
                        "status",
                        "active"
                    ),

                    "connection_status":
                    "online",

                    "condition_status":
                    request.data.get(
                        "condition_status",
                        "normal"
                    ),

                    "last_reading_at":
                    timezone.now(),

                },
            )


            # ====================================================
            # SENSOR ALREADY EXISTS
            # ====================================================

            if not created:

                sensor.value = value

                sensor.connection_status = "online"

                sensor.last_reading_at = timezone.now()


                if request.data.get(
                    "condition_status"
                ):

                    sensor.condition_status = (
                        request.data.get(
                            "condition_status"
                        )
                    )


                sensor.save(

                    update_fields=[

                        "value",

                        "connection_status",

                        "condition_status",

                        "last_reading_at",

                        "updated_at",

                    ]

                )


            print(
                f"Device sensor "
                f"{'created' if created else 'updated'}: "
                f"{sensor_id}"
            )


            return Response(

                {

                    "message":
                    "Sensor registered and updated",

                    "sensor_id":
                    sensor.sensor_id,

                    "sensor_type":
                    sensor.sensor_type,

                    "created":
                    created,

                },

                status=201 if created else 200

            )


        # ========================================================
        # EXISTING ADMIN BEHAVIOUR
        # ========================================================

        if _is_admin(request.user) and sensor_type:

            sensor, created = (
                SensorData.objects.update_or_create(

                    sensor_id=sensor_id,

                    defaults={

                        "sensor_type":
                        sensor_type,

                        "location":
                        request.data.get(
                            "location",
                            ""
                        ),

                        "value":
                        value,

                        "last_reading_at":
                        timezone.now(),

                        "connection_status":
                        "online",

                    },

                )
            )


            return Response(

                {

                    "message":
                    "Sensor updated",

                    "sensor_id":
                    sensor.sensor_id,

                    "changed":
                    created,

                },

                status=201

            )


        # ========================================================
        # ORIGINAL ERROR
        # ========================================================

        return Response(

            {

                "error":
                str(exc)

            },

            status=400

        )

    # ============================================================
    # PARKING SENSOR → LED OFF
    # ============================================================

    PARKING_SENSOR_TO_SLOT = {

        "PARK_A01": "A01",

        "PARK_A02": "A02",

        "PARK_A03": "A03",

        "PARK_A04": "A04",

    }

    slot_number = PARKING_SENSOR_TO_SLOT.get(
        sensor_id
    )

    if (
        slot_number
        and value == "detected"
    ):

        try:

            parking_slot = ParkingSlot.objects.get(
                slot_number=slot_number
            )

            led = ParkingLED.objects.get(
                parking_slot=parking_slot
            )

            # ----------------------------------------------------
            # Only create OFF command if LED is currently ON
            # ----------------------------------------------------

            if led.status == "on":

                LEDCommand.objects.create(

                    led=led,

                    parking_slot=parking_slot,

                    action="off",

                    status="pending",

                    requested_via="lifecycle",

                    expires_at=(
                        timezone.now()
                        + timezone.timedelta(
                            seconds=30
                        )
                    ),
                )

                print(
                    f"{slot_number}: "
                    f"vehicle detected → "
                    f"{led.led_name} OFF command created"
                )

        except ParkingSlot.DoesNotExist:

            print(
                f"Parking slot {slot_number} not found."
            )

        except ParkingLED.DoesNotExist:

            print(
                f"LED for slot {slot_number} not found."
            )

    # ============================================================
    # RESPONSE
    # ============================================================

    return Response(
        {
            "message": "Sensor updated",

            "sensor_id":
            sensor.sensor_id,

            "changed":
            changed,

            "parking_slot":
            slot_number,

            "vehicle_detected":
            value == "detected",
        }
    )

# ==========================
# REVENUE DASHBOARD API
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def revenue_summary(request):


    transactions = Transaction.objects.all()



    total_revenue = Decimal("0")

    parking_revenue = Decimal("0")

    penalty_revenue = Decimal("0")




    for transaction in transactions:


        if transaction.transaction_type == "payment":

            total_revenue += transaction.amount

            parking_revenue += transaction.amount



        elif transaction.transaction_type == "penalty":

            total_revenue += transaction.amount

            penalty_revenue += transaction.amount






    return Response({

        "total_revenue":
        total_revenue,


        "parking_revenue":
        parking_revenue,


        "penalty_revenue":
        penalty_revenue

    })







# ==========================
# CREATE BOOKING
# ==========================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_booking(request):

    if _is_admin(request.user):
        raise PermissionDenied

    form = BookingForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=400)
    try:
        secure_booking = create_pending_booking(user=request.user, **form.cleaned_data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response({"message": "Booking created successfully", "booking_id": secure_booking.id})

    try:

        slot_id = request.data.get(
            "parking_slot"
        )


        booking_date = request.data.get(
            "booking_date"
        )


        start_time = request.data.get(
            "start_time"
        )


        end_time = request.data.get(
            "end_time"
        )



        slot = ParkingSlot.objects.get(

            id=slot_id

        )




        conflict = Booking.objects.filter(

            parking_slot=slot,

            booking_date=booking_date,

            start_time__lt=end_time,

            end_time__gt=start_time,

            status__in=[
                "confirmed",
                "parked"
            ]

        ).exists()





        if conflict:


            return Response({

                "error":
                "Parking slot already booked"

            },

            status=400

            )







        booking = Booking.objects.create(

            user=request.user,

            parking_slot=slot,

            booking_date=booking_date,

            start_time=start_time,

            end_time=end_time,

            status="pending"

        )





        return Response({

            "message":
            "Booking created successfully",


            "booking_id":
            booking.id

        })





    except ParkingSlot.DoesNotExist:


        return Response({

            "error":
            "Parking slot not found"

        },

        status=404

        )
# ==========================
# CAR ENTRY
# ==========================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def car_entry(request, booking_id):

    return Response({"error": "This legacy endpoint is retired. Use the validated customer gate flow."}, status=410)

    booking = _get_authorized_booking(request, booking_id)

    if booking is None:


        return Response({

            "error":
            "Booking not found"

        },

        status=404

        )




    booking.actual_arrival_time = timezone.now()

    booking.status = "parked"

    booking.save()



    slot = booking.parking_slot


    if slot:

        slot.status = "occupied"

        slot.save()



    return Response({

        "message":
        "Car entered parking",


        "booking_status":
        booking.status,


        "slot":
        slot.slot_number

    })







# ==========================
# CAR EXIT + PAYMENT
# ==========================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def car_exit(request, booking_id):

    return Response({"error": "This legacy endpoint is retired. Use the validated exit gate and overstay flow."}, status=410)

    booking = _get_authorized_booking(request, booking_id)

    if booking is None:


        return Response({

            "error":
            "Booking not found"

        },

        status=404

        )





    exit_time = timezone.now()



    parking_fee = Decimal("2.00")

    penalty = Decimal("0")

    overtime_minutes = 0





    end_datetime = timezone.make_aware(

        timezone.datetime.combine(

            booking.booking_date,

            booking.end_time

        )

    )





    if exit_time > end_datetime:


        overtime_minutes = int(

            (

                exit_time - end_datetime

            ).total_seconds()

            / 60

        )


        penalty = Decimal("20.00")


        booking.status = "overtime"



    else:


        booking.status = "completed"






    total_payment = (

        parking_fee +

        penalty

    )






    wallet, created = Wallet.objects.get_or_create(

        user=booking.user

    )





    if wallet.balance < total_payment:


        return Response({

            "error":
            "Insufficient balance"

        },

        status=400

        )







    wallet.balance -= total_payment

    wallet.save()






    Transaction.objects.create(

        user=booking.user,

        transaction_type="payment",

        amount=parking_fee

    )







    if penalty > 0:


        Transaction.objects.create(

            user=booking.user,

            transaction_type="penalty",

            amount=penalty

        )






    booking.actual_exit_time = exit_time

    booking.overtime_minutes = overtime_minutes

    booking.save()





    slot = booking.parking_slot


    if slot:


        slot.status = "available"

        slot.save()





    return Response({

        "message":
        "Exit completed",


        "parking_fee":
        parking_fee,


        "penalty":
        penalty,


        "overtime_minutes":
        overtime_minutes

    })








# ==========================
# CANCEL BOOKING
# ==========================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_booking(request, booking_id):
    if _is_admin(request.user):
        raise PermissionDenied
    authorized_booking = _get_authorized_booking(request, booking_id)
    if authorized_booking is None:
        return Response({"error": "Booking not found"}, status=404)
    try:
        booking, refund, changed = cancel_customer_booking(
            booking_id=booking_id,
            user=request.user,
        )
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    if not changed:
        return Response({"message": "Booking was already cancelled.", "refunded": bool(refund)})
    return Response({
        "message": (
            f"Booking cancelled. £{refund.amount} was refunded to your wallet."
            if refund else "Booking cancelled. No refund was issued."
        ),
        "refunded": bool(refund),
        "refund_amount": refund.amount if refund else Decimal("0.00"),
    })








# ==========================
# WALLET API
# ==========================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wallet_detail(request, user_id):

    if not _is_admin(request.user) and request.user.id != user_id:
        raise PermissionDenied

    try:


        wallet = Wallet.objects.get(

            user_id=user_id

        )


    except Wallet.DoesNotExist:


        return Response({

            "error":
            "Wallet not found"

        },

        status=404

        )





    serializer = WalletSerializer(

        wallet

    )


    return Response(

        serializer.data

    )








# ==========================
# ADD WALLET BALANCE
# ==========================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_wallet_balance(request, user_id):

    if not _is_admin(request.user) and request.user.id != user_id:
        raise PermissionDenied

    amount = request.data.get(

        "amount"

    )



    try:

        parsed_amount = Decimal(amount)
        if not parsed_amount.is_finite() or parsed_amount <= 0:
            raise ValueError


        wallet, created = Wallet.objects.get_or_create(

            user_id=user_id

        )



        wallet.balance += parsed_amount


        wallet.save()





        return Response({

            "message":
            "Balance updated",


            "balance":
            wallet.balance

        })





    except Exception:


        return Response({

            "error":
            "Invalid amount"

        },

        status=400

        )







# ==========================
# TRANSACTION HISTORY
# ==========================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history(request, user_id):

    if not _is_admin(request.user) and request.user.id != user_id:
        raise PermissionDenied

    transactions = Transaction.objects.filter(

        user_id=user_id

    ).order_by(

        "-created_at"

    )



    serializer = TransactionSerializer(

        transactions,

        many=True

    )



    return Response(

        serializer.data

    )
# ==========================
# EMERGENCY API
# ==========================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def emergency_list(request):


    emergencies = Emergency.objects.all().order_by(
        "-created_at"
    )


    serializer = EmergencySerializer(

        emergencies,

        many=True

    )


    return Response(

        serializer.data

    )







# ==========================
# CREATE EMERGENCY
# ==========================


@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_emergency(request):


    emergency = Emergency.objects.create(

        emergency_type=request.data.get(
            "emergency_type"
        ),


        description=request.data.get(
            "description"
        ),


        status="active"

    )



    return Response({

        "message":
        "Emergency created successfully",


        "data":
        EmergencySerializer(
            emergency
        ).data

    })







# ==========================
# RESOLVE EMERGENCY
# ==========================


@api_view(["POST"])
@permission_classes([IsAdminUser])
def resolve_emergency(request, emergency_id):


    try:


        emergency = Emergency.objects.get(

            id=emergency_id

        )


    except Emergency.DoesNotExist:


        return Response({

            "error":
            "Emergency not found"

        },

        status=404

        )





    changed = emergency.status != "resolved"
    emergency.status = "resolved"
    emergency.save(update_fields=["status", "updated_at"])
    if changed:
        SystemEvent.objects.create(event_type="emergency", source="admin_emergency", description=f"Admin resolved Emergency #{emergency.id}.", user=request.user)



    return Response({

        "message":
        "Emergency resolved",


        "status":
        emergency.status

    })
    

# ==========================
# FIRE SENSOR CHECK
# ==========================

@api_view(["GET"])
@permission_classes([IsAdminUser])
def fire_sensor_check(request):

    sensors = SensorData.objects.filter(
        sensor_type="fire"
    )

    alerts = []

    for sensor in sensors:

        value = str(
            sensor.value
        ).strip().lower()

        # Digital flame sensor
        #
        # Raspberry Pi sends:
        # detected = flame detected
        # clear    = no flame

        if value == "detected":

            alerts.append({

                "sensor_id":
                sensor.sensor_id,

                "location":
                sensor.location,

                "value":
                sensor.value,

                "status":
                "danger"

            })

    return Response({

        "fire_detected":
        len(alerts) > 0,

        "alerts":
        alerts

    })

# ============================================================
# CREATE PARKING LED COMMAND AFTER SUCCESSFUL GATE OPEN
# ============================================================

def create_parking_led_command_from_gate(gate_command):
    """
    When an entrance gate successfully opens for a booking,
    create a GREEN LED command for the booked parking slot.
    """

    # --------------------------------------------------------
    # Only process OPEN commands
    # --------------------------------------------------------

    if gate_command.action != "open":
        return None

    # --------------------------------------------------------
    # Only process entrance gate
    # --------------------------------------------------------

    if gate_command.gate.gate_type not in (
        "entrance",
        "entry",
    ):
        return None

    # --------------------------------------------------------
    # Gate command must have a booking
    # --------------------------------------------------------

    if not gate_command.booking:
        return None

    # --------------------------------------------------------
    # Booking must have a parking slot
    # --------------------------------------------------------

    parking_slot = gate_command.booking.parking_slot

    if not parking_slot:
        return None

    # --------------------------------------------------------
    # Find GREEN LED for this parking slot
    # --------------------------------------------------------

    try:

        green_led = ParkingLED.objects.get(
            parking_slot=parking_slot,
            led_type="green",
        )

    except ParkingLED.DoesNotExist:

        print(
            f"No green LED found for slot "
            f"{parking_slot.slot_number}"
        )

        return None

    # --------------------------------------------------------
    # Prevent duplicate pending/executing command
    # --------------------------------------------------------

    existing_command = LEDCommand.objects.filter(
        led=green_led,
        action="on",
        status__in=[
            "pending",
            "executing",
        ],
    ).first()

    if existing_command:

        return existing_command

    # --------------------------------------------------------
    # Create LED command
    # --------------------------------------------------------

    now = timezone.now()

    led_command = LEDCommand.objects.create(

        led=green_led,

        parking_slot=parking_slot,

        action="on",

        status="pending",

        requested_via="lifecycle",

        expires_at=(
            now + timezone.timedelta(seconds=30)
        ),
    )

    # --------------------------------------------------------
    # System event
    # --------------------------------------------------------

    SystemEvent.objects.create(

        event_type="other",

        source="gate_led",

        description=(
            f"Entrance gate opened successfully. "
            f"Green LED command created for "
            f"parking slot "
            f"{parking_slot.slot_number}."
        ),

        booking=gate_command.booking,

        parking_slot=parking_slot,

        gate=gate_command.gate,
    )

    print(
        f"LED command {led_command.id} created for "
        f"slot {parking_slot.slot_number}"
    )

    return led_command
# ============================================================
# GATE API
# ============================================================

@api_view(["GET"])
@permission_classes([IsAdminUser])
def gates_api(request):

    gates = Gate.objects.all()

    serializer = GateSerializer(
        gates,
        many=True
    )

    return Response(
        serializer.data
    )


# ============================================================
# DEVICE GATE COMMANDS
# ============================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def device_gate_commands(request):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": (
                    "Valid device authentication "
                    "is required."
                )
            },
            status=401
        )

    # --------------------------------------------------------
    # CURRENT TIME
    # --------------------------------------------------------

    now = timezone.now()

    # --------------------------------------------------------
    # EXPIRE OLD COMMANDS
    # --------------------------------------------------------

    expire_gate_commands(
        now=now
    )

    # --------------------------------------------------------
    # GET PENDING COMMANDS
    # --------------------------------------------------------

    commands = GateCommand.objects.filter(
        status="pending",
        expires_at__gt=now,
    ).select_related(
        "gate",
        "booking",
        "booking__parking_slot",
    ).order_by(
        "created_at",
        "id",
    )

    # --------------------------------------------------------
    # BUILD RESPONSE
    # --------------------------------------------------------

    command_data = []

    for command in commands:

        booking = command.booking

        parking_slot = None

        if booking:

            parking_slot = booking.parking_slot

        command_data.append(
            {
                "id": command.id,

                "gate_id": command.gate_id,

                "gate": command.gate.gate_type,

                "gate_name": command.gate.gate_name,

                "action": command.action,

                "status": command.status,

                "booking_id": (
                    booking.id
                    if booking
                    else None
                ),

                "slot_number": (
                    parking_slot.slot_number
                    if parking_slot
                    else None
                ),

                "created_at": command.created_at,

                "expires_at": command.expires_at,
            }
        )

    return Response(
        {
            "commands": command_data
        }
    )


# ============================================================
# CLAIM GATE COMMAND
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def device_claim_gate_command(
    request,
    command_id
):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": (
                    "Valid device authentication "
                    "is required."
                )
            },
            status=401
        )

    # --------------------------------------------------------
    # CLAIM COMMAND
    # --------------------------------------------------------

    try:

        command = claim_gate_command(
            command_id=command_id
        )

    except GateCommand.DoesNotExist:

        return Response(
            {
                "error": "Gate command not found."
            },
            status=404
        )

    except ValueError as exc:

        return Response(
            {
                "error": str(exc)
            },
            status=409
        )

    # --------------------------------------------------------
    # BOOKING / SLOT
    # --------------------------------------------------------

    booking = command.booking

    parking_slot = None

    if booking:

        parking_slot = booking.parking_slot

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response(
        {
            "id": command.id,

            "gate_id": command.gate_id,

            "gate": command.gate.gate_type,

            "gate_name": command.gate.gate_name,

            "action": command.action,

            "status": command.status,

            "booking_id": (
                booking.id
                if booking
                else None
            ),

            "slot_number": (
                parking_slot.slot_number
                if parking_slot
                else None
            ),

            "expires_at": command.expires_at,
        }
    )

# ============================================================
# ACKNOWLEDGE GATE COMMAND
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def device_acknowledge_gate_command(
    request,
    command_id
):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": (
                    "Valid device authentication "
                    "is required."
                )
            },
            status=401
        )

    # --------------------------------------------------------
    # RESULT STATUS
    # --------------------------------------------------------

    result_status = request.data.get(
        "status",
        ""
    )

    if result_status not in [
        "succeeded",
        "failed",
    ]:

        return Response(
            {
                "error": (
                    "Acknowledgement status must be "
                    "succeeded or failed."
                )
            },
            status=400
        )

    # --------------------------------------------------------
    # ACKNOWLEDGE GATE COMMAND
    # --------------------------------------------------------

    try:

        command, changed = acknowledge_gate_command(
            command_id=command_id,
            result_status=result_status,
            error_message=request.data.get(
                "error",
                ""
            ),
        )

    except GateCommand.DoesNotExist:

        return Response(
            {
                "error": "Gate command not found."
            },
            status=404
        )

    except ValueError as exc:

        return Response(
            {
                "error": str(exc)
            },
            status=409
        )

    # --------------------------------------------------------
    # BOOKING
    # --------------------------------------------------------

    booking = command.booking

    # --------------------------------------------------------
    # PARKING SLOT
    # --------------------------------------------------------

    parking_slot = None

    if booking:

        parking_slot = booking.parking_slot

    # --------------------------------------------------------
    # LED COMMAND
    # --------------------------------------------------------

    led_command = None

    # ========================================================
    # LED RULE
    #
    # ONLY:
    #   - entrance gate
    #   - successful open command
    #   - parking slot exists
    #
    # will create an LED command.
    #
    # EXIT GATE:
    #   NEVER creates an LED command.
    #
    # NO LED COLOUR IS USED.
    # ========================================================

    if (
        result_status == "succeeded"
        and command.action == "open"
        and command.gate.gate_type == "entrance"
        and parking_slot
    ):

        # ----------------------------------------------------
        # FIND LED ASSIGNED TO THIS PARKING SLOT
        # ----------------------------------------------------

        led = ParkingLED.objects.filter(
            parking_slot=parking_slot
        ).first()

        # ----------------------------------------------------
        # CREATE LED COMMAND
        # ----------------------------------------------------

        if led:

            now = timezone.now()

            led_command = LEDCommand.objects.create(
                led=led,

                parking_slot=parking_slot,

                action="on",

                status="pending",

                requested_via="lifecycle",

                expires_at=(
                    now
                    + timezone.timedelta(
                        seconds=30
                    )
                ),
            )

            # ------------------------------------------------
            # SYSTEM EVENT
            # ------------------------------------------------

            SystemEvent.objects.create(
                event_type="other",

                source="gate_led",

                description=(
                    f"LED "
                    f"{led.led_name} "
                    f"turned ON after "
                    f"entrance gate "
                    f"{command.gate.gate_name} "
                    f"opened for parking slot "
                    f"{parking_slot.slot_number}."
                ),

                parking_slot=parking_slot,

                booking=booking,
            )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response(
        {
            "id": command.id,

            "gate_id": command.gate_id,

            "gate": command.gate.gate_type,

            "gate_name": command.gate.gate_name,

            "action": command.action,

            "status": command.status,

            "booking_id": (
                booking.id
                if booking
                else None
            ),

            "slot_number": (
                parking_slot.slot_number
                if parking_slot
                else None
            ),

            "led_command_id": (
                led_command.id
                if led_command
                else None
            ),

            "led": (
                led_command.led.led_name
                if led_command
                else None
            ),

            "message": (
                "Entrance gate acknowledged "
                "and LED command created."
                if led_command
                else
                "Gate command acknowledged."
            ),
        }
    )
    
    
    
# ============================================================
# OPEN GATE
# ============================================================

@api_view(["POST"])
@permission_classes([IsAdminUser])
def open_gate(
    request,
    gate_id
):

    # --------------------------------------------------------
    # FIND GATE
    # --------------------------------------------------------

    try:

        gate = Gate.objects.get(
            id=gate_id
        )

    except Gate.DoesNotExist:

        return Response(
            {
                "error": "Gate not found."
            },
            status=404
        )

    # --------------------------------------------------------
    # GET GATE TYPE
    # --------------------------------------------------------

    gate_type = gate.gate_type
    # ========================================================
    # ENTRANCE GATE
    # ========================================================

    if gate_type == "entrance":

        # Slot number is OPTIONAL for admin
        slot_number = request.data.get("slot_number")

        parking_slot = None
        booking = None

        # If admin provided a slot number, try to find it
        if slot_number:

            try:
                parking_slot = ParkingSlot.objects.get(
                    slot_number=slot_number
                )

            except ParkingSlot.DoesNotExist:

                return Response(
                    {
                        "error": (
                            f"Parking slot "
                            f"{slot_number} not found."
                        )
                    },
                    status=404
                )

            # Try to find an active booking
            booking = Booking.objects.filter(
                parking_slot=parking_slot,
                booking_date=timezone.localdate(),
                status__in=[
                    "confirmed",
                    "active",
                    "parked",
                    "overtime",
                ],
            ).order_by(
                "-created_at"
            ).first()

        # No slot number or no booking:
        # Admin can still open the gate.


    # ========================================================
    # EXIT GATE
    # ========================================================

    elif gate_type == "exit":

        parking_slot = None
        booking = None


    # ========================================================
    # UNKNOWN GATE TYPE
    # ========================================================

    else:

        return Response(
            {
                "error": (
                    f"Unsupported gate type: "
                    f"{gate_type}"
                )
            },
            status=400
        )
        
    # ========================================================
    # REMOVE OLD PENDING COMMANDS
    # ========================================================

    GateCommand.objects.filter(
        gate=gate,
        status="pending",
    ).update(
        status="expired"
    )

    # ========================================================
    # UPDATE DATABASE GATE STATE
    # ========================================================

    gate.is_open = True

    gate.save(
        update_fields=[
            "is_open",
            "updated_at",
        ]
    )

    # ========================================================
    # CREATE NEW GATE COMMAND
    # ========================================================

    gate_command, _created = create_gate_command(
        gate=gate,

        action="open",

        requested_via="admin",

        requested_by_user=request.user,

        booking=booking,
    )

    # ========================================================
    # SYSTEM EVENT
    # ========================================================

    SystemEvent.objects.create(
        event_type="gate_opened",

        source="admin_gate",

        description=(
            f"Admin manually opened "
            f"{gate.gate_name}."
            +
            (
                f" Parking slot "
                f"{parking_slot.slot_number}."
                if parking_slot
                else
                ""
            )
        ),

        user=request.user,

        gate=gate,

        parking_slot=parking_slot,

        booking=booking,
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return Response(
        {
            "message": "Gate opened.",

            "gate": gate.gate_name,

            "gate_type": gate.gate_type,

            "status": gate.is_open,

            "parking_slot": (
                parking_slot.slot_number
                if parking_slot
                else None
            ),

            "booking_id": (
                booking.id
                if booking
                else None
            ),

            "gate_command_id": gate_command.id,
        }
    )


# ============================================================
# CLOSE GATE
# ============================================================

@api_view(["POST"])
@permission_classes([IsAdminUser])
def close_gate(
    request,
    gate_id
):

    # --------------------------------------------------------
    # FIND GATE
    # --------------------------------------------------------

    try:

        gate = Gate.objects.get(
            id=gate_id
        )

    except Gate.DoesNotExist:

        return Response(
            {
                "error": "Gate not found."
            },
            status=404
        )

    # --------------------------------------------------------
    # REMOVE OLD PENDING COMMANDS
    # --------------------------------------------------------

    GateCommand.objects.filter(
        gate=gate,
        status="pending",
    ).update(
        status="expired"
    )

    # --------------------------------------------------------
    # CLOSE GATE
    # --------------------------------------------------------

    gate.is_open = False

    gate.save(
        update_fields=[
            "is_open",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # CREATE CLOSE COMMAND
    #
    # No booking is required for closing either gate.
    # --------------------------------------------------------

    gate_command, _created = create_gate_command(
        gate=gate,

        action="close",

        requested_via="admin",

        requested_by_user=request.user,

        booking=None,
    )

    # --------------------------------------------------------
    # SYSTEM EVENT
    # --------------------------------------------------------

    SystemEvent.objects.create(
        event_type="gate_closed",

        source="admin_gate",

        description=(
            f"Admin manually closed "
            f"{gate.gate_name}."
        ),

        user=request.user,

        gate=gate,
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response(
        {
            "message": "Gate closed.",

            "gate": gate.gate_name,

            "gate_type": gate.gate_type,

            "status": gate.is_open,

            "gate_command_id": gate_command.id,
        }
    )
    
    


# ==========================
# WEB VIEWS
# ==========================


class SensorReadingListView(ListView):


    model = SensorData


    template_name = (
        "back1/sensor_readings.html"
    )


    context_object_name = (
        "sensors"
    )








class ParkingSlotListView(ListView):


    model = ParkingSlot


    template_name = (
        "back1/parking_slots.html"
    )


    context_object_name = (
        "slots"
    )








class BookingListView(ListView):


    model = Booking


    template_name = (
        "back1/bookings.html"
    )


    context_object_name = (
        "bookings"
    )








class BookingCreateView(LoginRequiredMixin, View):
    template_name = "back1/booking_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and _is_admin(request.user):
            return redirect("back1:admin-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {
            "form": BookingForm(),
            "hours": [f"{hour:02d}:00" for hour in range(24)],
        })

    def post(self, request):
        # Legacy parking-space fields are deliberately ignored. Assignment is
        # always recalculated server-side from the authenticated request.
        form = BookingForm(request.POST)
        if form.is_valid():
            try:
                booking = create_pending_booking(
                    user=request.user, **form.cleaned_data
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Parking space assigned. Complete payment to confirm.")
                return redirect("back1:booking-payment", booking_id=booking.id)
        return render(request, self.template_name, {
            "form": form,
            "hours": [f"{hour:02d}:00" for hour in range(24)],
        })


@login_required
def booking_payment(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("parking_slot"), pk=booking_id, user=request.user
    )
    expire_stale_pending_bookings()
    booking.refresh_from_db()
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    if request.method == "POST":
        try:
            booking, charged = pay_booking(booking_id=booking.id, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            if charged:
                send_booking_confirmation(booking)
            return redirect("back1:booking-success", booking_id=booking.id)
    return render(request, "back1/booking_payment.html", {
        "booking": booking, "wallet": wallet,
    })


@login_required
def booking_success(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("parking_slot"),
        pk=booking_id, user=request.user, payment_status="paid",
    )
    return render(request, "back1/booking_success.html", {"booking": booking})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def customer_gate_request(request, booking_id, gate_type):
    if gate_type not in ["entrance", "exit"]:
        return Response({"error": "Invalid gate."}, status=400)
    try:
        booking, gate, changed = request_customer_gate(
            booking_id=booking_id, user=request.user, gate_type=gate_type
        )
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found."}, status=404)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response({"message": f"{gate.get_gate_type_display()} Gate is open.", "changed": changed})


@login_required
def overstay_payment(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("parking_slot"), pk=booking_id, user=request.user
    )
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    rate = ParkingRate.objects.order_by("id").first()
    if request.method == "POST":
        try:
            booking, charged = pay_overstay(booking_id=booking.id, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            if charged:
                messages.success(request, "Overstay payment completed. Request the Exit Gate again.")
            return redirect("back1:bookings")
    return render(request, "back1/overstay_payment.html", {"booking": booking, "wallet": wallet, "rate": rate})
# ============================================================
# LED API
# ============================================================


# ============================================================
# GET LED COMMANDS
# Raspberry Pi polls this endpoint
# ============================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def device_led_commands(request):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": "Valid device authentication is required."
            },
            status=401
        )

    now = timezone.now()

    # --------------------------------------------------------
    # EXPIRE OLD COMMANDS
    # --------------------------------------------------------

    LEDCommand.objects.filter(
        status="pending",
        expires_at__lte=now
    ).update(
        status="expired"
    )

    # --------------------------------------------------------
    # GET PENDING COMMANDS
    # --------------------------------------------------------

    commands = (
        LEDCommand.objects
        .filter(
            status="pending",
            expires_at__gt=now
        )
        .select_related(
            "led",
            "parking_slot"
        )
        .order_by(
            "created_at",
            "id"
        )
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response({

        "commands": [

            {
                "id": command.id,

                "led_id": command.led_id,

                "slot_number": (
                    command.parking_slot.slot_number
                ),

                "led_name": (
                    command.led.led_name
                ),

                "action": command.action,

                "status": command.status,

                "created_at": command.created_at,

                "expires_at": command.expires_at,
            }

            for command in commands
        ]

    })


# ============================================================
# CLAIM LED COMMAND
# Raspberry Pi claims a pending command
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def device_claim_led_command(
    request,
    command_id
):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": "Valid device authentication is required."
            },
            status=401
        )

    # --------------------------------------------------------
    # FIND COMMAND
    # --------------------------------------------------------

    try:

        command = (
            LEDCommand.objects
            .select_related(
                "led",
                "parking_slot"
            )
            .get(
                id=command_id
            )
        )

    except LEDCommand.DoesNotExist:

        return Response(
            {
                "error": "LED command not found."
            },
            status=404
        )

    # --------------------------------------------------------
    # CHECK STATUS
    # --------------------------------------------------------

    if command.status != "pending":

        return Response(
            {
                "error": (
                    f"LED command is already "
                    f"{command.status}."
                )
            },
            status=409
        )

    # --------------------------------------------------------
    # CHECK EXPIRATION
    # --------------------------------------------------------

    if command.expires_at <= timezone.now():

        command.status = "expired"

        command.save(
            update_fields=[
                "status"
            ]
        )

        return Response(
            {
                "error": "LED command has expired."
            },
            status=409
        )

    # --------------------------------------------------------
    # CLAIM COMMAND
    # --------------------------------------------------------

    command.status = "executing"

    command.acknowledged_at = timezone.now()

    command.save(
        update_fields=[
            "status",
            "acknowledged_at"
        ]
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response({

        "id": command.id,

        "led_id": command.led_id,

        "slot_number": (
            command.parking_slot.slot_number
        ),

        "led_name": (
            command.led.led_name
        ),

        "action": command.action,

        "status": command.status,

        "expires_at": command.expires_at,

    })


# ============================================================
# ACKNOWLEDGE LED COMMAND
# Raspberry Pi reports execution result
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def device_acknowledge_led_command(
    request,
    command_id
):

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION
    # --------------------------------------------------------

    if not _device_api_key_is_valid(request):

        return Response(
            {
                "error": "Valid device authentication is required."
            },
            status=401
        )

    # --------------------------------------------------------
    # GET RESULT STATUS
    # --------------------------------------------------------

    result_status = request.data.get(
        "status",
        ""
    )

    # --------------------------------------------------------
    # VALIDATE RESULT STATUS
    # --------------------------------------------------------

    if result_status not in [
        "succeeded",
        "failed"
    ]:

        return Response(
            {
                "error": (
                    "Acknowledgement status must be "
                    "succeeded or failed."
                )
            },
            status=400
        )

    # --------------------------------------------------------
    # FIND COMMAND
    # --------------------------------------------------------

    try:

        command = (
            LEDCommand.objects
            .select_related(
                "led",
                "parking_slot"
            )
            .get(
                id=command_id
            )
        )

    except LEDCommand.DoesNotExist:

        return Response(
            {
                "error": "LED command not found."
            },
            status=404
        )

    # --------------------------------------------------------
    # VALIDATE COMMAND STATUS
    # --------------------------------------------------------

    if command.status not in [
        "executing",
        "pending"
    ]:

        return Response(
            {
                "error": (
                    "LED command cannot be acknowledged "
                    f"because its current status is "
                    f"{command.status}."
                )
            },
            status=409
        )

    # --------------------------------------------------------
    # ERROR MESSAGE
    # --------------------------------------------------------

    error_message = request.data.get(
        "error",
        ""
    )

    # --------------------------------------------------------
    # UPDATE COMMAND
    # --------------------------------------------------------

    command.status = result_status

    command.completed_at = timezone.now()

    command.error_message = error_message

    command.save(
        update_fields=[
            "status",
            "completed_at",
            "error_message"
        ]
    )

    # ========================================================
    # UPDATE ACTUAL LED DATABASE STATUS
    # ========================================================

    if result_status == "succeeded":

        if command.action == "on":

            command.led.status = "on"

        elif command.action == "off":

            command.led.status = "off"

        command.led.save(
            update_fields=[
                "status",
                "updated_at"
            ]
        )

        # ----------------------------------------------------
        # SYSTEM EVENT
        # ----------------------------------------------------

        SystemEvent.objects.create(

            event_type="other",

            source="raspberry_pi_led",

            description=(
                f"LED {command.led.led_name} "
                f"turned {command.action.upper()} "
                f"for parking slot "
                f"{command.parking_slot.slot_number}."
            ),

            parking_slot=command.parking_slot
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    return Response({

        "id": command.id,

        "led_id": command.led_id,

        "slot_number": (
            command.parking_slot.slot_number
        ),

        "led_name": (
            command.led.led_name
        ),

        "action": command.action,

        "status": command.status,

        "physical_led_status": (
            command.led.status
        ),

    })


# ============================================================
# CREATE LED COMMAND
# Admin manually creates an LED command
# ============================================================

@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_led_command(request):

    # --------------------------------------------------------
    # GET REQUEST DATA
    # --------------------------------------------------------

    slot_number = request.data.get(
        "slot_number"
    )

    led_name = request.data.get(
        "led_name"
    )

    action = request.data.get(
        "action"
    )

    # --------------------------------------------------------
    # VALIDATE SLOT
    # --------------------------------------------------------

    if not slot_number:

        return Response(
            {
                "error": "slot_number is required."
            },
            status=400
        )

    # --------------------------------------------------------
    # VALIDATE LED NAME
    # --------------------------------------------------------

    if not led_name:

        return Response(
            {
                "error": "led_name is required."
            },
            status=400
        )

    # --------------------------------------------------------
    # VALIDATE ACTION
    # --------------------------------------------------------

    if action not in [
        "on",
        "off"
    ]:

        return Response(
            {
                "error": (
                    "action must be 'on' or 'off'."
                )
            },
            status=400
        )

    # --------------------------------------------------------
    # FIND PARKING SLOT
    # --------------------------------------------------------

    try:

        parking_slot = ParkingSlot.objects.get(
            slot_number=slot_number
        )

    except ParkingSlot.DoesNotExist:

        return Response(
            {
                "error": (
                    f"Parking slot "
                    f"{slot_number} not found."
                )
            },
            status=404
        )

    # --------------------------------------------------------
    # FIND LED
    # --------------------------------------------------------

    try:

        led = ParkingLED.objects.get(
            parking_slot=parking_slot,
            led_name=led_name
        )

    except ParkingLED.DoesNotExist:

        return Response(
            {
                "error": (
                    f"LED {led_name} does not exist "
                    f"for slot {slot_number}."
                )
            },
            status=404
        )

    # --------------------------------------------------------
    # CREATE COMMAND
    # --------------------------------------------------------

    now = timezone.now()

    command = LEDCommand.objects.create(

        led=led,

        parking_slot=parking_slot,

        action=action,

        status="pending",

        requested_via="admin",

        expires_at=(
            now +
            timezone.timedelta(
                seconds=30
            )
        )

    )

    # --------------------------------------------------------
    # SYSTEM EVENT
    # --------------------------------------------------------

    SystemEvent.objects.create(

        event_type="admin_action",

        source="admin_led",

        description=(
            f"Admin requested LED "
            f"{led.led_name} to turn "
            f"{action.upper()} for "
            f"parking slot "
            f"{slot_number}."
        ),

        user=request.user,

        parking_slot=parking_slot

    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return Response({

        "message": "LED command created.",

        "id": command.id,

        "slot_number": (
            parking_slot.slot_number
        ),

        "led_name": (
            led.led_name
        ),

        "action": action,

        "status": command.status,

        "expires_at": command.expires_at,

    })