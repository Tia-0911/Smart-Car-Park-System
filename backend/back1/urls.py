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



    # New Sensor Update API
    path(
        'api/sensors/update/',
        views.sensor_update,
        name='sensor_update'
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
    # Booking API
    # ==========================


    path(
        'api/bookings/',
        views.bookings_api,
        name='bookings_api'
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