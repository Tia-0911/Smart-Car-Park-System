# ==========================
# IMPORTS
# ==========================

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy


from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


from .models import (
    ParkingSlot,
    SensorData,
    Booking,
    Gate,
    Wallet,
    Transaction,
    Emergency,
    ParkingRate
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



# ==========================
# ADMIN DASHBOARD
# ==========================


def dashboard(request):

    return render(
        request,
        "back1/dashboard.html"
    )



# ==========================
# DASHBOARD MONITORING API
# ==========================



# --------------------------
# Sensor Status
# --------------------------


@api_view(["GET"])
def dashboard_sensor_status(request):

    sensors = SensorData.objects.all().order_by(
        "-updated_at"
    )


    sensor_list = []


    online = 0
    error = 0



    for sensor in sensors:


        if sensor.status == "active":
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


            "status":
            sensor.status,


            "last_update":
            sensor.updated_at

        })



    return Response({

        "total_sensors":
        sensors.count(),


        "online":
        online,


        "error":
        error,


        "sensors":
        sensor_list

    })




# --------------------------
# Environmental Monitoring
# Temperature / Humidity / Fire
# --------------------------


@api_view(["GET"])
def dashboard_environment(request):


    temperature = SensorData.objects.filter(
        sensor_type="temperature"
    ).order_by(
        "-created_at"
    ).first()



    humidity = SensorData.objects.filter(
        sensor_type="humidity"
    ).order_by(
        "-created_at"
    ).first()



    fire = SensorData.objects.filter(
        sensor_type="fire"
    ).order_by(
        "-created_at"
    ).first()



    return Response({


        "temperature": {


            "value":
            temperature.value
            if temperature else "No Data",


            "status":
            temperature.status
            if temperature else "inactive"

        },



        "humidity": {


            "value":
            humidity.value
            if humidity else "No Data",


            "status":
            humidity.status
            if humidity else "inactive"

        },



        "fire": {


            "value":
            fire.value
            if fire else "No Data",


            "status":
            fire.status
            if fire else "inactive"

        }



    })




# --------------------------
# Emergency Alert
# --------------------------


@api_view(["GET"])
def dashboard_emergency(request):


    alerts = Emergency.objects.filter(
        status="active"
    ).order_by(
        "-created_at"
    )



    serializer = EmergencySerializer(
        alerts,
        many=True
    )



    return Response(
        serializer.data
    )
# ==========================
# SENSOR API
# ==========================


@api_view(["GET"])
def latest_reading(request):

    sensor = SensorData.objects.order_by(
        "-created_at"
    ).first()



    if not sensor:

        return Response({

            "message":
            "No sensor data available"

        })



    return Response(
        SensorDataSerializer(sensor).data
    )





@api_view(["GET"])
def readings_history(request):

    sensors = SensorData.objects.all().order_by(
        "-created_at"
    )[:20]



    serializer = SensorDataSerializer(
        sensors,
        many=True
    )



    return Response(
        serializer.data
    )





# ==========================
# SENSOR UPDATE
# Raspberry Pi sends data here
# ==========================


@api_view(["POST"])
def sensor_update(request):


    sensor_id = request.data.get(
        "sensor_id"
    )


    sensor_type = request.data.get(
        "sensor_type"
    )


    value = request.data.get(
        "value"
    )


    location = request.data.get(
        "location",
        ""
    )


    sensor_status = request.data.get(
        "status",
        "active"
    )



    sensor, created = SensorData.objects.update_or_create(


        sensor_id=sensor_id,


        defaults={

            "sensor_type":
            sensor_type,


            "value":
            value,


            "location":
            location,


            "status":
            sensor_status

        }

    )



    # ==========================
    # CAR SENSOR LOGIC
    # ==========================


    if sensor_type == "car":


        slot_number = request.data.get(
            "parking_slot"
        )



        if slot_number:


            try:

                slot = ParkingSlot.objects.get(
                    slot_number=slot_number
                )


                sensor.parking_slot = slot
                sensor.save()



                if str(value).lower() == "occupied":


                    slot.status = "occupied"



                    booking = Booking.objects.filter(

                        parking_slot=slot,

                        status="confirmed"

                    ).order_by(
                        "-created_at"
                    ).first()



                    if booking:


                        booking.status = "parked"

                        booking.actual_arrival_time = timezone.now()

                        booking.save()



                else:


                    slot.status = "available"



                    booking = Booking.objects.filter(

                        parking_slot=slot,

                        status="parked"

                    ).order_by(
                        "-created_at"
                    ).first()



                    if booking:


                        booking.status = "completed"

                        booking.actual_exit_time = timezone.now()

                        booking.save()



                slot.save()



            except ParkingSlot.DoesNotExist:

                pass





    # ==========================
    # TEMPERATURE EMERGENCY CHECK
    # ==========================


    if sensor_type == "temperature":


        try:

            temperature = float(value)



            if temperature >= 60:


                Emergency.objects.create(

                    emergency_type="sensor_error",


                    description=(

                        f"High temperature detected. "

                        f"Sensor {sensor_id}. "

                        f"Current value: {temperature}°C "

                        f"Location: {location}"

                    ),


                    status="active"

                )


        except:

            pass





    # ==========================
    # HUMIDITY EMERGENCY CHECK
    # ==========================


    if sensor_type == "humidity":


        try:

            humidity = float(value)



            if humidity >= 90:


                Emergency.objects.create(

                    emergency_type="sensor_error",


                    description=(

                        f"High humidity detected. "

                        f"Sensor {sensor_id}. "

                        f"Current value: {humidity}% "

                        f"Location: {location}"

                    ),


                    status="active"

                )


        except:

            pass





    # ==========================
    # FIRE SENSOR EMERGENCY CHECK
    # ==========================


    if sensor_type == "fire":


        if str(value).lower() in [

            "fire",

            "detected",

            "danger"

        ]:



            Emergency.objects.create(

                emergency_type="fire",


                description=(

                    f"Fire detected. "

                    f"Sensor {sensor_id}. "

                    f"Location: {location}"

                ),


                status="active"

            )





    return Response({


        "message":

        "Sensor updated successfully",



        "sensor":

        SensorDataSerializer(sensor).data

    })
# ==========================
# PARKING AVAILABILITY API
# ==========================


@api_view(["GET"])
def check_availability(request):

    date = request.GET.get(
        "date"
    )


    start_time = request.GET.get(
        "start_time"
    )


    end_time = request.GET.get(
        "end_time"
    )



    if not date or not start_time or not end_time:

        return Response({

            "error":
            "Please provide date, start_time and end_time"

        }, status=400)



    total_slots = ParkingSlot.objects.count()



    booked_slots = Booking.objects.filter(

        booking_date=date,

        start_time__lt=end_time,

        end_time__gt=start_time,

        status__in=[

            "confirmed",

            "parked"

        ]

    ).count()



    available = total_slots - booked_slots



    return Response({

        "date":
        date,


        "time":
        f"{start_time} - {end_time}",


        "total_slots":
        total_slots,


        "booked_slots":
        booked_slots,


        "available_slots":
        available,


        "status":

        "Available"
        if available > 0
        else "Full"

    })





# ==========================
# BOOKING API
# ==========================


@api_view(["GET"])
def bookings_api(request):


    bookings = Booking.objects.all().order_by(
        "-created_at"
    )


    serializer = BookingSerializer(

        bookings,

        many=True

    )


    return Response(
        serializer.data
    )





@api_view(["POST"])
def create_booking(request):


    user_id = request.data.get(
        "user"
    )


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



    try:


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
                "This slot is already booked"

            }, status=400)





        booking = Booking.objects.create(

            user_id=user_id,

            parking_slot=slot,

            booking_date=booking_date,

            start_time=start_time,

            end_time=end_time,

            status="confirmed"

        )



        return Response({

            "message":
            "Booking created successfully",


            "booking_id":
            booking.id,


            "status":
            booking.status

        })



    except ParkingSlot.DoesNotExist:


        return Response({

            "error":
            "Parking slot not found"

        }, status=404)





# ==========================
# CANCEL BOOKING
# ==========================


@api_view(["POST"])
def cancel_booking(request, booking_id):


    try:


        booking = Booking.objects.get(

            id=booking_id

        )



        booking.status = "cancelled"

        booking.save()



        return Response({

            "message":
            "Booking cancelled"

        })



    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        }, status=404)





# ==========================
# CAR EXIT + PAYMENT + OVERTIME
# ==========================


@api_view(["POST"])
def car_exit(request, booking_id):


    try:


        booking = Booking.objects.get(

            id=booking_id

        )



        exit_time = timezone.now()



        end_datetime = timezone.make_aware(

            timezone.datetime.combine(

                booking.booking_date,

                booking.end_time

            )

        )



        overtime_minutes = 0

        penalty = Decimal("0")



        # ----------------------
        # Check overtime
        # ----------------------


        if exit_time > end_datetime:


            overtime_minutes = int(

                (

                    exit_time - end_datetime

                ).total_seconds() / 60

            )


            penalty = Decimal("20")



            booking.status = "overtime"



        else:


            booking.status = "completed"





        # ----------------------
        # Normal parking fee
        # ----------------------


        duration = (

            exit_time -

            booking.actual_arrival_time

        )



        hours = max(

            1,

            int(

                duration.total_seconds() / 3600

            )

        )



        parking_fee = Decimal(

            hours * 2

        )



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
                "Insufficient wallet balance",

                "amount_required":
                total_payment

            }, status=400)





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





        return Response({

            "message":
            "Car exit completed",


            "parking_fee":
            parking_fee,


            "penalty":
            penalty,


            "overtime_minutes":
            overtime_minutes,


            "status":
            booking.status

        })





    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        }, status=404)
# ==========================
# GATE API
# ==========================


@api_view(["GET"])
def gates_api(request):

    gates = Gate.objects.all()


    serializer = GateSerializer(
        gates,
        many=True
    )


    return Response(
        serializer.data
    )





# ==========================
# OPEN GATE
# Admin = Open anytime
# Customer = Check booking time
# ==========================


@api_view(["POST"])
def open_gate(request, gate_id):


    try:


        gate = Gate.objects.get(
            id=gate_id
        )



        # ======================
        # ADMIN OVERRIDE
        # ======================

        if request.user.is_authenticated and (

            request.user.is_staff or

            request.user.is_superuser

        ):


            gate.is_open = True

            gate.save()



            return Response({

                "message":
                "Gate opened by admin",


                "gate":
                gate.gate_name,


                "status":
                gate.is_open

            })





        # ======================
        # CUSTOMER ACCESS
        # ======================


        booking = Booking.objects.filter(

            user=request.user,


            status="confirmed"

        ).order_by(

            "-created_at"

        ).first()



        if not booking:


            return Response({

                "error":
                "No active booking found"

            }, status=400)





        booking_start = timezone.make_aware(

            timezone.datetime.combine(

                booking.booking_date,

                booking.start_time

            )

        )



        booking_end = timezone.make_aware(

            timezone.datetime.combine(

                booking.booking_date,

                booking.end_time

            )

        )



        now = timezone.now()



        allowed_time = (

            booking_start -

            timezone.timedelta(minutes=5)

        )



        if now < allowed_time:


            return Response({

                "error":
                "Gate can open 5 minutes before booking time"

            }, status=400)





        if now > booking_end:


            return Response({

                "error":
                "Booking expired"

            }, status=400)





        gate.is_open = True

        gate.save()



        return Response({

            "message":
            "Gate opened successfully",


            "gate":
            gate.gate_name,


            "status":
            gate.is_open

        })





    except Gate.DoesNotExist:


        return Response({

            "error":
            "Gate not found"

        }, status=404)







# ==========================
# OPEN EXIT GATE
# ==========================


@api_view(["POST"])
def open_exit_gate(request, gate_id):


    try:


        gate = Gate.objects.get(

            id=gate_id

        )


        gate.is_open = True

        gate.save()



        return Response({

            "message":
            "Exit gate opened",


            "gate":
            gate.gate_name,


            "status":
            gate.is_open

        })



    except Gate.DoesNotExist:


        return Response({

            "error":
            "Gate not found"

        }, status=404)







# ==========================
# CLOSE GATE
# ==========================


@api_view(["POST"])
def close_gate(request, gate_id):


    try:


        gate = Gate.objects.get(

            id=gate_id

        )


        gate.is_open = False

        gate.save()



        return Response({

            "message":
            "Gate closed successfully",


            "gate":
            gate.gate_name,


            "status":
            gate.is_open

        })



    except Gate.DoesNotExist:


        return Response({

            "error":
            "Gate not found"

        }, status=404)







# ==========================
# CAR ENTRY
# ==========================


@api_view(["POST"])
def car_entry(request, booking_id):


    try:


        booking = Booking.objects.get(

            id=booking_id

        )



        booking.actual_arrival_time = (

            timezone.now()

        )


        booking.status = "parked"


        booking.save()



        slot = booking.parking_slot


        if slot:


            slot.status = "occupied"

            slot.save()





        return Response({

            "message":
            "Car entry recorded",


            "arrival_time":
            booking.actual_arrival_time,


            "status":
            booking.status

        })





    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        }, status=404)
# ==========================
# WALLET API
# ==========================


@api_view(["GET"])
def wallet_detail(request, user_id):

    try:

        wallet = Wallet.objects.get(
            user_id=user_id
        )


        serializer = WalletSerializer(
            wallet
        )


        return Response(
            serializer.data
        )


    except Wallet.DoesNotExist:


        return Response({

            "error":
            "Wallet not found"

        }, status=404)





@api_view(["POST"])
def add_wallet_balance(request, user_id):


    amount = request.data.get(
        "amount"
    )


    try:


        wallet, created = Wallet.objects.get_or_create(

            user_id=user_id

        )


        wallet.balance += Decimal(
            amount
        )


        wallet.save()



        return Response({

            "message":
            "Wallet updated",


            "balance":
            wallet.balance

        })



    except Exception:


        return Response({

            "error":
            "Invalid amount"

        }, status=400)






# ==========================
# TRANSACTION API
# ==========================


@api_view(["GET"])
def transaction_history(request, user_id):


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







@api_view(["POST"])
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

        "Emergency created",


        "data":

        EmergencySerializer(
            emergency
        ).data

    })







@api_view(["POST"])
def resolve_emergency(request, emergency_id):


    try:


        emergency = Emergency.objects.get(

            id=emergency_id

        )


        emergency.status = "resolved"

        emergency.save()



        return Response({

            "message":
            "Emergency resolved",


            "status":
            emergency.status

        })



    except Emergency.DoesNotExist:


        return Response({

            "error":
            "Emergency not found"

        }, status=404)







# ==========================
# FIRE SENSOR CHECK
# ==========================


@api_view(["POST"])
def fire_sensor_check(request):


    value = request.data.get(
        "value"
    )


    sensor_id = request.data.get(
        "sensor_id",
        "Unknown"
    )


    location = request.data.get(
        "location",
        "Unknown"
    )



    if str(value).lower() in [

        "fire",

        "detected",

        "danger"

    ]:


        emergency = Emergency.objects.create(

            emergency_type="fire",


            description=(

                f"Fire detected by "

                f"sensor {sensor_id} "

                f"at {location}"

            ),


            status="active"

        )



        return Response({

            "message":
            "Fire emergency activated",


            "emergency_id":
            emergency.id

        })




    return Response({

        "message":
        "No emergency detected"

    })







# ==========================
# PARKING SLOT API
# ==========================


@api_view(["GET"])
def parking_slots_api(request):


    slots = ParkingSlot.objects.all()



    serializer = ParkingSlotSerializer(

        slots,

        many=True

    )


    return Response(

        serializer.data

    )







# ==========================
# SENSOR WEB VIEW
# ==========================


class SensorReadingListView(ListView):


    model = SensorData


    template_name = (

        "back1/sensor_readings.html"

    )


    context_object_name = (

        "sensors"

    )







class SensorReadingDetailView(ListView):


    model = SensorData


    template_name = (

        "back1/sensor_detail.html"

    )







# ==========================
# PARKING SLOT WEB VIEW
# ==========================


class ParkingSlotListView(ListView):


    model = ParkingSlot


    template_name = (

        "back1/parking_slots.html"

    )


    context_object_name = (

        "slots"

    )







# ==========================
# BOOKING WEB VIEW
# ==========================


class BookingListView(ListView):


    model = Booking


    template_name = (

        "back1/bookings.html"

    )


    context_object_name = (

        "bookings"

    )







class BookingCreateView(
    LoginRequiredMixin,
    CreateView
):


    model = Booking



    fields = [

        "parking_slot",

        "booking_date",

        "start_time",

        "end_time"

    ]



    template_name = (

        "back1/booking_form.html"

    )



    success_url = reverse_lazy(
        "back1:dashboard"
    )




    def form_valid(self, form):


        form.instance.user = (

            self.request.user

        )



        messages.success(

            self.request,

            "Booking created successfully"

        )


        return super().form_valid(
            form
        )