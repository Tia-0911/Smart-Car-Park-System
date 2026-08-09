from django.urls import path
from . import views


app_name = "back1"


urlpatterns = [

    # ==========================
    # Dashboard
    # ==========================

    path(
        "",
        views.dashboard,
        name="dashboard"
    ),


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
        views.BookingListView.as_view(),
        name="bookings"
    ),


    path(
        "bookings/new/",
        views.BookingCreateView.as_view(),
        name="booking-create"
    ),

]