from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SensorReading
from .serializers import SensorReadingSerializer


def dashboard(request):
    latest = SensorReading.objects.last()
    history = SensorReading.objects.order_by('-created_at')[:10]

    return render(request, 'back1/dashboard.html', {
        'latest': latest,
        'history': history
    })


@api_view(["GET"])
def latest_reading(request):
    reading = SensorReading.objects.last()

    if not reading:
        return Response({"detail": "No data"}, status=204)

    serializer = SensorReadingSerializer(reading)
    return Response(serializer.data)


@api_view(["GET"])
def readings_history(request):
    readings = SensorReading.objects.order_by("-created_at")[:20]

    serializer = SensorReadingSerializer(readings, many=True)
    return Response(serializer.data)


# ==========================
# Class-Based Views
# ==========================

class SensorReadingListView(ListView):
    model = SensorReading
    ordering = ['-created_at']
    template_name = 'back1/readings.html'
    context_object_name = 'readings'
    paginate_by = 10


class SensorReadingDetailView(DetailView):
    model = SensorReading
    template_name = 'back1/reading_detail.html'


class SensorReadingCreateView(LoginRequiredMixin, CreateView):
    model = SensorReading
    fields = [
        'temperature',
        'humidity',
        'device_id'
    ]
    template_name = 'back1/sensorreading_form.html'