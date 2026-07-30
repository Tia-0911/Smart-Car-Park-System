from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ParkingSlot, Booking, Gate
from .serializers import ParkingSlotSerializer, BookingSerializer, GateSerializer


# ==========================
# Dashboard
# ==========================

def dashboard(request):
    slots = ParkingSlot.objects.all()
    bookings = Booking.objects.all()
    gates = Gate.objects.all()

    return render(request, 'back1/dashboard.html', {
        'slots': slots,
        'bookings': bookings,
        'gates': gates
    })


# ==========================
# API Views
# ==========================

@api_view(["GET"])
def parking_slots_api(request):
    slots = ParkingSlot.objects.all()

    serializer = ParkingSlotSerializer(
        slots,
        many=True
    )

    return Response(serializer.data)


@api_view(["GET"])
def bookings_api(request):
    bookings = Booking.objects.all()

    serializer = BookingSerializer(
        bookings,
        many=True
    )

    return Response(serializer.data)


@api_view(["GET"])
def gates_api(request):
    gates = Gate.objects.all()

    serializer = GateSerializer(
        gates,
        many=True
    )

    return Response(serializer.data)


# ==========================
# Class-Based Views
# ==========================

class ParkingSlotListView(ListView):
    model = ParkingSlot
    template_name = 'back1/parking_slots.html'
    context_object_name = 'slots'


class BookingListView(ListView):
    model = Booking
    template_name = 'back1/bookings.html'
    context_object_name = 'bookings'


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    fields = [
        'parking_slot',
        'start_time',
        'end_time',
        'qr_code'
    ]
    template_name = 'back1/booking_form.html'