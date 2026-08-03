from django.shortcuts import render
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ParkingSlot, Booking, SensorData, Gate

from .serializers import (
    ParkingSlotSerializer,
    BookingSerializer,
    GateSerializer
)





# ==========================
# Dashboard
# ==========================

def dashboard(request):

    slots = ParkingSlot.objects.all()

    bookings = Booking.objects.all()

    gates = Gate.objects.all()


    sensors = SensorData.objects.all().order_by(
        '-created_at'
    )


    latest = sensors.first()

    history = sensors[:10]



    total_slots = slots.count()



    available_slots = slots.filter(
        status="available"
    ).count()



    occupied_slots = slots.filter(
        status="Occupied"
    ).count()
    occupancy_percentage = 0

    if total_slots > 0:
        occupancy_percentage = int(
            (occupied_slots / total_slots) * 100
        )



    latest_bookings = bookings.order_by(
        '-created_at'
    )[:5]



    return render(
        request,
        'back1/dashboard.html',
        {

            'slots': slots,

            'bookings': bookings,

            'gates': gates,

            'latest': latest,

            'history': history,


            'total_slots': total_slots,

            'available_slots': available_slots,

            'occupied_slots': occupied_slots,
            
            'occupancy_percentage': occupancy_percentage,

            'latest_bookings': latest_bookings,

        }
    )







# ==========================
# Sensor API
# ==========================


@api_view(["GET"])
def latest_reading(request):

    sensor = SensorData.objects.order_by(
        '-created_at'
    ).first()


    if not sensor:

        return Response({
            "message": "No sensor data available"
        })



    return Response({

        "sensor_type": sensor.sensor_type,

        "value": sensor.value,

        "parking_slot": sensor.parking_slot.slot_number,

        "created_at": sensor.created_at

    })






@api_view(["GET"])
def readings_history(request):

    sensors = SensorData.objects.all().order_by(
        '-created_at'
    )


    data = []


    for sensor in sensors:


        data.append({

            "sensor_type": sensor.sensor_type,

            "value": sensor.value,

            "parking_slot": sensor.parking_slot.slot_number,

            "created_at": sensor.created_at

        })


    return Response(data)







# ==========================
# NEW Sensor Update API
# ==========================


@api_view(["POST"])
def sensor_update(request):


    sensor_type = request.data.get(
        "sensor_type"
    )


    value = request.data.get(
        "value"
    )


    slot_number = request.data.get(
        "parking_slot"
    )



    try:


        slot = ParkingSlot.objects.get(
            slot_number=slot_number
        )



        sensor = SensorData.objects.create(

            sensor_type=sensor_type,

            value=value,

            parking_slot=slot

        )



        # Update Parking Slot Status


        if str(value).lower() == "occupied":

            slot.status = "Occupied"


        else:

            slot.status = "available"



        slot.save()



        return Response({

            "message": "Sensor data updated successfully",

            "parking_slot": slot.slot_number,

            "status": slot.status,

            "created_at": sensor.created_at

        })



    except ParkingSlot.DoesNotExist:


        return Response({

            "error": "Parking slot not found"

        }, status=404)








# ==========================
# Parking API
# ==========================


@api_view(["GET"])
def parking_slots_api(request):

    slots = ParkingSlot.objects.all()


    serializer = ParkingSlotSerializer(
        slots,
        many=True
    )


    return Response(serializer.data)







# ==========================
# Booking API
# ==========================


@api_view(["GET"])
def bookings_api(request):

    bookings = Booking.objects.all()


    serializer = BookingSerializer(
        bookings,
        many=True
    )


    return Response(serializer.data)








# ==========================
# Gate API
# ==========================


@api_view(["GET"])
def gates_api(request):

    gates = Gate.objects.all()


    serializer = GateSerializer(
        gates,
        many=True
    )


    return Response(serializer.data)






@api_view(["POST"])
def open_gate(request, gate_id):

    gate = Gate.objects.get(
        id=gate_id
    )


    gate.is_open = True

    gate.save()



    return Response({

        "message": "Gate opened successfully",

        "gate": gate.gate_name,

        "status": gate.is_open

    })







@api_view(["POST"])
def close_gate(request, gate_id):

    gate = Gate.objects.get(
        id=gate_id
    )


    gate.is_open = False

    gate.save()



    return Response({

        "message": "Gate closed successfully",

        "gate": gate.gate_name,

        "status": gate.is_open

    })








# ==========================
# Sensor Views
# ==========================


class SensorReadingListView(ListView):

    model = SensorData

    template_name = 'back1/sensor_readings.html'

    context_object_name = 'sensors'






class SensorReadingDetailView(DetailView):

    model = SensorData

    template_name = 'back1/sensor_detail.html'

    context_object_name = 'sensor'






class ParkingSlotListView(ListView):

    model = ParkingSlot

    template_name = 'back1/parking_slots.html'

    context_object_name = 'slots'







# ==========================
# Booking Views
# ==========================


class BookingListView(ListView):

    model = Booking

    template_name = 'back1/bookings.html'

    context_object_name = 'bookings'







class BookingCreateView(LoginRequiredMixin, CreateView):

    model = Booking


    fields = [

        'parking_slot',

        'booking_date',

        'start_time',

        'end_time'

    ]



    template_name = 'back1/booking_form.html'


    success_url = '/'




    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)


        context["hours"] = [

            f"{hour:02d}:00"

            for hour in range(24)

        ]



        slots = ParkingSlot.objects.all()



        selected_date = self.request.GET.get(
            "date"
        )


        selected_start = self.request.GET.get(
            "start"
        )


        selected_end = self.request.GET.get(
            "end"
        )



        slot_status = []



        for slot in slots:


            available = True



            if selected_date and selected_start and selected_end:


                conflict = Booking.objects.filter(

                    parking_slot=slot,

                    booking_date=selected_date,

                    start_time__lt=selected_end,

                    end_time__gt=selected_start

                ).exists()



                if conflict:

                    available = False




            slot_status.append({

                "id": slot.id,

                "slot_number": slot.slot_number,

                "available": available

            })



        context["slot_status"] = slot_status


        return context






    def form_valid(self, form):


        form.instance.user = self.request.user



        slot = form.cleaned_data["parking_slot"]

        date = form.cleaned_data["booking_date"]

        start = form.cleaned_data["start_time"]

        end = form.cleaned_data["end_time"]




        conflict = Booking.objects.filter(

            parking_slot=slot,

            booking_date=date,

            start_time__lt=end,

            end_time__gt=start

        ).exists()



        if conflict:


            form.add_error(

                None,

                "This parking slot is already booked for this time."

            )


            return self.form_invalid(form)





        messages.success(

            self.request,

            "Booking created successfully!"

        )



        return super().form_valid(form)