from django.urls import path
from . import views


app_name = 'back1'


urlpatterns = [

    # ==========================
    # Dashboard
    # ==========================

    path(
        '',
        views.dashboard,
        name='dashboard'
    ),



    # ==========================
    # Dashboard Monitoring API
    # ==========================

    path(
        'api/dashboard/sensor-status/',
        views.dashboard_sensor_status,
        name='dashboard_sensor_status'
    ),


    path(
        'api/dashboard/environment/',
        views.dashboard_environment,
        name='dashboard_environment'
    ),


    path(
        'api/dashboard/emergency/',
        views.dashboard_emergency,
        name='dashboard_emergency'
    ),





    # ==========================
    # Sensor API
    # ==========================

    path(
        'api/sensors/latest/',
        views.latest_reading,
        name='latest_reading'
    ),


    path(
        'api/sensors/history/',
        views.readings_history,
        name='readings_history'
    ),


    path(
        'api/sensors/update/',
        views.sensor_update,
        name='sensor_update'
    ),


    path(
        'api/sensors/fire-check/',
        views.fire_sensor_check,
        name='fire_sensor_check'
    ),





    # ==========================
    # Parking API
    # ==========================

    path(
        'api/parking-slots/',
        views.parking_slots_api,
        name='parking_slots_api'
    ),





    # ==========================
    # Availability API
    # ==========================

    path(
        'api/availability/',
        views.check_availability,
        name='check_availability'
    ),





    # ==========================
    # Booking API
    # ==========================

    path(
        'api/bookings/',
        views.bookings_api,
        name='bookings_api'
    ),


    path(
        'api/bookings/create/',
        views.create_booking,
        name='create_booking'
    ),


    path(
        'api/bookings/<int:booking_id>/cancel/',
        views.cancel_booking,
        name='cancel_booking'
    ),


    path(
        'api/bookings/<int:booking_id>/entry/',
        views.car_entry,
        name='car_entry'
    ),


    path(
        'api/bookings/<int:booking_id>/exit/',
        views.car_exit,
        name='car_exit'
    ),





    # ==========================
    # Gate API
    # ==========================

    path(
        'api/gates/',
        views.gates_api,
        name='gates_api'
    ),


    path(
        'api/gates/<int:gate_id>/open/',
        views.open_gate,
        name='open_gate'
    ),


    path(
        'api/gates/<int:gate_id>/close/',
        views.close_gate,
        name='close_gate'
    ),


    path(
        'api/gates/<int:gate_id>/exit-open/',
        views.open_exit_gate,
        name='open_exit_gate'
    ),





    # ==========================
    # Wallet API
    # ==========================

    path(
        'api/wallet/<int:user_id>/',
        views.wallet_detail,
        name='wallet_detail'
    ),


    path(
        'api/wallet/<int:user_id>/add/',
        views.add_wallet_balance,
        name='add_wallet_balance'
    ),





    # ==========================
    # Transaction API
    # ==========================

    path(
        'api/transactions/<int:user_id>/',
        views.transaction_history,
        name='transaction_history'
    ),





    # ==========================
    # Emergency API
    # ==========================

    path(
        'api/emergency/',
        views.emergency_list,
        name='emergency_list'
    ),


    path(
        'api/emergency/create/',
        views.create_emergency,
        name='create_emergency'
    ),


    path(
        'api/emergency/<int:emergency_id>/resolve/',
        views.resolve_emergency,
        name='resolve_emergency'
    ),





    # ==========================
    # Booking Pages
    # ==========================

    path(
        'bookings/',
        views.BookingListView.as_view(),
        name='bookings'
    ),


    path(
        'bookings/new/',
        views.BookingCreateView.as_view(),
        name='booking-create'
    ),

]