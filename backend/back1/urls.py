from django.urls import path
from . import views

app_name = 'back1'

urlpatterns = [

    path('', views.dashboard, name='dashboard'),

    # API
    path(
        'api/sensors/latest',
        views.latest_reading,
        name='latest_reading'
    ),

    path(
        'api/sensors/history',
        views.readings_history,
        name='readings_history'
    ),


    # Class-Based Views (Sensor Readings)

    # List all readings
    path(
        'readings/',
        views.SensorReadingListView.as_view(),
        name='readings'
    ),

    # Detail page
    path(
        'readings/<int:pk>/',
        views.SensorReadingDetailView.as_view(),
        name='reading-detail'
    ),

    # Create new reading
    path(
        'readings/new/',
        views.SensorReadingCreateView.as_view(),
        name='reading-create'
    ),
]