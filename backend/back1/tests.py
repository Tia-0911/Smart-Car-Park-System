from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import (
    Alert,
    Booking,
    Emergency,
    EmergencyNotification,
    Gate,
    GateCommand,
    ParkingRate,
    ParkingSlot,
    SensorData,
    SensorReadingHistory,
    SystemEvent,
    Transaction,
    Wallet,
)
from .services import (
    availability,
    calculate_normal_price,
    create_pending_booking,
    expire_stale_pending_bookings,
    pay_booking,
    send_booking_confirmation,
    usable_parking_spaces,
    entrance_access_allowed,
    pay_overstay,
    process_booking_reminders,
    process_overstays,
    request_customer_gate,
    sensor_is_online,
    monitored_sensor_status,
    update_logical_sensor,
    process_sensor_alerts,
    send_emergency_notifications,
    finalize_overstay,
    cancel_customer_booking,
    cancellation_quote,
    booking_range_has_ended,
    booking_bounds,
    create_gate_command,
)
from .forms import AdminBookingForm, AdminCustomerForm


@override_settings(SENSOR_DEVICE_API_KEY="gate-device-key", GATE_COMMAND_EXPIRY_SECONDS=60)
class RaspberryPiGateCommandTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="gate-admin", password="pw", is_staff=True
        )
        self.customer = User.objects.create_user(
            username="gate-customer", password="pw"
        )
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.entrance = Gate.objects.get(gate_type="entrance")
        self.exit = Gate.objects.get(gate_type="exit")
        self.booking = Booking.objects.create(
            user=self.customer,
            parking_slot=self.slot,
            booking_date=timezone.localdate(),
            start_time=time(0),
            end_time=time(23, 59),
            status="confirmed",
            payment_status="paid",
            outstanding_balance=Decimal("0.00"),
        )
        self.device_headers = {"HTTP_X_DEVICE_API_KEY": "gate-device-key"}

    def _claim(self, command):
        return self.client.post(
            reverse("back1:device-claim-gate-command", args=[command.id]),
            **self.device_headers,
        )

    def _acknowledge(self, command, status_value, error=""):
        return self.client.post(
            reverse("back1:device-acknowledge-gate-command", args=[command.id]),
            {"status": status_value, "error": error},
            content_type="application/json",
            **self.device_headers,
        )

    def test_admin_open_and_close_create_one_hardware_command_each(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(reverse("back1:open_gate", args=[self.entrance.id])).status_code,
            200,
        )
        self.client.post(reverse("back1:open_gate", args=[self.entrance.id]))
        self.assertEqual(
            GateCommand.objects.filter(gate=self.entrance, action="open").count(), 1
        )
        open_command = GateCommand.objects.get(gate=self.entrance, action="open")
        self.assertEqual(open_command.requested_via, "admin")
        self.assertEqual(open_command.requested_by_user, self.admin)

        self.assertEqual(
            self.client.post(reverse("back1:close_gate", args=[self.entrance.id])).status_code,
            200,
        )
        close_command = GateCommand.objects.get(gate=self.entrance, action="close")
        self.assertEqual(close_command.requested_via, "admin")

    def test_customer_entrance_authorization_controls_command_creation(self):
        self.client.force_login(self.customer)
        url = reverse(
            "back1:customer-gate-request", args=[self.booking.id, "entrance"]
        )
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertFalse(GateCommand.objects.exists())

        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected")
        self.assertEqual(self.client.post(url).status_code, 200)
        command = GateCommand.objects.get()
        self.assertEqual((command.action, command.requested_via), ("open", "customer"))
        self.assertEqual(command.booking, self.booking)

    def test_customer_exit_authorization_and_outstanding_balance(self):
        self.booking.status = "overtime"
        self.booking.outstanding_balance = Decimal("20.00")
        self.booking.save(update_fields=["status", "outstanding_balance"])
        update_logical_sensor(sensor_id="EXIT_01", value="detected")
        self.client.force_login(self.customer)
        url = reverse("back1:customer-gate-request", args=[self.booking.id, "exit"])
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertFalse(GateCommand.objects.exists())

        self.booking.outstanding_balance = Decimal("0.00")
        self.booking.save(update_fields=["outstanding_balance"])
        self.assertEqual(self.client.post(url).status_code, 200)
        command = GateCommand.objects.get()
        self.assertEqual((command.gate, command.action), (self.exit, "open"))

    def test_lifecycle_clear_creates_close_command(self):
        self.booking.entrance_gate_opened_at = timezone.now()
        self.booking.save(update_fields=["entrance_gate_opened_at"])
        self.entrance.is_open = True
        self.entrance.save(update_fields=["is_open"])
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected")
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear")
        command = GateCommand.objects.get(gate=self.entrance, action="close")
        self.assertEqual(command.requested_via, "lifecycle")
        self.assertEqual(command.booking, self.booking)

    def test_device_auth_fetch_and_claim_is_single_use(self):
        command, _ = create_gate_command(
            gate=self.entrance, action="open", requested_via="admin"
        )
        url = reverse("back1:device-gate-commands")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(
            self.client.get(url, HTTP_X_DEVICE_API_KEY="wrong").status_code, 401
        )
        response = self.client.get(url, **self.device_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["commands"][0]["id"], command.id)
        self.assertEqual(self._claim(command).status_code, 200)
        self.assertEqual(self._claim(command).status_code, 409)
        self.assertEqual(
            self.client.get(url, **self.device_headers).json()["commands"], []
        )

    def test_success_acknowledgement_is_idempotent_and_updates_physical_state(self):
        command, _ = create_gate_command(
            gate=self.entrance, action="open", requested_via="admin"
        )
        self._claim(command)
        first = self._acknowledge(command, "succeeded")
        retry = self._acknowledge(command, "succeeded")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["changed"])
        self.assertEqual(retry.status_code, 200)
        self.assertFalse(retry.json()["changed"])
        command.refresh_from_db(); self.entrance.refresh_from_db()
        self.assertEqual(command.status, "succeeded")
        self.assertTrue(self.entrance.is_physically_open)
        self.assertEqual(
            SystemEvent.objects.filter(source="gate_hardware").count(), 1
        )

        close_command, _ = create_gate_command(
            gate=self.entrance, action="close", requested_via="lifecycle"
        )
        self._claim(close_command)
        self._acknowledge(close_command, "succeeded")
        self.entrance.refresh_from_db()
        self.assertFalse(self.entrance.is_physically_open)

    def test_failure_records_reason_without_changing_physical_state(self):
        self.entrance.is_physically_open = False
        self.entrance.save(update_fields=["is_physically_open"])
        command, _ = create_gate_command(
            gate=self.entrance, action="open", requested_via="admin"
        )
        self._claim(command)
        response = self._acknowledge(command, "failed", "Servo timeout")
        self.assertEqual(response.status_code, 200)
        command.refresh_from_db(); self.entrance.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(command.error_message, "Servo timeout")
        self.assertFalse(self.entrance.is_physically_open)
        event = SystemEvent.objects.get(source="gate_hardware")
        self.assertIn("Servo timeout", event.description)
        self.assertFalse(Alert.objects.exists())

    def test_expired_command_is_not_returned_or_acknowledged(self):
        command = GateCommand.objects.create(
            gate=self.entrance,
            action="open",
            requested_via="admin",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.get(
            reverse("back1:device-gate-commands"), **self.device_headers
        )
        self.assertEqual(response.json()["commands"], [])
        command.refresh_from_db()
        self.assertEqual(command.status, "expired")
        self.assertEqual(self._claim(command).status_code, 409)
        self.assertEqual(self._acknowledge(command, "succeeded").status_code, 409)

    def test_unresolved_identical_commands_are_deduplicated(self):
        first, created = create_gate_command(
            gate=self.entrance, action="open", requested_via="admin"
        )
        second, created_again = create_gate_command(
            gate=self.entrance, action="open", requested_via="customer",
            booking=self.booking, requested_by_user=self.customer,
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(GateCommand.objects.count(), 1)


class PartCAdminManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="part-c-admin", password="pw", is_staff=True)
        self.customer = User.objects.create_user(username="part-c-customer", password="pw", email="affected@example.com")
        self.other = User.objects.create_user(username="part-c-history", password="pw", email="history@example.com")
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.day = timezone.localdate() + timedelta(days=2)
        self.booking = Booking.objects.create(user=self.customer, parking_slot=self.slot, booking_date=self.day, start_time=time(10), end_time=time(11), status="confirmed", payment_status="paid")

    def test_admin_booking_list_and_customer_denial(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-bookings"), {"date": self.day.isoformat()})
        self.assertContains(response, self.customer.username)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("back1:admin-bookings")).status_code, 403)

    def test_admin_booking_form_ignores_self_conflict_and_rejects_other_conflict(self):
        payload = {"booking_date": self.day, "start_time": "10:00", "end_time": "11:00", "parking_slot": self.slot.id, "status": "confirmed"}
        self.assertTrue(AdminBookingForm(payload, instance=self.booking).is_valid())
        Booking.objects.create(user=self.other, parking_slot=self.slot, booking_date=self.day, start_time=time(11), end_time=time(12), status="confirmed")
        payload["end_time"] = "11:30"
        form = AdminBookingForm(payload, instance=self.booking)
        self.assertFalse(form.is_valid())
        self.assertIn("conflicts", str(form.errors))

    def test_admin_booking_rejects_unusable_space_and_protects_completed(self):
        self.slot.is_under_maintenance = True; self.slot.save(update_fields=["is_under_maintenance"])
        form = AdminBookingForm({"booking_date": self.day, "start_time": "10:00", "end_time": "11:00", "parking_slot": self.slot.id, "status": "confirmed"}, instance=self.booking)
        self.assertFalse(form.is_valid())
        self.slot.is_under_maintenance = False; self.slot.save(update_fields=["is_under_maintenance"])
        self.booking.status = "completed"; self.booking.save(update_fields=["status"])
        form = AdminBookingForm({"booking_date": self.day + timedelta(days=1), "start_time": "10:00", "end_time": "11:00", "parking_slot": self.slot.id, "status": "completed"}, instance=self.booking)
        self.assertFalse(form.is_valid())

    def test_delete_financial_booking_soft_cancels_and_preserves_history(self):
        Transaction.objects.create(user=self.customer, booking=self.booking, transaction_type="payment", amount=Decimal("2"), payment_category="normal", payment_status="paid")
        self.client.force_login(self.admin)
        self.client.post(reverse("back1:admin-booking-delete", args=[self.booking.id]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "cancelled")
        self.assertTrue(Transaction.objects.filter(booking=self.booking).exists())
        self.assertTrue(SystemEvent.objects.filter(source="admin_booking").exists())

    def test_customer_form_cannot_elevate_and_history_causes_deactivation(self):
        form = AdminCustomerForm({"first_name": "Changed", "last_name": "User", "email": "new@example.com", "is_active": "on", "is_staff": "on"}, instance=self.customer)
        self.assertTrue(form.is_valid()); updated = form.save()
        self.assertFalse(updated.is_staff)
        self.client.force_login(self.admin)
        self.client.post(reverse("back1:admin-customer-delete", args=[self.customer.id]))
        self.customer.refresh_from_db(); self.assertFalse(self.customer.is_active)
        self.assertTrue(Booking.objects.filter(pk=self.booking.id).exists())

    def test_staff_account_not_available_in_customer_management(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("back1:admin-customer-edit", args=[self.admin.id])).status_code, 404)

    def test_offline_abnormal_and_recovery_alert_lifecycle(self):
        now = timezone.now()
        sensor, _ = update_logical_sensor(sensor_id="PARK_A04", value="clear", now=now - timedelta(seconds=601))
        process_sensor_alerts(now=now)
        self.assertEqual(Alert.objects.filter(sensor=sensor, alert_type="sensor_offline", acknowledged=False).count(), 1)
        process_sensor_alerts(now=now)
        self.assertEqual(Alert.objects.filter(sensor=sensor, alert_type="sensor_offline").count(), 1)
        update_logical_sensor(sensor_id="PARK_A04", value="clear", condition_status="normal", now=now)
        self.assertFalse(Alert.objects.filter(sensor=sensor, acknowledged=False).exists())
        self.assertTrue(SystemEvent.objects.filter(source="sensor_recovery").exists())

    def test_emergency_transition_is_idempotent_and_critical(self):
        now = timezone.now()
        update_logical_sensor(sensor_id="EMERGENCY_01", value="detected", now=now)
        update_logical_sensor(sensor_id="EMERGENCY_01", value="detected", now=now + timedelta(seconds=1))
        self.assertEqual(Emergency.objects.filter(status="active").count(), 1)
        self.assertEqual(Alert.objects.filter(alert_type="emergency", severity="critical", acknowledged=False).count(), 1)
        self.assertEqual(SystemEvent.objects.filter(description="Emergency sensor activated.").count(), 1)

    def test_admin_acknowledges_alert_customer_cannot(self):
        sensor = SensorData.objects.get(sensor_id="PARK_A01")
        alert = Alert.objects.create(alert_type="sensor_abnormal", severity="warning", message="test", sensor=sensor)
        url = reverse("back1:acknowledge-alert", args=[alert.id])
        self.client.force_login(self.customer); self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.admin); self.assertEqual(self.client.post(url).status_code, 200)
        alert.refresh_from_db(); self.assertEqual(alert.acknowledged_by, self.admin)

    def test_emergency_notification_only_targets_affected_customers(self):
        emergency = Emergency.objects.create(emergency_type="fire", description="Evacuate", status="active")
        self.booking.status = "active"; self.booking.save(update_fields=["status"])
        Booking.objects.create(user=self.other, parking_slot=ParkingSlot.objects.get(slot_number="A02"), booking_date=self.day - timedelta(days=10), start_time=time(10), end_time=time(11), status="completed")
        notifications = send_emergency_notifications(emergency=emergency, admin=self.admin, message="Please leave safely")
        self.assertEqual([item.recipient for item in notifications], [self.customer])
        self.assertEqual(notifications[0].status, "sent")
        self.assertEqual(notifications[0].sent_by, self.admin)

    def test_event_log_newest_first_and_customer_denied(self):
        old = SystemEvent.objects.create(event_type="other", source="test", description="old", timestamp=timezone.now() - timedelta(minutes=1))
        new = SystemEvent.objects.create(event_type="other", source="test", description="new")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-events"))
        events = list(response.context["page_obj"].object_list)
        self.assertLess(events.index(new), events.index(old))
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("back1:admin-events")).status_code, 403)

    def test_admin_dashboard_uses_real_events_and_no_demo_customers(self):
        SystemEvent.objects.create(event_type="other", source="real", description="Real operational event")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertContains(response, "Real operational event")
        self.assertNotContains(response, "Customer: John")
        self.assertNotContains(response, "Customer: Anna")


class PartDFinalSecurityAuditTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="security-a", password="pw", email="a@example.com")
        self.other = User.objects.create_user(username="security-b", password="pw", email="b@example.com")
        self.admin = User.objects.create_user(username="security-admin", password="pw", is_staff=True)
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.booking = Booking.objects.create(
            user=self.other, parking_slot=self.slot,
            booking_date=timezone.localdate() + timedelta(days=1),
            start_time=time(10), end_time=time(11), status="pending", payment_status="pending",
            pending_expires_at=timezone.now() + timedelta(minutes=15),
        )
        Wallet.objects.create(user=self.customer, balance=Decimal("20"))
        Wallet.objects.create(user=self.other, balance=Decimal("20"))

    def test_anonymous_private_browser_and_api_matrix(self):
        browser_routes = [
            reverse("back1:customer-dashboard"), reverse("back1:bookings"),
            reverse("back1:booking-create"), reverse("back1:profile"),
            reverse("back1:admin-dashboard"), reverse("back1:admin-bookings"),
            reverse("back1:admin-customers"), reverse("back1:admin-events"),
        ]
        for url in browser_routes:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        api_routes = [
            reverse("back1:booking_list"), reverse("back1:gates_api"),
            reverse("back1:dashboard_sensor_status"),
            reverse("back1:wallet_detail", args=[self.customer.id]),
        ]
        for url in api_routes:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_customer_admin_separation_matrix(self):
        self.client.force_login(self.customer)
        denied = [
            reverse("back1:admin-dashboard"), reverse("back1:admin-bookings"),
            reverse("back1:admin-customers"), reverse("back1:admin-events"),
            reverse("back1:gates_api"), reverse("back1:emergency_list"),
        ]
        for url in denied:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_cross_customer_idor_is_denied_for_all_booking_actions(self):
        self.client.force_login(self.customer)
        urls = [
            reverse("back1:booking-payment", args=[self.booking.id]),
            reverse("back1:booking-success", args=[self.booking.id]),
            reverse("back1:overstay-payment", args=[self.booking.id]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        post_urls = [
            reverse("back1:cancel_booking", args=[self.booking.id]),
            reverse("back1:customer-gate-request", args=[self.booking.id, "entrance"]),
            reverse("back1:customer-gate-request", args=[self.booking.id, "exit"]),
        ]
        for url in post_urls:
            self.assertIn(self.client.post(url).status_code, [403, 404], url)

    @override_settings(SENSOR_DEVICE_API_KEY="isolated-device-key")
    def test_device_key_only_authorizes_sensor_endpoint(self):
        response = self.client.post(reverse("back1:device-sensor-update"), {"sensor_id": "PARK_A01", "value": "clear"}, HTTP_X_DEVICE_API_KEY="isolated-device-key")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("back1:admin-bookings"), HTTP_X_DEVICE_API_KEY="isolated-device-key").status_code, 302)
        self.assertEqual(self.client.post(reverse("back1:open_gate", args=[Gate.objects.get(gate_type="entrance").id]), HTTP_X_DEVICE_API_KEY="isolated-device-key").status_code, 401)

    def test_mass_assignment_fields_are_ignored_by_booking_api(self):
        self.client.force_login(self.customer)
        malicious_slot = ParkingSlot.objects.get(slot_number="A06")
        response = self.client.post(reverse("back1:create_booking"), {
            "booking_date": timezone.localdate() + timedelta(days=2),
            "start_time": "10:00", "end_time": "11:00",
            "parking_slot": malicious_slot.id, "user": self.other.id,
            "status": "confirmed", "payment_status": "paid",
            "normal_parking_amount": "0.01", "outstanding_balance": "0",
            "confirmation_email_sent": "true",
        })
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(pk=response.json()["booking_id"])
        self.assertEqual(booking.user, self.customer)
        self.assertEqual(booking.parking_slot.slot_number, "A01")
        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.payment_status, "pending")
        self.assertEqual(booking.normal_parking_amount, Decimal("2.00"))
        self.assertFalse(booking.confirmation_email_sent)

    def test_legacy_lifecycle_endpoints_cannot_bypass_validated_flow(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("back1:car_entry", args=[self.booking.id])).status_code, 410)
        self.assertEqual(self.client.post(reverse("back1:car_exit", args=[self.booking.id])).status_code, 410)
        self.booking.refresh_from_db(); self.assertEqual(self.booking.status, "pending")

    def test_wallet_top_up_rejects_zero_negative_and_non_finite(self):
        self.client.force_login(self.customer)
        url = reverse("back1:add_wallet_balance", args=[self.customer.id])
        for amount in ["0", "-1", "NaN", "Infinity"]:
            self.assertEqual(self.client.post(url, {"amount": amount}).status_code, 400)
        self.assertEqual(Wallet.objects.get(user=self.customer).balance, Decimal("20"))

    def test_normal_browser_post_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.customer)
        response = csrf_client.post(reverse("back1:profile"), {"first_name": "Bypass", "last_name": "", "email": "a@example.com"})
        self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db(); self.assertNotEqual(self.customer.first_name, "Bypass")

    def test_mutating_routes_reject_get(self):
        self.client.force_login(self.admin)
        alert = Alert.objects.create(alert_type="other", severity="info", message="method")
        routes = [
            reverse("back1:admin-booking-delete", args=[self.booking.id]),
            reverse("back1:admin-customer-delete", args=[self.customer.id]),
            reverse("back1:acknowledge-alert", args=[alert.id]),
            reverse("back1:open_gate", args=[Gate.objects.get(gate_type="entrance").id]),
            reverse("back1:resolve_emergency", args=[Emergency.objects.create(emergency_type="fire", description="x").id]),
        ]
        for url in routes:
            self.assertIn(self.client.get(url).status_code, [405], url)


class AdminDashboardRealSummaryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="summary-admin", password="pw", is_staff=True
        )
        self.customer = User.objects.create_user(username="summary-customer", password="pw")
        self.slots = {
            slot.slot_number: slot
            for slot in ParkingSlot.objects.order_by("slot_number")
        }

    def test_summary_context_uses_current_capacity_and_paid_transactions(self):
        ParkingSlot.objects.update(
            is_enabled=True,
            is_under_maintenance=False,
            is_backup=False,
            is_physically_occupied=False,
            status="available",
        )
        ParkingSlot.objects.filter(slot_number="A02").update(is_physically_occupied=True)
        ParkingSlot.objects.filter(slot_number="A03").update(is_under_maintenance=True)
        ParkingSlot.objects.filter(slot_number="A04").update(is_backup=True)
        ParkingSlot.objects.filter(slot_number="A05").update(is_enabled=False)

        today = timezone.localdate()
        Booking.objects.create(
            user=self.customer,
            parking_slot=self.slots["A06"],
            booking_date=today,
            start_time=time(0, 0),
            end_time=time(23, 59),
            status="confirmed",
            payment_status="paid",
        )
        Booking.objects.create(
            user=self.customer,
            parking_slot=self.slots["A01"],
            booking_date=today + timedelta(days=1),
            start_time=time(10),
            end_time=time(11),
            status="pending",
            payment_status="pending",
            pending_expires_at=timezone.now() + timedelta(minutes=10),
        )
        stale = Booking.objects.create(
            user=self.customer,
            parking_slot=self.slots["A01"],
            booking_date=today + timedelta(days=2),
            start_time=time(10),
            end_time=time(11),
            status="pending",
            payment_status="pending",
            pending_expires_at=timezone.now() - timedelta(minutes=1),
        )

        Transaction.objects.create(
            user=self.customer, transaction_type="payment", payment_category="normal",
            payment_status="paid", amount=Decimal("16.00"), paid_at=timezone.now(),
        )
        Transaction.objects.create(
            user=self.customer, transaction_type="payment", payment_category="normal",
            payment_status="pending", amount=Decimal("99.00"),
        )
        Transaction.objects.create(
            user=self.customer, transaction_type="penalty", payment_category="overstay",
            payment_status="paid", amount=Decimal("40.00"), paid_at=timezone.now(),
        )
        Transaction.objects.create(
            user=self.customer, transaction_type="penalty", payment_category="overstay",
            payment_status="outstanding", amount=Decimal("80.00"),
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"))

        self.assertEqual(response.context["total_slots"], 6)
        self.assertEqual(response.context["available_slots"], 1)
        self.assertEqual(response.context["occupied_slots"], 1)
        self.assertEqual(response.context["booking_count"], 1)
        self.assertEqual(response.context["parking_revenue"], Decimal("16.00"))
        self.assertEqual(response.context["penalty_revenue"], Decimal("40.00"))
        self.assertEqual(response.context["total_revenue"], Decimal("56.00"))
        stale.refresh_from_db()
        self.assertEqual(stale.status, "expired")

    def test_progress_widths_follow_real_percentages_including_zero(self):
        ParkingSlot.objects.update(
            is_enabled=True, is_under_maintenance=False, is_backup=False,
            is_physically_occupied=False, status="available",
        )
        self.client.force_login(self.admin)

        ParkingSlot.objects.filter(slot_number__in=["A05", "A06"]).update(is_enabled=False)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertEqual(response.context["availability_percentage"], 66)
        self.assertEqual(response.context["occupancy_percentage"], 0)
        self.assertContains(response, 'style="width:66%;"')
        self.assertContains(response, 'style="width:0%;"')

        ParkingSlot.objects.update(is_enabled=True)
        ParkingSlot.objects.filter(slot_number__in=["A01", "A02", "A03"]).update(
            is_physically_occupied=True
        )
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertEqual(response.context["availability_percentage"], 50)
        self.assertEqual(response.context["occupancy_percentage"], 50)
        self.assertContains(response, 'style="width:50%;"', count=2)

        ParkingSlot.objects.update(is_physically_occupied=True)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertEqual(response.context["availability_percentage"], 0)
        self.assertEqual(response.context["occupancy_percentage"], 100)
        self.assertContains(response, 'style="width:0%;"')
        self.assertContains(response, 'style="width:100%;"')

        ParkingSlot.objects.all().delete()
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertEqual(response.context["availability_percentage"], 0)
        self.assertEqual(response.context["occupancy_percentage"], 0)
        self.assertContains(response, 'style="width:0%;"', count=2)

    def test_viewing_date_filters_supported_daily_sections(self):
        selected = timezone.localdate() - timedelta(days=2)
        other = selected + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.customer, parking_slot=self.slots["A01"], booking_date=selected,
            start_time=time(10), end_time=time(11), status="confirmed", payment_status="paid",
        )
        Booking.objects.create(
            user=self.customer, parking_slot=self.slots["A02"], booking_date=other,
            start_time=time(10), end_time=time(11), status="confirmed", payment_status="paid",
        )
        selected_at = timezone.make_aware(datetime.combine(selected, time(12)))
        other_at = timezone.make_aware(datetime.combine(other, time(12)))
        Transaction.objects.create(
            user=self.customer, booking=booking, transaction_type="payment",
            payment_category="normal", payment_status="paid", amount=Decimal("6.00"), paid_at=selected_at,
        )
        Transaction.objects.create(
            user=self.customer, transaction_type="penalty", payment_category="overstay",
            payment_status="paid", amount=Decimal("20.00"), paid_at=selected_at,
        )
        Transaction.objects.create(
            user=self.customer, transaction_type="payment", payment_category="normal",
            payment_status="paid", amount=Decimal("99.00"), paid_at=other_at,
        )
        SystemEvent.objects.create(timestamp=selected_at, source="date-test", description="Selected activity")
        SystemEvent.objects.create(timestamp=other_at, source="date-test", description="Other activity")

        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"), {"date": selected.isoformat()})
        self.assertEqual(response.context["viewing_date"], selected)
        self.assertEqual(response.context["booking_count"], 1)
        self.assertEqual(list(response.context["recent_bookings"]), [booking])
        self.assertEqual(response.context["parking_revenue"], Decimal("6.00"))
        self.assertEqual(response.context["penalty_revenue"], Decimal("20.00"))
        self.assertEqual(response.context["total_revenue"], Decimal("26.00"))
        self.assertContains(response, "Selected activity")
        self.assertNotContains(response, "Other activity")

        today_response = self.client.get(reverse("back1:admin-dashboard"))
        invalid_response = self.client.get(reverse("back1:admin-dashboard"), {"date": "not-a-date"})
        self.assertEqual(today_response.context["viewing_date"], timezone.localdate())
        self.assertEqual(invalid_response.context["viewing_date"], timezone.localdate())

    def test_last_sync_and_polling_payload_use_only_emergency_sensor_timestamps(self):
        base = timezone.now() - timedelta(minutes=8)
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="24.5", now=base)
        update_logical_sensor(sensor_id="HUMIDITY_01", value="58", now=base + timedelta(minutes=1))
        latest = base + timedelta(minutes=2)
        update_logical_sensor(sensor_id="FIRE_01", value="normal", now=latest)
        update_logical_sensor(sensor_id="PARK_A01", value="clear", now=base + timedelta(minutes=7))
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=base + timedelta(minutes=7))

        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"), {"date": "2020-01-01"})
        self.assertEqual(response.context["latest_emergency_sync"], latest)
        self.assertTrue(timezone.is_aware(response.context["latest_emergency_sync"]))
        self.assertContains(response, "300000")

        api = self.client.get(reverse("back1:dashboard_sensor_status"))
        self.assertEqual(api.status_code, 200)
        payload = api.json()["dashboard"]
        self.assertEqual(payload["parking_failed_count"], 0)
        self.assertEqual(len(payload["sensors"]), 5)
        self.assertEqual(payload["latest_sync"], latest.isoformat().replace("+00:00", "Z"))
        values = {row["sensor_id"]: row for row in payload["sensors"]}
        self.assertEqual(values["TEMPERATURE_01"]["value"], "24.5°C")
        self.assertEqual(values["HUMIDITY_01"]["value"], "58%")
        self.assertEqual(values["FIRE_01"]["value"], "Normal")

    def test_last_sync_no_emergency_data(self):
        SensorData.objects.filter(sensor_id__in=["TEMPERATURE_01", "HUMIDITY_01", "FIRE_01"]).delete()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertIsNone(response.context["latest_emergency_sync"])
        self.assertContains(response, "No data yet")
        payload = self.client.get(reverse("back1:dashboard_sensor_status")).json()["dashboard"]
        self.assertIsNone(payload["latest_sync"])
        emergency = {row["sensor_id"]: row for row in payload["sensors"]}
        self.assertEqual(emergency["TEMPERATURE_01"]["display_status"], "NO DATA")
        self.assertEqual(emergency["HUMIDITY_01"]["display_status"], "NO DATA")
        self.assertEqual(emergency["FIRE_01"]["display_status"], "NO DATA")

    def test_live_parking_overview_maps_each_existing_effective_status(self):
        statuses = {
            "A01": "available", "A02": "occupied", "A03": "disabled",
            "A04": "backup", "A05": "maintenance", "A06": "reserved",
        }
        for slot_number, status in statuses.items():
            ParkingSlot.objects.filter(slot_number=slot_number).update(status=status)
        self.client.force_login(self.admin)

        today = self.client.get(reverse("back1:admin-dashboard"))
        historical = self.client.get(reverse("back1:admin-dashboard"), {"date": "2020-01-01"})
        for response in (today, historical):
            for slot_number, status in statuses.items():
                self.assertContains(
                    response,
                    f'class="real-slot parking-overview-link {status}"',
                )
            self.assertContains(response, "Available")
            self.assertContains(response, "Occupied")
            self.assertContains(response, "Disabled")
            self.assertContains(response, ">Backup<", html=False)
            self.assertContains(response, "Maintenance")
            self.assertContains(response, "Reserved")

    def test_parking_overview_gates_use_shared_live_gate_state(self):
        entrance = Gate.objects.get(gate_type="entrance")
        exit_gate = Gate.objects.get(gate_type="exit")
        entrance.is_open = True
        entrance.save(update_fields=["is_open", "updated_at"])
        exit_gate.is_open = False
        exit_gate.save(update_fields=["is_open", "updated_at"])
        self.client.force_login(self.admin)

        for response in (
            self.client.get(reverse("back1:admin-dashboard")),
            self.client.get(reverse("back1:admin-dashboard"), {"date": "2020-01-01"}),
        ):
            self.assertContains(response, 'class="parking-gate parking-overview-link gate-open" data-overview-gate="entrance"')
            self.assertContains(response, 'class="parking-gate parking-overview-link gate-closed" data-overview-gate="exit"')
            self.assertContains(response, "🔴 OPEN")
            self.assertContains(response, "🟢 CLOSED")
            self.assertContains(response, 'data-control-gate="entrance"')
            self.assertContains(response, 'data-control-gate="exit"')

        payload = self.client.get(reverse("back1:dashboard_sensor_status")).json()
        gates = {gate["gate_type"]: gate["is_open"] for gate in payload["gates"]}
        self.assertEqual(gates, {"entrance": True, "exit": False})

    def test_dashboard_navigation_preserves_date_and_uses_existing_destinations(self):
        selected = date(2026, 8, 10)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"), {"date": selected.isoformat()})
        bookings_url = reverse("back1:admin-bookings") + "?date=2026-08-10"
        events_url = reverse("back1:admin-events") + "?date=2026-08-10"
        self.assertContains(response, f'href="{bookings_url}"', count=2)
        self.assertContains(response, f'href="{events_url}"')
        self.assertContains(response, 'recent-card booking-card clickable-dashboard-card')
        self.assertContains(response, 'recent-card activity-card clickable-dashboard-card')
        self.assertContains(response, 'aria-label="View booking history for 10 Aug 2026"')
        self.assertContains(response, 'aria-label="View activity history for 10 Aug 2026"')
        self.assertNotContains(response, "View All →")
        self.assertNotContains(response, "View History →")
        self.assertContains(response, reverse("admin:back1_parkingslot_changelist"))
        self.assertContains(response, reverse("back1:admin-sensors"))
        for slot in ParkingSlot.objects.all():
            self.assertContains(response, reverse("admin:back1_parkingslot_change", args=[slot.id]))
        for gate in Gate.objects.all():
            self.assertContains(response, reverse("admin:back1_gate_change", args=[gate.id]))

    def test_date_aware_detail_lists_default_validate_and_navigate_independently(self):
        selected = timezone.localdate() - timedelta(days=3)
        selected_at = timezone.make_aware(datetime.combine(selected, time(12)))
        booking = Booking.objects.create(
            user=self.customer, parking_slot=self.slots["A01"], booking_date=selected,
            start_time=time(10), end_time=time(11), status="confirmed",
        )
        SystemEvent.objects.create(timestamp=selected_at, source="navigation", description="Selected event")
        self.client.force_login(self.admin)

        for route_name in ("back1:admin-bookings", "back1:admin-events"):
            direct = self.client.get(reverse(route_name))
            invalid = self.client.get(reverse(route_name), {"date": "invalid"})
            chosen = self.client.get(reverse(route_name), {"date": selected.isoformat()})
            self.assertEqual(direct.context["viewing_date"], timezone.localdate())
            self.assertEqual(invalid.context["viewing_date"], timezone.localdate())
            self.assertEqual(chosen.context["viewing_date"], selected)
            self.assertContains(chosen, f'?date={(selected - timedelta(days=1)).isoformat()}')
            self.assertContains(chosen, f'?date={(selected + timedelta(days=1)).isoformat()}')
            self.assertContains(chosen, f'value="{selected.isoformat()}"')

        bookings = self.client.get(reverse("back1:admin-bookings"), {"date": selected.isoformat()})
        events = self.client.get(reverse("back1:admin-events"), {"date": selected.isoformat()})
        self.assertContains(bookings, f"#{booking.id}")
        self.assertContains(events, "Selected event")

    def test_admin_history_pages_load_current_shared_styles_and_wrappers(self):
        self.client.force_login(self.admin)
        expected_classes = {
            "back1:admin-bookings": "history-filter-card",
            "back1:admin-revenue": "history-summary-grid",
            "back1:admin-sensors": "sensor-history-grid",
            "back1:admin-events": "event-history-card",
        }
        for route_name, page_class in expected_classes.items():
            response = self.client.get(
                reverse(route_name), {"date": "2026-08-12"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "/static/css/dashboard.css?v=13")
            self.assertContains(response, 'class="admin-history-page"')
            self.assertContains(response, page_class)

        sensors = self.client.get(
            reverse("back1:admin-sensors"), {"date": "2026-08-12"}
        )
        self.assertContains(sensors, "sensor-final-row", count=2)


class PartDCompleteCustomerE2ETests(TestCase):
    def test_registration_to_overstay_payment_and_completed_history(self):
        response = self.client.post(reverse("back1:register"), {
            "username": "e2e-customer", "first_name": "E2E", "last_name": "Customer",
            "email": "e2e@example.com", "password1": "Safe-test-password-908!",
            "password2": "Safe-test-password-908!",
        })
        self.assertRedirects(response, reverse("back1:customer-dashboard"))
        user = User.objects.get(username="e2e-customer")
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Safe-test-password-908!"))
        Wallet.objects.create(user=user, balance=Decimal("50.00"))

        ParkingSlot.objects.filter(slot_number="A05").update(is_under_maintenance=True)
        ParkingSlot.objects.filter(slot_number="A06").update(is_backup=True)
        day = timezone.localdate()
        for index in range(3):
            holder = User.objects.create_user(username=f"e2e-holder-{index}")
            Booking.objects.create(user=holder, parking_slot=ParkingSlot.objects.get(slot_number=f"A0{index + 1}"), booking_date=day, start_time=time(10), end_time=time(11), status="confirmed")
        self.assertTrue(availability(day, time(10), time(11))["available"])
        fourth = User.objects.create_user(username="e2e-holder-4")
        Booking.objects.create(user=fourth, parking_slot=ParkingSlot.objects.get(slot_number="A04"), booking_date=day, start_time=time(10), end_time=time(11), status="confirmed")
        self.assertFalse(availability(day, time(10), time(11))["available"])
        Booking.objects.filter(user__username__startswith="e2e-holder").delete()

        booking = create_pending_booking(user=user, booking_date=day, start_time=time(10), end_time=time(11))
        self.assertEqual(booking.parking_slot.slot_number, "A01")
        self.assertEqual(booking.normal_parking_amount, Decimal("2.00"))
        booking, charged = pay_booking(booking_id=booking.id, user=user)
        self.assertTrue(charged); self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("48.00"))
        self.assertTrue(send_booking_confirmation(booking)); self.assertFalse(send_booking_confirmation(booking))

        at_early = timezone.make_aware(datetime.combine(day, time(9, 54)))
        at_entry = timezone.make_aware(datetime.combine(day, time(9, 55)))
        with self.assertRaises(ValueError):
            request_customer_gate(booking_id=booking.id, user=user, gate_type="entrance", now=at_early)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=at_entry)
        with self.assertRaisesMessage(ValueError, "No vehicle"):
            request_customer_gate(booking_id=booking.id, user=user, gate_type="entrance", now=at_entry)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=at_entry)
        request_customer_gate(booking_id=booking.id, user=user, gate_type="entrance", now=at_entry)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=at_entry + timedelta(minutes=1))
        self.assertFalse(Gate.objects.get(gate_type="entrance").is_open)

        update_logical_sensor(sensor_id="PARK_A01", value="detected", now=timezone.make_aware(datetime.combine(day, time(10))))
        booking.refresh_from_db(); self.assertEqual(booking.status, "active")
        self.assertEqual(process_booking_reminders(now=timezone.make_aware(datetime.combine(day, time(10, 45)))), 1)
        self.assertEqual(process_booking_reminders(now=timezone.make_aware(datetime.combine(day, time(10, 46)))), 0)

        leave_time = timezone.make_aware(datetime.combine(day, time(11, 15)))
        process_overstays(now=leave_time)
        update_logical_sensor(sensor_id="PARK_A01", value="clear", now=leave_time)
        booking.refresh_from_db(); self.assertEqual(booking.outstanding_balance, Decimal("20.00"))
        update_logical_sensor(sensor_id="EXIT_01", value="detected", now=leave_time + timedelta(minutes=3))
        with self.assertRaisesMessage(ValueError, "Outstanding payment"):
            request_customer_gate(booking_id=booking.id, user=user, gate_type="exit", now=leave_time + timedelta(minutes=3))
        booking, charged = pay_overstay(booking_id=booking.id, user=user)
        self.assertTrue(charged); self.assertEqual(Wallet.objects.get(user=user).balance, Decimal("28.00"))
        self.assertFalse(Gate.objects.get(gate_type="exit").is_open)
        request_customer_gate(booking_id=booking.id, user=user, gate_type="exit", now=leave_time + timedelta(minutes=3))
        update_logical_sensor(sensor_id="EXIT_01", value="clear", now=leave_time + timedelta(minutes=4))
        booking.refresh_from_db()
        self.assertEqual(booking.status, "completed")
        self.assertIsNotNone(booking.completed_at); self.assertIsNotNone(booking.actual_exit_time)
        self.assertEqual(Transaction.objects.filter(booking=booking).count(), 2)
        dashboard = self.client.get(reverse("back1:customer-dashboard"))
        self.assertContains(dashboard, "No upcoming booking.")
        self.assertContains(self.client.get(reverse("back1:bookings")), "Past Bookings")


class SensorMonitoringPresentationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="sensor-admin", password="pw", is_staff=True)
        self.customer = User.objects.create_user(username="sensor-customer", password="pw")
        self.now = timezone.now()
        safe_values = {
            "TEMPERATURE_01": "24.5",
            "HUMIDITY_01": "58",
            "FIRE_01": "normal",
            "ENTRANCE_01": "clear",
            "EXIT_01": "clear",
            **{f"PARK_A0{i}": "clear" for i in range(1, 7)},
        }
        for sensor_id, value in safe_values.items():
            update_logical_sensor(sensor_id=sensor_id, value=value, now=self.now)

    def test_environment_values_conditions_and_alert_deduplication(self):
        temperature, _ = update_logical_sensor(sensor_id="TEMPERATURE_01", value="55", now=self.now)
        humidity = SensorData.objects.get(sensor_id="HUMIDITY_01")
        self.assertEqual(temperature.value, "55")
        self.assertEqual(temperature.condition_status, "abnormal")
        self.assertEqual(humidity.value, "58")
        self.assertEqual(humidity.condition_status, "normal")
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="55", now=self.now + timedelta(seconds=1))
        self.assertEqual(
            Alert.objects.filter(sensor=temperature, alert_type="sensor_abnormal", acknowledged=False).count(),
            1,
        )

    def test_fire_detection_is_distinct_from_fire_sensor_failure(self):
        fire, _ = update_logical_sensor(sensor_id="FIRE_01", value="fire detected", now=self.now)
        self.assertEqual(fire.condition_status, "abnormal")
        self.assertTrue(Alert.objects.filter(sensor=fire, alert_type="emergency", acknowledged=False).exists())
        rows = {row["sensor_id"]: row for row in monitored_sensor_status(now=self.now)}
        self.assertEqual(rows["FIRE_01"]["value_display"], "Fire Detected")
        self.assertFalse(rows["FIRE_01"]["failed"])
        self.assertTrue(rows["FIRE_01"]["abnormal"])

        rows = {row["sensor_id"]: row for row in monitored_sensor_status(now=self.now + timedelta(seconds=601))}
        self.assertTrue(rows["FIRE_01"]["failed"])
        self.assertIn("Sensor Failed", rows["FIRE_01"]["issue"])

    def test_admin_sensors_page_lists_all_required_devices(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-sensors"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Temperature Sensor")
        self.assertContains(response, "24.5°C")
        self.assertContains(response, "Humidity Sensor")
        self.assertContains(response, "58%")
        self.assertContains(response, "Fire Sensor")
        self.assertContains(response, "PARK_A01")
        self.assertContains(response, "PARK_A06")
        self.assertContains(response, "Entrance Sensor")
        self.assertContains(response, "Exit Sensor")

        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("back1:admin-sensors")).status_code, 403)

    def test_dashboard_emergency_summary_uses_current_sensor_issues(self):
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="55", now=self.now)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now - timedelta(seconds=601))
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertContains(response, "2 Active Issues")
        self.assertContains(response, "Temperature Sensor")
        self.assertContains(response, "55°C")
        self.assertContains(response, "UNSAFE")
        self.assertContains(response, "Entrance Sensor")
        self.assertContains(response, "FAILED")
        self.assertContains(response, "Parking Sensors A01–A06")
        self.assertContains(response, "🟢 ALL NORMAL")
        self.assertContains(response, 'class="emergency-sensor-item', count=6)
        self.assertContains(response, "Exit Sensor")
        self.assertNotContains(response, "🔥 Fire Detection")
        self.assertNotContains(response, "📡 Sensor Failure")
        self.assertNotContains(response, "🚧 Gate Failure")
        self.assertNotContains(response, "Immediate admin attention required")
        self.assertNotContains(response, "Review the current sensor issues below")

        update_logical_sensor(sensor_id="PARK_A03", value="clear", now=self.now - timedelta(seconds=601))
        update_logical_sensor(sensor_id="PARK_A05", value="clear", now=self.now - timedelta(seconds=601))
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertContains(response, "4 Active Issues")
        self.assertContains(response, 'class="emergency-sensor-value sensor-status-pill parking-live-status parking-failed-summary"')
        self.assertNotContains(response, "parking-failed-name")


class AdminNavigationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="nav-admin", password="pw", is_staff=True)
        self.client.force_login(self.admin)

    def test_admin_nav_structure_and_existing_routes(self):
        response = self.client.get(reverse("back1:admin-dashboard"))
        expected_links = {
            "Dashboard": reverse("back1:admin-dashboard"),
            "Bookings": reverse("back1:admin-bookings"),
            "Customers": reverse("back1:admin-customers"),
            "Parking Spaces": reverse("admin:back1_parkingslot_changelist"),
            "Alerts": reverse("back1:admin-alerts"),
            "📅 Booking History": reverse("back1:admin-bookings"),
            "💳 Revenue &amp; Payment History": reverse("back1:admin-revenue"),
            "📡 Sensor History": reverse("back1:admin-sensors"),
            "⚡ System Event Log": reverse("back1:admin-events"),
        }
        for label, url in expected_links.items():
            self.assertContains(response, f'href="{url}"')
            self.assertContains(response, label)
        self.assertContains(response, 'id="admin-history-menu"')
        self.assertContains(response, 'data-bs-toggle="dropdown"')
        self.assertNotContains(response, ">Sensors</a>")
        self.assertContains(response, ">Logout</button>")

    def test_history_trigger_and_item_active_states(self):
        for route_name in ["back1:admin-bookings", "back1:admin-revenue", "back1:admin-sensors", "back1:admin-events"]:
            response = self.client.get(reverse(route_name))
            self.assertContains(response, "admin-nav-link dropdown-toggle active")
            self.assertContains(response, f'class="dropdown-item active" href="{reverse(route_name)}"')

    def test_dashboard_drill_down_links_remain_available(self):
        response = self.client.get(reverse("back1:admin-dashboard"), {"date": "2026-08-12"})
        self.assertContains(response, reverse("back1:admin-bookings") + "?date=2026-08-12")
        self.assertContains(response, reverse("back1:admin-events") + "?date=2026-08-12")
        self.assertContains(response, reverse("back1:admin-sensors"))


class AdminEventPresentationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="event-ui-admin", password="pw", is_staff=True)
        self.customer = User.objects.create_user(username="event-customer", email="event@example.com")
        self.booking = Booking.objects.create(
            user=self.customer, parking_slot=ParkingSlot.objects.get(slot_number="A01"),
            booking_date=timezone.localdate(), start_time=time(10), end_time=time(11),
            status="confirmed",
        )

    def test_shared_event_badge_mapping_does_not_modify_stored_values(self):
        cases = [
            ({"event_type": "other", "source": "booking_email", "description": "Confirmation email sent."}, "Email Sent", "event-type-email"),
            ({"event_type": "other", "source": "booking_cancellation", "description": "Booking cancelled."}, "Booking Cancelled", "event-type-cancelled"),
            ({"event_type": "vehicle_detected", "source": "entrance_sensor", "description": "Vehicle arrived."}, "Vehicle Detected", "event-type-vehicle"),
            ({"event_type": "gate_opened", "source": "customer_gate", "description": "Gate opened."}, "Gate Opened", "event-type-gate-open"),
            ({"event_type": "gate_closed", "source": "gate_lifecycle", "description": "Gate closed."}, "Gate Closed", "event-type-gate-closed"),
            ({"event_type": "space_occupied", "source": "parking_sensor", "description": "Occupied."}, "Parking Occupied", "event-type-parking-occupied"),
            ({"event_type": "space_available", "source": "parking_sensor", "description": "Available."}, "Parking Available", "event-type-parking-available"),
            ({"event_type": "other", "source": "booking_lifecycle", "description": "Vehicle exited."}, "Vehicle Exited", "event-type-exited"),
            ({"event_type": "payment", "source": "booking_payment", "description": "Paid."}, "Payment", "event-type-payment"),
            ({"event_type": "other", "source": "unclassified", "description": "Unclassified event."}, "Other", "event-type-other"),
        ]
        for fields, label, css_class in cases:
            event = SystemEvent.objects.create(**fields)
            original = (event.event_type, event.source, event.description)
            rendered = render_to_string("back1/partials/event_type_badge.html", {"event": event})
            self.assertIn(label, rendered)
            self.assertIn(css_class, rendered)
            event.refresh_from_db()
            self.assertEqual((event.event_type, event.source, event.description), original)

    def test_event_log_and_recent_activity_use_same_badge_partial(self):
        event = SystemEvent.objects.create(
            event_type="other", source="booking_email",
            description="Confirmation email sent for booking #7.",
        )
        self.client.force_login(self.admin)
        selected = timezone.localdate(event.timestamp)
        events = self.client.get(reverse("back1:admin-events"), {"date": selected.isoformat()})
        dashboard = self.client.get(reverse("back1:admin-dashboard"), {"date": selected.isoformat()})
        for response in (events, dashboard):
            self.assertContains(response, "Email Sent")
            self.assertContains(response, "event-type-email")

    def test_admin_access_search_and_invalid_filters(self):
        event = SystemEvent.objects.create(
            event_type="other", source="booking_email",
            description="Confirmation sent for a reserved visit.", booking=self.booking,
        )
        url = reverse("back1:admin-events")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        selected = timezone.localdate(event.timestamp).isoformat()
        for query in ["reserved visit", str(self.booking.id), f"Booking {self.booking.id}", "event-customer", "event@example.com"]:
            response = self.client.get(url, {"date": selected, "q": query})
            self.assertEqual(list(response.context["page_obj"]), [event])
        invalid = self.client.get(url, {"date": selected, "type": "invalid", "source": "invalid"})
        self.assertEqual(list(invalid.context["page_obj"]), [event])
        self.assertEqual(invalid.context["selected_event_type"], "")
        self.assertEqual(invalid.context["selected_event_source"], "")

    def test_each_event_category_and_source_filter(self):
        sensor = SensorData.objects.get(sensor_id="ENTRANCE_01")
        cases = [
            ("vehicle", {"event_type": "vehicle_detected", "source": "entrance_sensor", "description": "Vehicle arrived.", "sensor": sensor}),
            ("gate", {"event_type": "gate_opened", "source": "admin_gate", "description": "Gate opened."}),
            ("parking", {"event_type": "space_occupied", "source": "parking_sensor", "description": "Space occupied."}),
            ("booking", {"event_type": "other", "source": "booking_email", "description": "Email sent."}),
            ("payment", {"event_type": "payment", "source": "booking_payment", "description": "Payment received."}),
            ("emergency", {"event_type": "emergency", "source": "admin_emergency", "description": "Emergency resolved."}),
            ("sensor", {"event_type": "sensor_offline", "source": "sensor_alert", "description": "Sensor offline."}),
        ]
        created = {category: SystemEvent.objects.create(**fields) for category, fields in cases}
        self.client.force_login(self.admin)
        url = reverse("back1:admin-events")
        selected = timezone.localdate().isoformat()
        for category, expected in created.items():
            response = self.client.get(url, {"date": selected, "type": category})
            self.assertIn(expected, list(response.context["page_obj"]))
        entrance = self.client.get(url, {"date": selected, "source": "entrance_sensor"})
        self.assertEqual(list(entrance.context["page_obj"]), [created["vehicle"]])
        combined = self.client.get(url, {
            "date": selected, "q": "Vehicle", "type": "vehicle", "source": "entrance_sensor",
        })
        self.assertEqual(list(combined.context["page_obj"]), [created["vehicle"]])

    def test_date_navigation_and_pagination_preserve_filters(self):
        selected = timezone.localdate()
        for index in range(51):
            SystemEvent.objects.create(
                event_type="gate_opened", source="admin_gate",
                description=f"Searchable gate event {index}",
            )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-events"), {
            "date": selected.isoformat(), "q": "Searchable", "type": "gate",
            "source": "admin_gate",
        })
        preserved = "q=Searchable&type=gate&source=admin_gate"
        self.assertContains(response, preserved)
        self.assertContains(response, "page=2")
        self.assertContains(response, f"date={(selected - timedelta(days=1)).isoformat()}")
        self.assertContains(response, f"date={(selected + timedelta(days=1)).isoformat()}")
        self.assertContains(response, f'date={selected.isoformat()}&q=Searchable')

    def test_filtered_and_date_empty_states_are_distinct(self):
        event = SystemEvent.objects.create(event_type="other", source="test", description="Existing event")
        self.client.force_login(self.admin)
        url = reverse("back1:admin-events")
        selected = timezone.localdate(event.timestamp)
        filtered = self.client.get(url, {"date": selected, "q": "does-not-match"})
        empty_date = self.client.get(url, {"date": selected - timedelta(days=30)})
        self.assertContains(filtered, "No events match the selected filters.")
        self.assertContains(empty_date, "No system activity recorded for this date.")


class AdminRevenueHistoryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="revenue-admin", password="pw", is_staff=True)
        self.customer = User.objects.create_user(username="revenue-customer", password="pw")
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.selected = timezone.localdate() - timedelta(days=2)
        self.booking = Booking.objects.create(
            user=self.customer, parking_slot=self.slot, booking_date=self.selected,
            start_time=time(10), end_time=time(11), status="completed", payment_status="paid",
        )

    def create_transaction(self, *, category, amount, paid_at, status="paid", transaction_type=None):
        booking = self.booking if category == "normal" and not Transaction.objects.filter(
            booking=self.booking, transaction_type="payment", payment_status="paid"
        ).exists() else None
        return Transaction.objects.create(
            user=self.customer,
            booking=booking,
            transaction_type=transaction_type or ("payment" if category == "normal" else "penalty"),
            payment_category=category,
            payment_status=status,
            amount=Decimal(amount),
            paid_at=paid_at,
        )

    def test_admin_only_access_and_default_invalid_dates(self):
        url = reverse("back1:admin-revenue")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).context["viewing_date"], timezone.localdate())
        self.assertEqual(self.client.get(url, {"date": "invalid"}).context["viewing_date"], timezone.localdate())

    def test_date_navigation_controls_preserve_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-revenue"), {
            "date": self.selected.isoformat(), "type": "parking",
        })
        self.assertEqual(response.context["viewing_date"], self.selected)
        self.assertContains(response, f'?date={(self.selected - timedelta(days=1)).isoformat()}&type=parking')
        self.assertContains(response, f'?date={(self.selected + timedelta(days=1)).isoformat()}&type=parking')
        self.assertContains(response, f'?date={timezone.localdate().isoformat()}&type=parking')

    def test_all_parking_penalty_filters_and_only_paid_transactions(self):
        selected_at = timezone.make_aware(datetime.combine(self.selected, time(12)))
        parking = self.create_transaction(category="normal", amount="6.00", paid_at=selected_at)
        penalty = self.create_transaction(category="overstay", amount="20.00", paid_at=selected_at + timedelta(hours=1))
        self.create_transaction(category="normal", amount="99.00", paid_at=selected_at, status="pending")
        self.create_transaction(category="refund", amount="4.00", paid_at=selected_at, transaction_type="refund")
        self.create_transaction(category="normal", amount="50.00", paid_at=selected_at + timedelta(days=1))
        self.client.force_login(self.admin)
        url = reverse("back1:admin-revenue")

        all_response = self.client.get(url, {"date": self.selected, "type": "all"})
        self.assertEqual(list(all_response.context["transactions"]), [penalty, parking])
        self.assertEqual(all_response.context["parking_revenue"], Decimal("6.00"))
        self.assertEqual(all_response.context["penalty_revenue"], Decimal("20.00"))
        self.assertEqual(all_response.context["total_revenue"], Decimal("26.00"))

        parking_response = self.client.get(url, {"date": self.selected, "type": "parking"})
        penalty_response = self.client.get(url, {"date": self.selected, "type": "penalty"})
        self.assertEqual(list(parking_response.context["transactions"]), [parking])
        self.assertEqual(list(penalty_response.context["transactions"]), [penalty])

    def test_dashboard_totals_and_card_links_match_revenue_history(self):
        selected_at = timezone.make_aware(datetime.combine(self.selected, time(14)))
        self.create_transaction(category="normal", amount="8.00", paid_at=selected_at)
        self.create_transaction(category="overstay", amount="40.00", paid_at=selected_at)
        self.client.force_login(self.admin)
        dashboard = self.client.get(reverse("back1:admin-dashboard"), {"date": self.selected})
        history = self.client.get(reverse("back1:admin-revenue"), {"date": self.selected})
        for key in ["parking_revenue", "penalty_revenue", "total_revenue"]:
            self.assertEqual(dashboard.context[key], history.context[key])
        for revenue_type in ["all", "parking", "penalty"]:
            self.assertContains(
                dashboard,
                f'{reverse("back1:admin-revenue")}?date={self.selected.isoformat()}&type={revenue_type}',
            )

    def test_no_data_and_uk_timezone_date_boundary(self):
        boundary = datetime(2026, 8, 10, 23, 30, tzinfo=datetime_timezone.utc)
        transaction = self.create_transaction(category="normal", amount="3.00", paid_at=boundary)
        self.client.force_login(self.admin)
        url = reverse("back1:admin-revenue")
        utc_day = self.client.get(url, {"date": "2026-08-10"})
        uk_day = self.client.get(url, {"date": "2026-08-11"})
        self.assertEqual(list(utc_day.context["transactions"]), [])
        self.assertEqual(list(uk_day.context["transactions"]), [transaction])
        self.assertEqual(utc_day.context["total_revenue"], Decimal("0.00"))
        self.assertContains(utc_day, "No paid transactions for this date.")
        self.assertContains(utc_day, "£0.00", count=3)


class SensorReadingHistoryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="history-admin", password="pw", is_staff=True)
        self.now = timezone.now().replace(microsecond=0)

    def test_real_ingestion_appends_history_for_all_monitored_sensor_types(self):
        reports = (
            ("TEMPERATURE_01", "24.5"), ("HUMIDITY_01", "58"),
            ("FIRE_01", "normal"), ("PARK_A01", "detected"),
            ("ENTRANCE_01", "clear"), ("EXIT_01", "detected"),
        )
        for offset, (sensor_id, value) in enumerate(reports):
            update_logical_sensor(sensor_id=sensor_id, value=value, now=self.now + timedelta(seconds=offset))

        self.assertEqual(SensorReadingHistory.objects.count(), len(reports))
        for sensor_id, value in reports:
            history = SensorReadingHistory.objects.get(sensor_id=sensor_id)
            current = SensorData.objects.get(sensor_id=sensor_id)
            self.assertEqual(history.value, current.value)
            self.assertEqual(history.sensor_type, current.sensor_type)
            self.assertEqual(history.condition_status, current.condition_status)
            self.assertEqual(history.connection_status, "online")

    def test_multiple_reports_append_without_overwriting_current_sensor(self):
        for minutes, value in ((0, "24.1"), (5, "24.3"), (10, "24.5")):
            update_logical_sensor(sensor_id="TEMPERATURE_01", value=value, now=self.now + timedelta(minutes=minutes))
        self.assertEqual(
            list(SensorReadingHistory.objects.filter(sensor_id="TEMPERATURE_01").values_list("value", flat=True)),
            ["24.1", "24.3", "24.5"],
        )
        self.assertEqual(SensorData.objects.get(sensor_id="TEMPERATURE_01").value, "24.5")

    def test_history_insert_keeps_existing_alert_processing(self):
        sensor, _ = update_logical_sensor(sensor_id="TEMPERATURE_01", value="55", now=self.now)
        self.assertEqual(sensor.condition_status, "abnormal")
        self.assertTrue(Alert.objects.filter(sensor=sensor, alert_type="sensor_abnormal", acknowledged=False).exists())
        self.assertEqual(SensorReadingHistory.objects.get(sensor_id="TEMPERATURE_01").condition_status, "abnormal")

    def test_sensor_history_page_date_filter_summary_detail_and_no_data(self):
        selected = timezone.localdate() - timedelta(days=2)
        selected_at = timezone.make_aware(datetime.combine(selected, time(9, 5)))
        other_at = selected_at + timedelta(days=1)
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="23.8", now=selected_at)
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="24.1", now=selected_at + timedelta(minutes=5))
        update_logical_sensor(sensor_id="TEMPERATURE_01", value="99", now=other_at)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("back1:admin-sensors"), {"date": selected.isoformat(), "sensor": "TEMPERATURE_01"})
        self.assertEqual(response.context["viewing_date"], selected)
        self.assertContains(response, "23.8°C")
        self.assertContains(response, "24.1°C")
        self.assertNotContains(response, "99°C")
        self.assertEqual([row["value_display"] for row in response.context["selected_readings"]], ["23.8°C", "24.1°C"])
        humidity = next(row for row in response.context["sensor_rows"] if row["sensor_id"] == "HUMIDITY_01")
        self.assertEqual(humidity["health_label"], "NO DATA")
        self.assertEqual(humidity["value_display"], "—")

        default = self.client.get(reverse("back1:admin-sensors"))
        invalid = self.client.get(reverse("back1:admin-sensors"), {"date": "invalid"})
        self.assertEqual(default.context["viewing_date"], timezone.localdate())
        self.assertEqual(invalid.context["viewing_date"], timezone.localdate())
        self.assertContains(response, f'?date={(selected - timedelta(days=1)).isoformat()}&sensor=TEMPERATURE_01')
        self.assertContains(response, f'?date={(selected + timedelta(days=1)).isoformat()}&sensor=TEMPERATURE_01')

    def test_uk_date_boundary_and_dashboard_polling_do_not_create_history(self):
        # 23:30 UTC is 00:30 the next UK day during BST.
        received = datetime(2026, 8, 10, 23, 30, tzinfo=datetime_timezone.utc)
        update_logical_sensor(sensor_id="FIRE_01", value="normal", now=received)
        self.client.force_login(self.admin)
        uk_date = timezone.localtime(received).date()
        response = self.client.get(reverse("back1:admin-sensors"), {"date": uk_date.isoformat(), "sensor": "FIRE_01"})
        self.assertEqual(len(response.context["selected_readings"]), 1)
        before = SensorReadingHistory.objects.count()
        self.client.get(reverse("back1:dashboard_sensor_status"))
        self.assertEqual(SensorReadingHistory.objects.count(), before)


class PartBSensorGateLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="part-b", password="pw", email="partb@example.com")
        self.other = User.objects.create_user(username="part-b-other", password="pw")
        self.slot = ParkingSlot.objects.get(slot_number="A03")
        self.day = timezone.localdate()
        self.booking = Booking.objects.create(
            user=self.user, parking_slot=self.slot, booking_date=self.day,
            start_time=time(10), end_time=time(11), status="confirmed", payment_status="paid",
            normal_parking_amount=Decimal("2.00"), outstanding_balance=Decimal("0.00"),
        )
        Wallet.objects.create(user=self.user, balance=Decimal("50.00"))
        Wallet.objects.create(user=self.other, balance=Decimal("50.00"))
        self.now = timezone.make_aware(datetime.combine(self.day, time(10)))

    @override_settings(SENSOR_DEVICE_API_KEY="test-device-key")
    def test_device_auth_updates_same_seeded_sensor_without_duplicates(self):
        url = reverse("back1:device-sensor-update")
        self.assertEqual(self.client.post(url, {"sensor_id": "PARK_A01", "value": "detected"}).status_code, 401)
        self.assertEqual(self.client.post(url, {"sensor_id": "PARK_A01", "value": "detected"}, HTTP_X_DEVICE_API_KEY="bad").status_code, 401)
        response = self.client.post(url, {"sensor_id": "PARK_A01", "value": "detected"}, HTTP_X_DEVICE_API_KEY="test-device-key")
        self.assertEqual(response.status_code, 200)
        self.client.post(url, {"sensor_id": "PARK_A01", "value": "clear"}, HTTP_X_DEVICE_API_KEY="test-device-key")
        self.assertEqual(SensorData.objects.filter(sensor_id="PARK_A01").count(), 1)
        sensor = SensorData.objects.get(sensor_id="PARK_A01")
        self.assertEqual(sensor.parking_slot.slot_number, "A01")
        self.assertEqual(sensor.connection_status, "online")

    @override_settings(SENSOR_DEVICE_API_KEY="test-device-key")
    def test_real_device_api_creates_exact_vehicle_transition_rows(self):
        self.booking.parking_slot = ParkingSlot.objects.get(slot_number="A01")
        self.booking.save(update_fields=["parking_slot", "updated_at"])
        url = reverse("back1:device-sensor-update")
        headers = {"HTTP_X_DEVICE_API_KEY": "test-device-key"}

        with patch("back1.services.timezone.now", return_value=self.now):
            for sensor_id, value in (
                ("ENTRANCE_01", "clear"),
                ("ENTRANCE_01", "detected"),
                ("PARK_A01", "clear"),
                ("PARK_A01", "occupied"),
                ("PARK_A01", "occupied"),
                ("PARK_A01", "clear"),
                ("EXIT_01", "clear"),
                ("EXIT_01", "detected"),
            ):
                self.assertEqual(
                    self.client.post(url, {"sensor_id": sensor_id, "value": value}, **headers).status_code,
                    200,
                )

        rows = list(SystemEvent.objects.filter(
            source__in=["entrance_sensor", "parking_sensor", "exit_sensor"]
        ).order_by("id"))
        self.assertEqual(
            [(row.event_type, row.source, row.description) for row in rows],
            [
                ("vehicle_detected", "entrance_sensor", "Vehicle arrived at Entrance."),
                ("space_occupied", "parking_sensor", "Vehicle occupied A01."),
                ("space_available", "parking_sensor", "Vehicle left A01."),
                ("vehicle_detected", "exit_sensor", "Vehicle arrived at Exit."),
            ],
        )
        self.assertIsNone(rows[0].booking_id)
        self.assertEqual(rows[1].booking_id, self.booking.id)
        self.assertEqual(rows[1].parking_slot.slot_number, "A01")
        self.assertEqual(rows[2].booking_id, self.booking.id)
        self.assertIsNone(rows[3].booking_id)
        self.assertTrue(all(row.gate_id is None for row in rows))

    @override_settings(SENSOR_DEVICE_API_KEY="test-device-key")
    def test_real_api_and_customer_gate_endpoints_complete_new_journey(self):
        self.booking.parking_slot = ParkingSlot.objects.get(slot_number="A01")
        self.booking.save(update_fields=["parking_slot", "updated_at"])
        sensor_url = reverse("back1:device-sensor-update")
        headers = {"HTTP_X_DEVICE_API_KEY": "test-device-key"}
        self.client.force_login(self.user)

        with patch("back1.services.timezone.now", return_value=self.now):
            def sensor(sensor_id, value):
                response = self.client.post(sensor_url, {"sensor_id": sensor_id, "value": value}, **headers)
                self.assertEqual(response.status_code, 200)

            sensor("ENTRANCE_01", "clear"); sensor("ENTRANCE_01", "detected")
            self.assertEqual(self.client.post(reverse("back1:customer-gate-request", args=[self.booking.id, "entrance"])).status_code, 200)
            sensor("ENTRANCE_01", "clear")
            sensor("PARK_A01", "clear"); sensor("PARK_A01", "occupied"); sensor("PARK_A01", "clear")
            sensor("EXIT_01", "clear"); sensor("EXIT_01", "detected")
            self.assertEqual(self.client.post(reverse("back1:customer-gate-request", args=[self.booking.id, "exit"])).status_code, 200)
            sensor("EXIT_01", "clear")

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")
        completion = SystemEvent.objects.get(booking=self.booking, source="booking_lifecycle")
        self.assertIn("Vehicle exited", completion.description)

        admin = User.objects.create_user(username="journey-admin", password="pw", is_staff=True)
        self.client.force_login(admin)
        event_page = self.client.get(reverse("back1:admin-events"), {"date": self.day.isoformat()})
        dashboard = self.client.get(reverse("back1:admin-dashboard"), {"date": self.day.isoformat()})
        for text in ["Vehicle Detected", "Parking Occupied", "Parking Available", "Vehicle Exited"]:
            self.assertContains(event_page, text)
        self.assertContains(dashboard, "Vehicle Exited")

    @override_settings(SENSOR_DEVICE_API_KEY="test-device-key")
    def test_customer_cannot_submit_sensor_reading(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("back1:device-sensor-update"), {"sensor_id": "ENTRANCE_01", "value": "detected"})
        self.assertEqual(response.status_code, 403)

    def test_sensor_transition_events_are_not_duplicated(self):
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=self.now)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=self.now + timedelta(seconds=1))
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now + timedelta(seconds=2))
        self.assertEqual(SystemEvent.objects.filter(sensor__sensor_id="ENTRANCE_01").count(), 2)

    def test_complete_vehicle_journey_records_transition_events_once(self):
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=self.now + timedelta(minutes=1))
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=self.now + timedelta(minutes=2))
        request_customer_gate(
            booking_id=self.booking.id, user=self.user,
            gate_type="entrance", now=self.now + timedelta(minutes=2),
        )
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now + timedelta(minutes=3))

        update_logical_sensor(sensor_id="PARK_A03", value="clear", now=self.now)
        update_logical_sensor(sensor_id="PARK_A03", value="detected", now=self.now + timedelta(minutes=4))
        update_logical_sensor(sensor_id="PARK_A03", value="detected", now=self.now + timedelta(minutes=5))
        update_logical_sensor(sensor_id="PARK_A03", value="clear", now=self.now + timedelta(minutes=55))

        update_logical_sensor(sensor_id="EXIT_01", value="clear", now=self.now)
        update_logical_sensor(sensor_id="EXIT_01", value="detected", now=self.now + timedelta(minutes=56))
        request_customer_gate(
            booking_id=self.booking.id, user=self.user,
            gate_type="exit", now=self.now + timedelta(minutes=57),
        )
        update_logical_sensor(sensor_id="EXIT_01", value="clear", now=self.now + timedelta(minutes=58))

        journey = SystemEvent.objects.filter(booking=self.booking).order_by("timestamp")
        self.assertEqual(
            list(journey.values_list("event_type", flat=True)),
            ["gate_opened", "gate_closed", "space_occupied", "space_available", "gate_opened", "gate_closed", "other"],
        )
        self.assertEqual(SystemEvent.objects.filter(source="entrance_sensor", event_type="vehicle_detected").count(), 2)
        self.assertEqual(SystemEvent.objects.filter(source="exit_sensor", event_type="vehicle_detected").count(), 2)
        self.assertEqual(SystemEvent.objects.filter(source="parking_sensor", event_type="space_occupied").count(), 1)
        self.assertEqual(SystemEvent.objects.filter(source="parking_sensor", event_type="space_available").count(), 1)
        self.assertTrue(journey.filter(source="booking_lifecycle", description__contains="Vehicle exited").exists())
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")

    def test_different_parking_spaces_record_independent_transitions(self):
        update_logical_sensor(sensor_id="PARK_A03", value="detected", now=self.now)
        update_logical_sensor(sensor_id="PARK_A04", value="detected", now=self.now)
        events = SystemEvent.objects.filter(event_type="space_occupied", source="parking_sensor")
        self.assertEqual(set(events.values_list("parking_slot__slot_number", flat=True)), {"A03", "A04"})

    def test_repeated_parking_reading_reconciles_stale_physical_flag_without_event(self):
        sensor = SensorData.objects.get(sensor_id="PARK_A01")
        sensor.value = "clear"
        sensor.save(update_fields=["value"])
        slot = ParkingSlot.objects.get(slot_number="A01")
        slot.is_physically_occupied = True
        slot.status = "occupied"
        slot.save(update_fields=["is_physically_occupied", "status"])
        before = SystemEvent.objects.filter(sensor=sensor).count()
        _, changed = update_logical_sensor(sensor_id="PARK_A01", value="clear")
        slot.refresh_from_db()
        self.assertFalse(changed)
        self.assertFalse(slot.is_physically_occupied)
        self.assertEqual(slot.status, "available")
        self.assertEqual(SystemEvent.objects.filter(sensor=sensor).count(), before)

    def test_recent_and_stale_sensor_online_derivation(self):
        sensor, _ = update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now)
        self.assertTrue(sensor_is_online(sensor, now=self.now + timedelta(seconds=599)))
        self.assertFalse(sensor_is_online(sensor, now=self.now + timedelta(seconds=601)))

    def test_exact_entrance_boundaries(self):
        start = timezone.make_aware(datetime.combine(self.day, time(10)))
        self.assertFalse(entrance_access_allowed(self.booking, now=start - timedelta(minutes=6)))
        self.assertTrue(entrance_access_allowed(self.booking, now=start - timedelta(minutes=5)))
        self.assertTrue(entrance_access_allowed(self.booking, now=start))
        self.assertTrue(entrance_access_allowed(self.booking, now=start + timedelta(hours=1)))
        self.assertFalse(entrance_access_allowed(self.booking, now=start + timedelta(hours=1, seconds=1)))

    def test_entrance_requires_sensor_and_duplicate_open_is_safe(self):
        update_logical_sensor(sensor_id="ENTRANCE_01", value="clear", now=self.now)
        with self.assertRaisesMessage(ValueError, "No vehicle"):
            request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="entrance", now=self.now)
        update_logical_sensor(sensor_id="ENTRANCE_01", value="detected", now=self.now)
        _, gate, changed = request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="entrance", now=self.now)
        self.assertTrue(gate.is_open); self.assertTrue(changed)
        _, _, changed_again = request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="entrance", now=self.now)
        self.assertFalse(changed_again)
        self.assertEqual(SystemEvent.objects.filter(source="customer_gate").count(), 1)

    def test_parking_sensor_controls_physical_state_and_activates_assigned_booking(self):
        update_logical_sensor(sensor_id="PARK_A03", value="detected", now=self.now)
        self.slot.refresh_from_db(); self.booking.refresh_from_db()
        self.assertTrue(self.slot.is_physically_occupied)
        self.assertEqual(self.booking.status, "active")
        update_logical_sensor(sensor_id="PARK_A03", value="clear", now=self.now + timedelta(minutes=10))
        self.slot.refresh_from_db(); self.booking.refresh_from_db()
        self.assertFalse(self.slot.is_physically_occupied)
        self.assertEqual(self.booking.status, "active")

    def test_reminder_due_once_and_not_for_cancelled(self):
        due = timezone.make_aware(datetime.combine(self.day, time(10, 46)))
        self.assertEqual(process_booking_reminders(now=due), 1)
        self.assertEqual(process_booking_reminders(now=due), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("£20/hour", mail.outbox[0].body)
        self.booking.reminder_email_sent = False; self.booking.status = "cancelled"; self.booking.save()
        self.assertEqual(process_booking_reminders(now=due), 0)

    def test_started_hour_overstay_and_no_penalty_transaction_until_payment(self):
        self.booking.status = "active"; self.booking.save(update_fields=["status"])
        self.slot.is_physically_occupied = True; self.slot.save(update_fields=["is_physically_occupied"])
        process_overstays(now=timezone.make_aware(datetime.combine(self.day, time(11, 15))))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.overstay_amount, Decimal("20.00"))
        self.assertEqual(self.booking.outstanding_balance, Decimal("20.00"))
        self.assertFalse(Transaction.objects.filter(booking=self.booking, payment_category="overstay").exists())

    def test_started_hour_overstay_boundaries(self):
        self.booking.status = "active"
        self.booking.save(update_fields=["status"])
        self.slot.is_physically_occupied = True
        self.slot.save(update_fields=["is_physically_occupied"])
        end = timezone.make_aware(datetime.combine(self.day, time(11)))
        for minutes, expected in (
            (1, Decimal("20.00")),
            (60, Decimal("20.00")),
            (61, Decimal("40.00")),
            (120, Decimal("40.00")),
            (121, Decimal("60.00")),
        ):
            amount = finalize_overstay(
                self.booking,
                now=end + timedelta(minutes=minutes),
            )
            self.booking.refresh_from_db()
            self.assertEqual(amount, expected, minutes)
            self.assertEqual(self.booking.overstay_amount, expected, minutes)
            self.assertEqual(self.booking.outstanding_balance, expected, minutes)
            self.assertEqual(self.booking.overtime_minutes, minutes)

    def test_bay_clear_freezes_overstay_and_does_not_complete(self):
        self.booking.status = "active"; self.booking.save(update_fields=["status"])
        update_logical_sensor(sensor_id="PARK_A03", value="detected", now=self.now)
        leave = timezone.make_aware(datetime.combine(self.day, time(11, 30)))
        update_logical_sensor(sensor_id="PARK_A03", value="clear", now=leave)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.overstay_amount, Decimal("20.00"))
        self.assertEqual(self.booking.status, "overtime")
        self.assertEqual(self.booking.parking_left_at, leave)

    def test_overstay_payment_idempotent_and_preserves_normal_transaction(self):
        Transaction.objects.create(user=self.user, booking=self.booking, transaction_type="payment", amount=Decimal("2"), payment_category="normal", payment_status="paid")
        self.booking.status = "overtime"; self.booking.overstay_amount = Decimal("5"); self.booking.outstanding_balance = Decimal("5"); self.booking.payment_status = "outstanding"; self.booking.save()
        _, charged = pay_overstay(booking_id=self.booking.id, user=self.user)
        self.assertTrue(charged)
        _, charged_again = pay_overstay(booking_id=self.booking.id, user=self.user)
        self.assertFalse(charged_again)
        self.assertEqual(Transaction.objects.filter(booking=self.booking).count(), 2)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("45.00"))

    def test_exit_requires_sensor_and_zero_balance_then_clear_completes(self):
        self.booking.status = "active"; self.booking.save(update_fields=["status"])
        update_logical_sensor(sensor_id="EXIT_01", value="clear", now=self.now)
        with self.assertRaisesMessage(ValueError, "No vehicle"):
            request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="exit", now=self.now)
        update_logical_sensor(sensor_id="EXIT_01", value="detected", now=self.now)
        _, gate, _ = request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="exit", now=self.now)
        self.assertTrue(gate.is_open)
        self.booking.refresh_from_db(); self.assertNotEqual(self.booking.status, "completed")
        update_logical_sensor(sensor_id="EXIT_01", value="clear", now=self.now + timedelta(minutes=1))
        self.booking.refresh_from_db(); gate.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")
        self.assertIsNotNone(self.booking.completed_at)
        self.assertFalse(gate.is_open)

    def test_outstanding_balance_blocks_exit_and_payment_does_not_open_gate(self):
        self.booking.status = "overtime"; self.booking.overstay_amount = Decimal("5"); self.booking.outstanding_balance = Decimal("5"); self.booking.payment_status = "outstanding"; self.booking.save()
        update_logical_sensor(sensor_id="EXIT_01", value="detected", now=self.now)
        with self.assertRaisesMessage(ValueError, "Outstanding payment"):
            request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="exit", now=self.now)
        pay_overstay(booking_id=self.booking.id, user=self.user)
        self.assertFalse(Gate.objects.get(gate_type="exit").is_open)
        request_customer_gate(booking_id=self.booking.id, user=self.user, gate_type="exit", now=self.now)
        self.assertTrue(Gate.objects.get(gate_type="exit").is_open)

    def test_other_customer_cannot_request_gate_or_pay_overstay(self):
        with self.assertRaises(Booking.DoesNotExist):
            request_customer_gate(booking_id=self.booking.id, user=self.other, gate_type="entrance", now=self.now)
        self.booking.outstanding_balance = Decimal("5"); self.booking.save(update_fields=["outstanding_balance"])
        with self.assertRaises(Booking.DoesNotExist):
            pay_overstay(booking_id=self.booking.id, user=self.other)


class PartABookingPaymentFlowTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="part-a", password="test-password", email="customer@example.com"
        )
        self.other = User.objects.create_user(
            username="part-a-other", password="test-password", email="other@example.com"
        )
        self.day = timezone.localdate() + timedelta(days=3)
        self.start = time(10, 0)
        self.end = time(11, 0)
        Wallet.objects.create(user=self.user, balance=Decimal("20.00"))
        Wallet.objects.create(user=self.other, balance=Decimal("20.00"))

    def make_booking(self, user=None, start=None, end=None):
        return create_pending_booking(
            user=user or self.user,
            booking_date=self.day,
            start_time=start or self.start,
            end_time=end or self.end,
        )

    def test_green_red_capacity_and_admin_restrictions(self):
        ParkingSlot.objects.filter(slot_number="A05").update(is_under_maintenance=True)
        ParkingSlot.objects.filter(slot_number="A06").update(is_backup=True)
        self.assertEqual(availability(self.day, self.start, self.end)["available_space_count"], 4)
        users = []
        for index in range(4):
            user = User.objects.create_user(username=f"capacity-{index}")
            users.append(user)
            booking = self.make_booking(user=user)
            booking.status = "confirmed"
            booking.save(update_fields=["status"])
        result = availability(self.day, self.start, self.end)
        self.assertFalse(result["available"])
        self.assertEqual(result["total_usable_space_count"], 4)

    def test_cancelled_expired_and_adjacent_do_not_consume_capacity(self):
        booking = self.make_booking()
        booking.status = "cancelled"
        booking.save(update_fields=["status"])
        self.assertEqual(availability(self.day, self.start, self.end)["available_space_count"], 6)
        adjacent = self.make_booking(start=time(9), end=time(10))
        adjacent.status = "confirmed"
        adjacent.save(update_fields=["status"])
        self.assertEqual(availability(self.day, self.start, self.end)["available_space_count"], 6)
        self.assertEqual(availability(self.day, time(9, 30), time(10, 30))["available_space_count"], 5)

    def test_lowest_usable_space_is_assigned_and_legacy_choice_ignored(self):
        ParkingSlot.objects.filter(slot_number="A01").update(is_enabled=False)
        self.client.force_login(self.user)
        response = self.client.post(reverse("back1:booking-create"), {
            "booking_date": self.day, "start_time": "10:00", "end_time": "11:00",
            "parking_slot": ParkingSlot.objects.get(slot_number="A06").id,
            "normal_parking_amount": "0.01",
        })
        booking = Booking.objects.get(user=self.user)
        self.assertRedirects(response, reverse("back1:booking-payment", args=[booking.id]))
        self.assertEqual(booking.parking_slot.slot_number, "A02")
        self.assertEqual(booking.normal_parking_amount, Decimal("2.00"))
        self.assertEqual(booking.status, "pending")

    def test_full_slot_submission_is_rejected_server_side(self):
        for index in range(6):
            user = User.objects.create_user(username=f"full-{index}")
            booking = self.make_booking(user=user)
            booking.status = "confirmed"
            booking.save(update_fields=["status"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("back1:booking-create"), {
            "booking_date": self.day, "start_time": "10:00", "end_time": "11:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No parking spaces are available")

    def test_pricing_uses_rate_and_rejects_invalid_duration(self):
        rate = ParkingRate.objects.first()
        rate.rate_per_hour = Decimal("3.50")
        rate.save(update_fields=["rate_per_hour"])
        self.assertEqual(calculate_normal_price(time(10), time(13)), Decimal("10.50"))
        with self.assertRaises(ValueError):
            calculate_normal_price(time(10), time(10))
        with self.assertRaises(ValueError):
            calculate_normal_price(time(11), time(10))

    def test_successful_payment_is_idempotent(self):
        booking = self.make_booking()
        paid, charged = pay_booking(booking_id=booking.id, user=self.user)
        self.assertTrue(charged)
        self.assertEqual(paid.status, "confirmed")
        self.assertEqual(paid.payment_status, "paid")
        self.assertEqual(paid.outstanding_balance, Decimal("0.00"))
        self.assertEqual(Transaction.objects.filter(booking=booking).count(), 1)
        paid_again, charged_again = pay_booking(booking_id=booking.id, user=self.user)
        self.assertFalse(charged_again)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("18.00"))

    def test_insufficient_balance_and_expired_payment_are_rejected(self):
        booking = self.make_booking()
        Wallet.objects.filter(user=self.user).update(balance=Decimal("1.00"))
        with self.assertRaisesMessage(ValueError, "Insufficient"):
            pay_booking(booking_id=booking.id, user=self.user)
        booking.pending_expires_at = timezone.now() - timedelta(seconds=1)
        booking.save(update_fields=["pending_expires_at"])
        with self.assertRaisesMessage(ValueError, "expired"):
            pay_booking(booking_id=booking.id, user=self.user)

    def test_customer_cannot_pay_or_view_other_customer_booking(self):
        booking = self.make_booking(user=self.other)
        with self.assertRaises(Booking.DoesNotExist):
            pay_booking(booking_id=booking.id, user=self.user)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("back1:booking-payment", args=[booking.id])).status_code, 404)
        booking.status = "confirmed"; booking.payment_status = "paid"; booking.save()
        self.assertEqual(self.client.get(reverse("back1:booking-success", args=[booking.id])).status_code, 404)

    def test_payment_rolls_back_if_transaction_creation_fails(self):
        booking = self.make_booking()
        with patch("back1.services.Transaction.objects.create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                pay_booking(booking_id=booking.id, user=self.user)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("20.00"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, "pending")

    def test_confirmation_email_is_sent_once_with_required_details(self):
        booking = self.make_booking()
        booking, _ = pay_booking(booking_id=booking.id, user=self.user)
        self.assertTrue(send_booking_confirmation(booking))
        booking.refresh_from_db()
        self.assertTrue(booking.confirmation_email_sent)
        self.assertFalse(send_booking_confirmation(booking))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn(booking.parking_slot.slot_number, mail.outbox[0].body)
        self.assertIn("09:55", mail.outbox[0].body)

    def test_email_failure_does_not_reverse_payment(self):
        booking = self.make_booking()
        booking, _ = pay_booking(booking_id=booking.id, user=self.user)
        with patch("back1.services.send_mail", side_effect=RuntimeError("smtp")):
            self.assertFalse(send_booking_confirmation(booking))
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, "paid")
        self.assertFalse(booking.confirmation_email_sent)

    def test_stale_pending_cleanup_and_my_booking_groups(self):
        booking = self.make_booking()
        booking.pending_expires_at = timezone.now() - timedelta(seconds=1)
        booking.save(update_fields=["pending_expires_at"])
        self.assertEqual(expire_stale_pending_bookings(), 1)
        self.client.force_login(self.user)
        response = self.client.get(reverse("back1:bookings"))
        self.assertContains(response, "Past Bookings")
        self.assertNotContains(response, "Pay Now")


class MultiHourBookingRangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="multi-hour", password="pw")
        self.day = timezone.localdate() + timedelta(days=4)

    def test_one_two_and_three_hour_bookings_have_correct_range_and_price(self):
        for index, (end_hour, expected) in enumerate(((11, "2.00"), (12, "4.00"), (13, "6.00"))):
            booking = create_pending_booking(
                user=self.user,
                booking_date=self.day + timedelta(days=index),
                start_time=time(10),
                end_time=time(end_hour),
            )
            self.assertEqual(booking.start_time, time(10))
            self.assertEqual(booking.end_time, time(end_hour))
            self.assertEqual(booking.normal_parking_amount, Decimal(expected))

    def test_full_range_requires_one_space_available_for_every_selected_hour(self):
        ParkingSlot.objects.exclude(slot_number__in=["A01", "A02"]).update(is_enabled=False)
        first_user = User.objects.create_user(username="range-first")
        second_user = User.objects.create_user(username="range-second")
        Booking.objects.create(
            user=first_user, parking_slot=ParkingSlot.objects.get(slot_number="A01"),
            booking_date=self.day, start_time=time(10), end_time=time(11), status="confirmed",
        )
        Booking.objects.create(
            user=second_user, parking_slot=ParkingSlot.objects.get(slot_number="A02"),
            booking_date=self.day, start_time=time(11), end_time=time(12), status="confirmed",
        )
        self.assertTrue(availability(self.day, time(10), time(11))["available"])
        self.assertTrue(availability(self.day, time(11), time(12))["available"])
        self.assertFalse(availability(self.day, time(10), time(12))["available"])
        with self.assertRaisesMessage(ValueError, "No parking spaces"):
            create_pending_booking(user=self.user, booking_date=self.day, start_time=time(10), end_time=time(12))

    def test_physical_and_admin_restrictions_are_excluded_from_assignment(self):
        ParkingSlot.objects.filter(slot_number="A01").update(is_physically_occupied=True)
        ParkingSlot.objects.filter(slot_number="A02").update(is_enabled=False)
        ParkingSlot.objects.filter(slot_number="A03").update(is_under_maintenance=True)
        ParkingSlot.objects.filter(slot_number="A04").update(is_backup=True)
        booking = create_pending_booking(
            user=self.user, booking_date=self.day,
            start_time=time(10), end_time=time(13),
        )
        self.assertEqual(booking.parking_slot.slot_number, "A05")
        self.assertEqual(booking.normal_parking_amount, Decimal("6.00"))

    def test_booking_page_enforces_a_single_consecutive_visual_range(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("back1:booking-create"))
        self.assertContains(response, "Select one hour, then click an adjacent hour")
        self.assertContains(response, "Gaps are not allowed")
        self.assertContains(response, "remove hours from either end")
        self.assertContains(response, 'type="hidden" name="start_time"')
        self.assertContains(response, 'type="hidden" name="end_time"')


class CustomerCancellationRefundTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cancel-customer", password="pw")
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("8.00"))
        self.start = timezone.now() + timedelta(days=3)

    def make_booking(self, *, status="pending", payment_status="pending", amount="4.00", start=None):
        start = start or self.start
        booking = Booking.objects.create(
            user=self.user,
            parking_slot=self.slot,
            booking_date=timezone.localdate(start),
            start_time=timezone.localtime(start).time().replace(microsecond=0),
            end_time=(timezone.localtime(start) + timedelta(hours=2)).time().replace(microsecond=0),
            status=status,
            payment_status=payment_status,
            normal_parking_amount=Decimal(amount),
            outstanding_balance=Decimal("0.00") if payment_status == "paid" else Decimal(amount),
            pending_expires_at=timezone.now() + timedelta(minutes=15),
        )
        if payment_status == "paid":
            Transaction.objects.create(
                user=self.user, booking=booking, transaction_type="payment",
                amount=Decimal(amount), payment_category="normal",
                payment_status="paid", paid_at=timezone.now(),
            )
        return booking

    def test_pending_cancellation_has_no_refund_and_releases_availability(self):
        booking = self.make_booking()
        self.assertFalse(availability(booking.booking_date, booking.start_time, booking.end_time)["available_space_count"] == 6)
        cancelled, refund, changed = cancel_customer_booking(
            booking_id=booking.id, user=self.user, now=timezone.now()
        )
        self.assertTrue(changed); self.assertIsNone(refund)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(Transaction.objects.filter(booking=booking, transaction_type="refund").exists())
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("8.00"))
        self.assertEqual(availability(booking.booking_date, booking.start_time, booking.end_time)["available_space_count"], 6)

    def test_refundable_confirmed_booking_credits_exact_normal_payment_once(self):
        booking = self.make_booking(status="confirmed", payment_status="paid")
        now = self.start - timedelta(hours=25)
        cancelled, refund, changed = cancel_customer_booking(booking_id=booking.id, user=self.user, now=now)
        self.assertTrue(changed); self.assertEqual(refund.amount, Decimal("4.00"))
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("12.00"))
        self.assertEqual(Transaction.objects.filter(booking=booking, transaction_type="refund", payment_category="refund").count(), 1)
        _, same_refund, changed_again = cancel_customer_booking(booking_id=booking.id, user=self.user, now=now)
        self.assertFalse(changed_again); self.assertEqual(same_refund.id, refund.id)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("12.00"))

    def test_confirmed_within_24_hours_cancels_without_refund(self):
        booking = self.make_booking(status="confirmed", payment_status="paid")
        cancelled, refund, changed = cancel_customer_booking(
            booking_id=booking.id, user=self.user,
            now=self.start - timedelta(hours=23, minutes=59),
        )
        self.assertTrue(changed); self.assertIsNone(refund)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("8.00"))
        self.assertFalse(Transaction.objects.filter(booking=booking, transaction_type="refund").exists())
        self.assertEqual(availability(booking.booking_date, booking.start_time, booking.end_time)["available_space_count"], 6)

    def test_exactly_24_hours_is_refundable_but_just_under_is_not(self):
        refundable = self.make_booking(status="confirmed", payment_status="paid", start=self.start)
        refundable_start, _ = booking_bounds(refundable)
        self.assertTrue(cancellation_quote(refundable, now=refundable_start - timedelta(hours=24))["refundable"])
        non_refundable = self.make_booking(status="confirmed", payment_status="paid", start=self.start + timedelta(days=1))
        non_refundable_start, _ = booking_bounds(non_refundable)
        self.assertFalse(cancellation_quote(non_refundable, now=non_refundable_start - timedelta(hours=24) + timedelta(seconds=1))["refundable"])

    def test_started_booking_and_expired_pending_cannot_be_cancelled(self):
        started = self.make_booking(status="confirmed", payment_status="paid", start=timezone.now() - timedelta(minutes=30))
        with self.assertRaisesMessage(ValueError, "can no longer"):
            cancel_customer_booking(booking_id=started.id, user=self.user)
        expired = self.make_booking(start=self.start + timedelta(days=2))
        expired.pending_expires_at = timezone.now() - timedelta(seconds=1)
        expired.save(update_fields=["pending_expires_at"])
        with self.assertRaisesMessage(ValueError, "can no longer"):
            cancel_customer_booking(booking_id=expired.id, user=self.user)

    def test_started_but_unexpired_pending_booking_can_be_cancelled_without_refund(self):
        booking = self.make_booking(
            status="pending",
            payment_status="pending",
            amount="2.00",
            start=timezone.now() - timedelta(minutes=30),
        )
        quote = cancellation_quote(booking)
        self.assertTrue(quote["can_cancel"])
        cancelled, refund, changed = cancel_customer_booking(
            booking_id=booking.id,
            user=self.user,
        )
        self.assertTrue(changed)
        self.assertIsNone(refund)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(
            Transaction.objects.filter(
                booking=booking,
                transaction_type="refund",
            ).exists()
        )

    def test_my_booking_shows_refund_aware_cancel_confirmation(self):
        booking = self.make_booking(status="confirmed", payment_status="paid")
        self.client.force_login(self.user)
        response = self.client.get(reverse("back1:bookings"))
        self.assertContains(response, "Cancel Booking")
        self.assertContains(response, "eligible for a full refund of £4.00")
        booking.status = "active"; booking.save(update_fields=["status"])
        response = self.client.get(reverse("back1:bookings"))
        self.assertNotContains(response, 'action="' + reverse("back1:cancel_booking", args=[booking.id]) + '"')

    def test_today_rejects_only_ranges_that_have_completely_ended(self):
        now = timezone.make_aware(datetime.combine(timezone.localdate(), time(10, 30)))
        self.assertTrue(booking_range_has_ended(timezone.localdate(now), time(10), now=now))
        self.assertFalse(booking_range_has_ended(timezone.localdate(now), time(11), now=now))
        self.assertFalse(booking_range_has_ended(timezone.localdate(now), time(12), now=now))


class CustomerWalletLayoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wallet-layout", password="pw")
        self.other = User.objects.create_user(username="wallet-other", password="pw")
        self.admin = User.objects.create_user(username="wallet-admin", password="pw", is_staff=True)
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("22.00"))
        Wallet.objects.create(user=self.other, balance=Decimal("987.65"))

    def test_current_customer_wallet_is_shown_with_two_decimal_places(self):
        self.client.force_login(self.user)
        for route in (
            reverse("back1:customer-dashboard"),
            reverse("back1:booking-create"),
            reverse("back1:bookings"),
            reverse("back1:profile"),
        ):
            response = self.client.get(route)
            self.assertContains(response, "Wallet Balance", msg_prefix=route)
            self.assertContains(response, "£22.00", msg_prefix=route)
            self.assertNotContains(response, "£987.65", msg_prefix=route)

    def test_admin_layout_does_not_show_customer_wallet_widget(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("back1:admin-dashboard"))
        self.assertNotContains(response, "Wallet Balance")

    def test_missing_wallet_displays_zero_without_creating_record(self):
        missing_user = User.objects.create_user(username="wallet-missing", password="pw")
        self.client.force_login(missing_user)
        response = self.client.get(reverse("back1:customer-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "£0.00")
        self.assertFalse(Wallet.objects.filter(user=missing_user).exists())

    def test_wallet_widget_updates_after_normal_payment(self):
        booking = create_pending_booking(
            user=self.user,
            booking_date=timezone.localdate() + timedelta(days=2),
            start_time=time(10),
            end_time=time(11),
        )
        pay_booking(booking_id=booking.id, user=self.user)
        self.client.force_login(self.user)
        self.assertContains(
            self.client.get(reverse("back1:booking-success", args=[booking.id])),
            "£20.00",
        )

    def test_wallet_widget_updates_after_full_refund(self):
        booking = create_pending_booking(
            user=self.user,
            booking_date=timezone.localdate() + timedelta(days=3),
            start_time=time(10),
            end_time=time(11),
        )
        pay_booking(booking_id=booking.id, user=self.user)
        booking_start, _ = booking_bounds(booking)
        cancel_customer_booking(
            booking_id=booking.id,
            user=self.user,
            now=booking_start - timedelta(hours=25),
        )
        self.client.force_login(self.user)
        self.assertContains(
            self.client.get(reverse("back1:bookings")),
            "£22.00",
        )

    def test_wallet_widget_updates_after_overstay_payment(self):
        booking = Booking.objects.create(
            user=self.user,
            parking_slot=ParkingSlot.objects.get(slot_number="A01"),
            booking_date=timezone.localdate(),
            start_time=time(8),
            end_time=time(9),
            status="overtime",
            payment_status="outstanding",
            overstay_amount=Decimal("5.00"),
            outstanding_balance=Decimal("5.00"),
        )
        pay_overstay(booking_id=booking.id, user=self.user)
        self.client.force_login(self.user)
        self.assertContains(
            self.client.get(reverse("back1:bookings")),
            "£17.00",
        )


class PhaseThreeParkingManagementTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="phase3-admin", password="test-password", is_staff=True
        )
        self.customer = User.objects.create_user(
            username="phase3-customer", password="test-password"
        )
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.url = reverse("back1:admin-parking-state", args=[self.slot.id])

    def test_required_six_spaces_are_preserved(self):
        self.assertEqual(ParkingSlot.objects.count(), 6)

    def test_usable_query_excludes_each_admin_unavailable_state(self):
        for state, changes in (
            ("disabled", {"is_enabled": False}),
            ("maintenance", {"is_enabled": True, "is_under_maintenance": True}),
            ("backup", {"is_enabled": True, "is_under_maintenance": False, "is_backup": True}),
        ):
            fields = {
                "is_enabled": True,
                "is_under_maintenance": False,
                "is_backup": False,
            }
            fields.update(changes)
            ParkingSlot.objects.filter(pk=self.slot.pk).update(**fields)
            self.assertFalse(
                usable_parking_spaces().filter(pk=self.slot.pk).exists(), state
            )

    def test_physical_and_booking_flags_do_not_change_admin_usability(self):
        self.slot.is_physically_occupied = True
        self.slot.is_booking_reserved = True
        self.slot.save(update_fields=["is_physically_occupied", "is_booking_reserved"])
        self.assertTrue(usable_parking_spaces().filter(pk=self.slot.pk).exists())

    def test_admin_can_set_all_states_and_event_is_logged(self):
        self.client.force_login(self.admin)
        expected = {
            "disabled": (False, False, False),
            "maintenance": (True, True, False),
            "backup": (True, False, True),
            "normal": (True, False, False),
        }
        for state, flags in expected.items():
            response = self.client.post(self.url, {"state": state})
            self.assertEqual(response.status_code, 200)
            self.slot.refresh_from_db()
            self.assertEqual(
                (self.slot.is_enabled, self.slot.is_under_maintenance, self.slot.is_backup),
                flags,
            )
        self.assertEqual(
            SystemEvent.objects.filter(
                source="admin_parking_management", parking_slot=self.slot
            ).count(),
            4,
        )

    def test_customer_and_anonymous_users_cannot_change_state(self):
        self.assertEqual(self.client.post(self.url, {"state": "disabled"}).status_code, 401)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(self.url, {"state": "disabled"}).status_code, 403)

    def test_invalid_state_is_rejected_without_mutation(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {"state": "occupied"})
        self.assertEqual(response.status_code, 400)
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_enabled)


class PhaseOneModelFoundationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="phase1-customer",
            password="test-password",
        )
        self.slot = ParkingSlot.objects.get(slot_number="A01")

    def test_six_required_spaces_and_two_gates_are_preserved(self):
        self.assertEqual(
            set(ParkingSlot.objects.values_list("slot_number", flat=True)),
            {"A01", "A02", "A03", "A04", "A05", "A06"},
        )
        self.assertEqual(
            set(Gate.objects.values_list("gate_type", flat=True)),
            {"entrance", "exit"},
        )

    def test_parking_availability_states_are_independent(self):
        self.slot.is_enabled = True
        self.slot.is_physically_occupied = True
        self.slot.is_booking_reserved = True
        self.slot.is_under_maintenance = False
        self.slot.is_backup = False
        self.slot.save()

        self.assertTrue(self.slot.is_enabled)
        self.assertTrue(self.slot.is_physically_occupied)
        self.assertTrue(self.slot.is_booking_reserved)
        self.slot.is_backup = True
        self.slot.save(update_fields=["is_backup"])
        self.assertTrue(self.slot.is_backup)

    def test_booking_supports_payment_and_lifecycle_foundation(self):
        booking = Booking.objects.create(
            user=self.user,
            parking_slot=self.slot,
            booking_date=date(2026, 8, 12),
            start_time=time(10, 0),
            end_time=time(11, 0),
            normal_parking_amount=Decimal("2.00"),
            overstay_amount=Decimal("20.00"),
            outstanding_balance=Decimal("20.00"),
        )

        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.payment_status, "pending")
        self.assertFalse(booking.confirmation_email_sent)
        self.assertFalse(booking.reminder_email_sent)

    def test_payment_can_be_linked_to_booking_and_categorised(self):
        booking = Booking.objects.create(
            user=self.user,
            parking_slot=self.slot,
            booking_date=date(2026, 8, 12),
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        payment = Transaction.objects.create(
            user=self.user,
            booking=booking,
            transaction_type="penalty",
            payment_category="overstay",
            payment_status="outstanding",
            amount=Decimal("20.00"),
        )

        self.assertEqual(payment.booking, booking)
        self.assertEqual(payment.payment_category, "overstay")
        self.assertEqual(payment.payment_status, "outstanding")

    def test_sensor_event_alert_and_notification_foundation(self):
        sensor = SensorData.objects.create(
            sensor_id="phase1-entrance",
            sensor_type="entrance",
            location="Entrance Gate",
            value="vehicle_detected",
            connection_status="online",
            condition_status="normal",
        )
        event = SystemEvent.objects.create(
            event_type="vehicle_detected",
            source="phase1-entrance",
            description="Vehicle detected at entrance",
            user=self.user,
            sensor=sensor,
            parking_slot=self.slot,
        )
        alert = Alert.objects.create(
            alert_type="sensor_offline",
            severity="warning",
            message="Entrance sensor offline",
            sensor=sensor,
        )
        emergency = Emergency.objects.create(
            emergency_type="sensor_error",
            description="Sensor requires attention",
        )
        notification = EmergencyNotification.objects.create(
            emergency=emergency,
            recipient=self.user,
            sent_by=self.user,
            message="Please follow safety instructions",
        )

        self.assertTrue(timezone.is_aware(sensor.last_reading_at))
        self.assertTrue(timezone.is_aware(event.timestamp))
        self.assertFalse(alert.acknowledged)
        self.assertEqual(notification.status, "pending")

    def test_default_parking_rates_have_single_source(self):
        rate = ParkingRate.objects.first()
        self.assertIsNotNone(rate)
        self.assertEqual(rate.rate_per_hour, Decimal("2.00"))
        self.assertEqual(rate.overtime_rate_per_hour, Decimal("20.00"))


class PhaseTwoAuthenticationAndPermissionTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer-one",
            email="customer-one@example.com",
            password="StrongTestPassword123!",
        )
        self.other_customer = User.objects.create_user(
            username="customer-two",
            email="customer-two@example.com",
            password="StrongTestPassword123!",
        )
        self.admin_user = User.objects.create_user(
            username="staff-user",
            email="staff@example.com",
            password="StrongTestPassword123!",
            is_staff=True,
        )
        self.slot = ParkingSlot.objects.get(slot_number="A01")
        self.own_booking = Booking.objects.create(
            user=self.customer,
            parking_slot=self.slot,
            booking_date=date(2026, 8, 12),
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        self.other_booking = Booking.objects.create(
            user=self.other_customer,
            parking_slot=ParkingSlot.objects.get(slot_number="A02"),
            booking_date=date(2026, 8, 13),
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        self.customer_wallet = Wallet.objects.create(
            user=self.customer,
            balance=Decimal("10.00"),
        )
        self.other_wallet = Wallet.objects.create(
            user=self.other_customer,
            balance=Decimal("10.00"),
        )

    def test_anonymous_private_browser_pages_redirect_to_login(self):
        for route_name in (
            "back1:customer-dashboard",
            "back1:bookings",
            "back1:profile",
            "back1:booking-create",
            "back1:admin-dashboard",
        ):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response["Location"])

    def test_customer_can_access_customer_pages_but_not_admin_dashboard(self):
        self.client.force_login(self.customer)
        self.assertEqual(
            self.client.get(reverse("back1:customer-dashboard")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("back1:bookings")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("back1:profile")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("back1:admin-dashboard")).status_code,
            403,
        )

    def test_admin_can_access_admin_dashboard_and_is_redirected_from_customer_dashboard(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(
            self.client.get(reverse("back1:admin-dashboard")).status_code,
            200,
        )
        response = self.client.get(reverse("back1:customer-dashboard"))
        self.assertRedirects(response, reverse("back1:admin-dashboard"))

    def test_registration_creates_and_logs_in_non_staff_customer(self):
        response = self.client.post(
            reverse("back1:register"),
            {
                "username": "new-customer",
                "first_name": "New",
                "last_name": "Customer",
                "email": "new-customer@example.com",
                "password1": "AnotherStrongPassword123!",
                "password2": "AnotherStrongPassword123!",
            },
        )
        user = User.objects.get(username="new-customer")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("AnotherStrongPassword123!"))
        self.assertRedirects(response, reverse("back1:customer-dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse("back1:register"),
            {
                "username": "duplicate-email",
                "first_name": "Duplicate",
                "last_name": "Email",
                "email": "CUSTOMER-ONE@example.com",
                "password1": "AnotherStrongPassword123!",
                "password2": "AnotherStrongPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertFalse(User.objects.filter(username="duplicate-email").exists())

    def test_role_aware_login_redirects_customer_and_admin(self):
        customer_response = self.client.post(
            reverse("login"),
            {"username": self.customer.username, "password": "StrongTestPassword123!"},
        )
        self.assertRedirects(
            customer_response,
            reverse("back1:customer-dashboard"),
        )
        self.client.logout()
        admin_response = self.client.post(
            reverse("login"),
            {"username": self.admin_user.username, "password": "StrongTestPassword123!"},
        )
        self.assertRedirects(
            admin_response,
            reverse("back1:admin-dashboard"),
        )

    def test_login_next_parameter_uses_django_safe_redirect_handling(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://malicious.example/",
            {"username": self.customer.username, "password": "StrongTestPassword123!"},
        )
        self.assertRedirects(response, reverse("back1:customer-dashboard"))

    def test_my_booking_page_and_api_only_show_customer_own_bookings(self):
        self.client.force_login(self.customer)
        page = self.client.get(reverse("back1:bookings"))
        self.assertContains(page, f"Booking #{self.own_booking.id}")
        self.assertNotContains(page, f"Booking #{self.other_booking.id}")

        api = self.client.get(reverse("back1:booking_list"))
        self.assertEqual(api.status_code, 200)
        returned_ids = {item["id"] for item in api.json()["bookings"]}
        self.assertEqual(returned_ids, {self.own_booking.id})

    def test_customer_cannot_access_another_customers_booking_action(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("back1:cancel_booking", args=[self.other_booking.id])
        )
        self.assertEqual(response.status_code, 403)
        self.other_booking.refresh_from_db()
        self.assertEqual(self.other_booking.status, "pending")

    def test_customer_booking_api_uses_request_user_and_pending_status(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("back1:create_booking"),
            {
                "user": self.other_customer.id,
                "parking_slot": ParkingSlot.objects.get(slot_number="A03").id,
                "booking_date": "2026-08-14",
                "start_time": "12:00",
                "end_time": "13:00",
                "status": "confirmed",
                "payment_status": "paid",
            },
        )
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(id=response.json()["booking_id"])
        self.assertEqual(booking.user, self.customer)
        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.payment_status, "pending")

    def test_customer_booking_form_uses_request_user(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("back1:booking-create"),
            {
                "parking_slot": ParkingSlot.objects.get(slot_number="A04").id,
                "booking_date": "2026-08-15",
                "start_time": "14:00",
                "end_time": "15:00",
                "user": self.other_customer.id,
                "status": "confirmed",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(booking_date=date(2026, 8, 15))
        self.assertEqual(booking.user, self.customer)
        self.assertEqual(booking.status, "pending")

    def test_gate_mutation_requires_admin(self):
        gate = Gate.objects.get(gate_type="entrance")
        url = reverse("back1:open_gate", args=[gate.id])

        self.assertEqual(self.client.post(url).status_code, 401)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(url).status_code, 403)
        gate.refresh_from_db()
        self.assertFalse(gate.is_open)

        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.post(url).status_code, 200)
        gate.refresh_from_db()
        self.assertTrue(gate.is_open)

    def test_wallet_access_requires_login_and_ownership(self):
        own_url = reverse("back1:wallet_detail", args=[self.customer.id])
        other_url = reverse("back1:wallet_detail", args=[self.other_customer.id])
        other_add_url = reverse(
            "back1:add_wallet_balance", args=[self.other_customer.id]
        )

        self.assertEqual(self.client.get(own_url).status_code, 401)
        self.assertEqual(self.client.post(other_add_url, {"amount": "5"}).status_code, 401)

        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(own_url).status_code, 200)
        self.assertEqual(self.client.get(other_url).status_code, 403)
        self.assertEqual(
            self.client.post(other_add_url, {"amount": "5"}).status_code,
            403,
        )

    def test_customer_cannot_access_parking_admin_but_admin_can(self):
        url = reverse("admin:back1_parkingslot_changelist")
        self.client.force_login(self.customer)
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.admin_user.is_superuser = True
        self.admin_user.save(update_fields=["is_superuser"])
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_sensor_and_emergency_mutations_are_temporarily_admin_only(self):
        sensor_url = reverse("back1:update_sensor")
        emergency_url = reverse("back1:create_emergency")
        payload = {
            "sensor_id": "phase2-temporary-device",
            "sensor_type": "entrance",
            "location": "Entrance",
            "value": "clear",
        }

        self.assertEqual(self.client.post(sensor_url, payload).status_code, 401)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(sensor_url, payload).status_code, 403)
        self.assertEqual(
            self.client.post(
                emergency_url,
                {"emergency_type": "maintenance", "description": "test"},
            ).status_code,
            403,
        )
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.post(sensor_url, payload).status_code, 201)

    def test_admin_can_view_all_bookings_through_admin_authorized_api(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("back1:booking_list"))
        self.assertEqual(response.status_code, 200)
        returned_ids = {item["id"] for item in response.json()["bookings"]}
        self.assertEqual(returned_ids, {self.own_booking.id, self.other_booking.id})

    def test_profile_updates_only_allowed_current_user_fields(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("back1:profile"),
            {
                "first_name": "Updated",
                "last_name": "Customer",
                "email": "updated@example.com",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )
        self.assertRedirects(response, reverse("back1:profile"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.email, "updated@example.com")
        self.assertFalse(self.customer.is_staff)
        self.assertFalse(self.customer.is_superuser)

    def test_logout_clears_authenticated_session(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        dashboard = self.client.get(reverse("back1:customer-dashboard"))
        self.assertEqual(dashboard.status_code, 302)
