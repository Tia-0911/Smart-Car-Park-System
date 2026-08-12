from django.urls import path
from . import views


app_name = "back1"


urlpatterns = [

    # ==========================
    # Dashboard
    # ==========================

    path(
        "",
        views.root_redirect,
        name="home"
    ),

    path(
        "register/",
        views.register,
        name="register"
    ),

    path(
        "dashboard/",
        views.customer_dashboard,
        name="customer-dashboard"
    ),

    path(
        "admin-dashboard/",
        views.dashboard,
        name="admin-dashboard"
    ),

    path(
        "profile/",
        views.profile,
        name="profile"
    ),
    path("admin-dashboard/bookings/", views.admin_bookings, name="admin-bookings"),
    path("admin-dashboard/bookings/<int:booking_id>/edit/", views.admin_booking_edit, name="admin-booking-edit"),
    path("admin-dashboard/bookings/<int:booking_id>/delete/", views.admin_booking_delete, name="admin-booking-delete"),
    path("admin-dashboard/customers/", views.admin_customers, name="admin-customers"),
    path("admin-dashboard/customers/<int:user_id>/edit/", views.admin_customer_edit, name="admin-customer-edit"),
    path("admin-dashboard/customers/<int:user_id>/delete/", views.admin_customer_delete, name="admin-customer-delete"),
    path("admin-dashboard/events/", views.admin_events, name="admin-events"),
    path("admin-dashboard/alerts/", views.admin_alerts, name="admin-alerts"),
    path("admin-dashboard/sensors/", views.admin_sensors, name="admin-sensors"),
    path("admin-dashboard/revenue/", views.admin_revenue, name="admin-revenue"),
    path("api/alerts/<int:alert_id>/acknowledge/", views.acknowledge_alert, name="acknowledge-alert"),
    path("admin-dashboard/emergencies/<int:emergency_id>/notify/", views.emergency_notify, name="emergency-notify"),


    # ==========================
    # Dashboard Monitoring API
    # ==========================

    path(
        "api/dashboard/sensor-status/",
        views.dashboard_sensor_status,
        name="dashboard_sensor_status"
    ),


    path(
        "api/dashboard/environment/",
        views.latest_sensor,
        name="dashboard_environment"
    ),


    path(
        "api/dashboard/emergency/",
        views.emergency_status,
        name="dashboard_emergency"
    ),



    # ==========================
    # Sensor API
    # ==========================

    path(
        "api/sensors/latest/",
        views.latest_sensor,
        name="latest_sensor"
    ),


    path(
        "api/sensors/history/",
        views.sensor_history,
        name="sensor_history"
    ),


    path(
        "api/sensors/update/",
        views.update_sensor,
        name="update_sensor"
    ),
    path("api/device/sensors/update/", views.update_sensor, name="device-sensor-update"),


    path(
        "api/sensors/fire-check/",
        views.fire_sensor_check,
        name="fire_sensor_check"
    ),



    # ==========================
    # Parking Slot API
    # ==========================

    path(
        "api/parking-slots/",
        views.parking_slots,
        name="parking_slots"
    ),

    path(
        "api/parking-slots/<int:slot_id>/admin-state/",
        views.admin_set_parking_state,
        name="admin-parking-state"
    ),
    path(
        "api/bookings/availability/",
        views.booking_availability,
        name="booking-availability",
    ),



    # ==========================
    # Booking API
    # ==========================

    path(
        "api/bookings/",
        views.booking_list,
        name="booking_list"
    ),


    path(
        "api/bookings/create/",
        views.create_booking,
        name="create_booking"
    ),


    path(
        "api/bookings/<int:booking_id>/cancel/",
        views.cancel_booking,
        name="cancel_booking"
    ),


    path(
        "api/bookings/<int:booking_id>/entry/",
        views.car_entry,
        name="car_entry"
    ),


    path(
        "api/bookings/<int:booking_id>/exit/",
        views.car_exit,
        name="car_exit"
    ),



    # ==========================
    # Gate API
    # ==========================

    path(
        "api/gates/",
        views.gates_api,
        name="gates_api"
    ),
    path(
        "api/device/gates/commands/",
        views.device_gate_commands,
        name="device-gate-commands",
    ),
    path(
        "api/device/gates/commands/<int:command_id>/claim/",
        views.device_claim_gate_command,
        name="device-claim-gate-command",
    ),
    path(
        "api/device/gates/commands/<int:command_id>/acknowledge/",
        views.device_acknowledge_gate_command,
        name="device-acknowledge-gate-command",
    ),


    path(
        "api/gates/<int:gate_id>/open/",
        views.open_gate,
        name="open_gate"
    ),


    path(
        "api/gates/<int:gate_id>/close/",
        views.close_gate,
        name="close_gate"
    ),



    # ==========================
    # Revenue API
    # ==========================

    path(
        "api/revenue/",
        views.revenue_summary,
        name="revenue_summary"
    ),



    # ==========================
    # Wallet API
    # ==========================

    path(
        "api/wallet/<int:user_id>/",
        views.wallet_detail,
        name="wallet_detail"
    ),


    path(
        "api/wallet/<int:user_id>/add/",
        views.add_wallet_balance,
        name="add_wallet_balance"
    ),



    # ==========================
    # Transaction API
    # ==========================

    path(
        "api/transactions/<int:user_id>/",
        views.transaction_history,
        name="transaction_history"
    ),



    # ==========================
    # Emergency API
    # ==========================

    path(
        "api/emergency/",
        views.emergency_list,
        name="emergency_list"
    ),


    path(
        "api/emergency/create/",
        views.create_emergency,
        name="create_emergency"
    ),


    path(
        "api/emergency/<int:emergency_id>/resolve/",
        views.resolve_emergency,
        name="resolve_emergency"
    ),



    # ==========================
    # Booking Pages
    # ==========================

    path(
        "bookings/",
        views.my_bookings,
        name="bookings"
    ),


    path(
        "bookings/new/",
        views.BookingCreateView.as_view(),
        name="booking-create"
    ),
    path(
        "bookings/<int:booking_id>/payment/",
        views.booking_payment,
        name="booking-payment",
    ),
    path(
        "bookings/<int:booking_id>/success/",
        views.booking_success,
        name="booking-success",
    ),
    path("api/bookings/<int:booking_id>/gate/<str:gate_type>/", views.customer_gate_request, name="customer-gate-request"),
    path("bookings/<int:booking_id>/overstay-payment/", views.overstay_payment, name="overstay-payment"),

]
