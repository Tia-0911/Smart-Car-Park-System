# ==========================
# IMPORTS
# ==========================

from decimal import Decimal
from django.db.models import Sum

from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
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
    Emergency
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
# DASHBOARD VIEW
# ==========================


def dashboard(request):


    # ----------------------
    # Parking Summary
    # ----------------------

    total_slots = ParkingSlot.objects.count()


    occupied_slots = ParkingSlot.objects.filter(
        status="occupied"
    ).count()


    available_slots = (
        total_slots - occupied_slots
    )


    if total_slots > 0:

        occupancy_percentage = int(
            (occupied_slots / total_slots) * 100
        )

    else:

        occupancy_percentage = 0





    # ----------------------
    # Latest Sensor
    # ----------------------

    latest_sensor = SensorData.objects.order_by(
        "-created_at"
    ).first()



    sensor_history = SensorData.objects.order_by(
        "-created_at"
    )[:10]






    # ----------------------
    # Booking
    # ----------------------

    latest_bookings = Booking.objects.order_by(
        "-created_at"
    )[:5]
    
    
    booking_count = Booking.objects.filter(
    status__in=[
        "confirmed",
        "parked"
        ]
    ).count()



    # ----------------------
    # Gate
    # ----------------------

    entrance_gate = Gate.objects.filter(
        gate_type="entrance"
    ).first()



    exit_gate = Gate.objects.filter(
        gate_type="exit"
    ).first()





    # ----------------------
    # Emergency
    # ----------------------

    emergency_alerts = Emergency.objects.filter(
        status="active"
    ).order_by(
        "-created_at"
    )[:5]
    
    
    parking_slots = ParkingSlot.objects.all()


    total_revenue = Transaction.objects.filter(
        transaction_type__in=[
            "payment",
            "penalty"
        ]
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0



    parking_revenue = Transaction.objects.filter(
        transaction_type="payment"
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0



    penalty_revenue = Transaction.objects.filter(
        transaction_type="penalty"
    ).aggregate(
        total=Sum("amount")
    )["total"] or 0
    
    
    # ----------------------
    # Recently Activity
    # ----------------------

    recent_activities = Transaction.objects.order_by(
        "-created_at"
    )[:5]


    context = {


        "total_slots":
        total_slots,


        "occupied_slots":
        occupied_slots,


        "available_slots":
        available_slots,


        "occupancy_percentage":
        occupancy_percentage,


        "latest_sensor":
        latest_sensor,


        "sensor_history":
        sensor_history,


        "latest_bookings":
        latest_bookings,
        
        "booking_count":
        booking_count,


        "parking_slots":
        parking_slots,


        "total_revenue":
        total_revenue,


        "parking_revenue":
        parking_revenue,


        "penalty_revenue":
        penalty_revenue,


        "entrance_gate":
        entrance_gate,


        "exit_gate":
        exit_gate,


        "emergency_alerts":
        emergency_alerts,


        "recent_bookings":
        latest_bookings,


        "recent_activities":
        recent_activities

    }



    return render(

        request,

        "back1/dashboard.html",

        context

    )






# ==========================
# SENSOR STATUS API
# ==========================


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


            "updated_at":
            sensor.updated_at

        })




    return Response({

        "total":
        sensors.count(),


        "online":
        online,


        "error":
        error,


        "data":
        sensor_list

    })
# ==========================
# PARKING SLOT API
# ==========================


@api_view(["GET"])
def parking_slots(request):


    slots = ParkingSlot.objects.all().order_by(
        "slot_number"
    )


    data = []


    for slot in slots:


        data.append({

            "slot_number":
            slot.slot_number,


            "status":
            slot.status,


            "updated_at":
            slot.updated_at

        })



    return Response({

        "total":
        slots.count(),


        "slots":
        data

    })







# ==========================
# BOOKING API
# ==========================


@api_view(["GET"])
def booking_list(request):


    bookings = Booking.objects.all().order_by(
        "-created_at"
    )[:10]



    data = []



    for booking in bookings:


        data.append({

            "id":
            booking.id,


            "user":
            booking.user.username,


            "slot":
            booking.parking_slot.slot_number,


            "date":
            booking.booking_date,


            "start_time":
            booking.start_time,


            "end_time":
            booking.end_time,


            "status":
            booking.status

        })




    return Response({

        "total":
        bookings.count(),


        "bookings":
        data

    })







# ==========================
# GATE CONTROL API
# ==========================


@api_view(["GET"])
def gate_status(request):


    gates = Gate.objects.all()



    data = []



    for gate in gates:


        data.append({

            "id":
            gate.id,


            "name":
            gate.gate_name,


            "type":
            gate.gate_type,


            "is_open":
            gate.is_open,


            "status":
            "Open" if gate.is_open else "Closed"

        })




    return Response({

        "gates":
        data

    })







@api_view(["POST"])
def gate_control(request, gate_id):


    try:

        gate = Gate.objects.get(
            id=gate_id
        )


    except Gate.DoesNotExist:


        return Response(

            {
                "error":
                "Gate not found"
            },

            status=status.HTTP_404_NOT_FOUND

        )





    action = request.data.get(
        "action"
    )




    if action == "open":


        gate.is_open = True


    elif action == "close":


        gate.is_open = False


    else:


        return Response(

            {
                "error":
                "Invalid action"
            },

            status=status.HTTP_400_BAD_REQUEST

        )




    gate.save()



    return Response({

        "message":
        f"{gate.gate_name} {action}ed",


        "status":
        gate.is_open

    })






# ==========================
# EMERGENCY API
# ==========================


@api_view(["GET"])
def emergency_status(request):


    emergencies = Emergency.objects.filter(
        status="active"
    ).order_by(
        "-created_at"
    )



    data = []



    for emergency in emergencies:


        data.append({

            "type":
            emergency.emergency_type,


            "description":
            emergency.description,


            "status":
            emergency.status,


            "created_at":
            emergency.created_at

        })




    return Response({

        "active_alerts":
        emergencies.count(),


        "data":
        data

    })
# ==========================
# SENSOR DATA FROM RASPBERRY PI
# ==========================


@api_view(["GET"])
def latest_sensor(request):


    sensor = SensorData.objects.order_by(
        "-created_at"
    ).first()



    if not sensor:


        return Response({

            "message":
            "No sensor data available"

        })




    serializer = SensorDataSerializer(
        sensor
    )


    return Response(
        serializer.data
    )







@api_view(["GET"])
def sensor_history(request):


    sensors = SensorData.objects.order_by(
        "-created_at"
    )[:50]



    serializer = SensorDataSerializer(

        sensors,

        many=True

    )



    return Response(
        serializer.data
    )








# ==========================
# RASPBERRY PI UPDATE SENSOR
# ==========================


@api_view(["POST"])
def update_sensor(request):


    sensor_id = request.data.get(
        "sensor_id"
    )


    sensor_type = request.data.get(
        "sensor_type"
    )


    location = request.data.get(
        "location"
    )


    value = request.data.get(
        "value"
    )


    sensor_status = request.data.get(
        "status",
        "active"
    )



    sensor = SensorData.objects.create(

        sensor_id=sensor_id,

        sensor_type=sensor_type,

        location=location,

        value=value,

        status=sensor_status

    )



    return Response({

        "message":
        "Sensor data saved",


        "sensor_id":
        sensor.sensor_id

    },

    status=status.HTTP_201_CREATED

    )







# ==========================
# REVENUE DASHBOARD API
# ==========================


@api_view(["GET"])
def revenue_summary(request):


    transactions = Transaction.objects.all()



    total_revenue = Decimal("0")

    parking_revenue = Decimal("0")

    penalty_revenue = Decimal("0")




    for transaction in transactions:


        if transaction.transaction_type == "payment":

            total_revenue += transaction.amount

            parking_revenue += transaction.amount



        elif transaction.transaction_type == "penalty":

            total_revenue += transaction.amount

            penalty_revenue += transaction.amount






    return Response({

        "total_revenue":
        total_revenue,


        "parking_revenue":
        parking_revenue,


        "penalty_revenue":
        penalty_revenue

    })







# ==========================
# CREATE BOOKING
# ==========================


@api_view(["POST"])
def create_booking(request):


    try:


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
                "Parking slot already booked"

            },

            status=400

            )







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
            booking.id

        })





    except ParkingSlot.DoesNotExist:


        return Response({

            "error":
            "Parking slot not found"

        },

        status=404

        )
# ==========================
# CAR ENTRY
# ==========================


@api_view(["POST"])
def car_entry(request, booking_id):


    try:


        booking = Booking.objects.get(
            id=booking_id
        )


    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        },

        status=404

        )




    booking.actual_arrival_time = timezone.now()

    booking.status = "parked"

    booking.save()



    slot = booking.parking_slot


    if slot:

        slot.status = "occupied"

        slot.save()



    return Response({

        "message":
        "Car entered parking",


        "booking_status":
        booking.status,


        "slot":
        slot.slot_number

    })







# ==========================
# CAR EXIT + PAYMENT
# ==========================


@api_view(["POST"])
def car_exit(request, booking_id):


    try:


        booking = Booking.objects.get(

            id=booking_id

        )



    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        },

        status=404

        )





    exit_time = timezone.now()



    parking_fee = Decimal("2.00")

    penalty = Decimal("0")

    overtime_minutes = 0





    end_datetime = timezone.make_aware(

        timezone.datetime.combine(

            booking.booking_date,

            booking.end_time

        )

    )





    if exit_time > end_datetime:


        overtime_minutes = int(

            (

                exit_time - end_datetime

            ).total_seconds()

            / 60

        )


        penalty = Decimal("20.00")


        booking.status = "overtime"



    else:


        booking.status = "completed"






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
            "Insufficient balance"

        },

        status=400

        )







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





    slot = booking.parking_slot


    if slot:


        slot.status = "available"

        slot.save()





    return Response({

        "message":
        "Exit completed",


        "parking_fee":
        parking_fee,


        "penalty":
        penalty,


        "overtime_minutes":
        overtime_minutes

    })








# ==========================
# CANCEL BOOKING
# ==========================


@api_view(["POST"])
def cancel_booking(request, booking_id):


    try:


        booking = Booking.objects.get(

            id=booking_id

        )


    except Booking.DoesNotExist:


        return Response({

            "error":
            "Booking not found"

        },

        status=404

        )





    booking.status = "cancelled"

    booking.save()



    return Response({

        "message":
        "Booking cancelled"

    })








# ==========================
# WALLET API
# ==========================


@api_view(["GET"])
def wallet_detail(request, user_id):


    try:


        wallet = Wallet.objects.get(

            user_id=user_id

        )


    except Wallet.DoesNotExist:


        return Response({

            "error":
            "Wallet not found"

        },

        status=404

        )





    serializer = WalletSerializer(

        wallet

    )


    return Response(

        serializer.data

    )








# ==========================
# ADD WALLET BALANCE
# ==========================


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
            "Balance updated",


            "balance":
            wallet.balance

        })





    except Exception:


        return Response({

            "error":
            "Invalid amount"

        },

        status=400

        )







# ==========================
# TRANSACTION HISTORY
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







# ==========================
# CREATE EMERGENCY
# ==========================


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
        "Emergency created successfully",


        "data":
        EmergencySerializer(
            emergency
        ).data

    })







# ==========================
# RESOLVE EMERGENCY
# ==========================


@api_view(["POST"])
def resolve_emergency(request, emergency_id):


    try:


        emergency = Emergency.objects.get(

            id=emergency_id

        )


    except Emergency.DoesNotExist:


        return Response({

            "error":
            "Emergency not found"

        },

        status=404

        )





    emergency.status = "resolved"

    emergency.save()



    return Response({

        "message":
        "Emergency resolved",


        "status":
        emergency.status

    })








# ==========================
# FIRE SENSOR CHECK
# ==========================


@api_view(["GET"])
def fire_sensor_check(request):


    sensors = SensorData.objects.filter(

        sensor_type="fire"

    )



    alerts = []



    for sensor in sensors:


        try:


            value = float(
                sensor.value
            )


        except:


            value = 0




        if value > 50:


            alerts.append({

                "sensor_id":
                sensor.sensor_id,


                "location":
                sensor.location,


                "value":
                value,


                "status":
                "danger"

            })





    return Response({

        "fire_detected":
        len(alerts) > 0,


        "alerts":
        alerts

    })









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
# ==========================


@api_view(["POST"])
def open_gate(request, gate_id):


    try:


        gate = Gate.objects.get(

            id=gate_id

        )


    except Gate.DoesNotExist:


        return Response({

            "error":
            "Gate not found"

        },

        status=404

        )





    gate.is_open = True

    gate.save()



    return Response({

        "message":
        "Gate opened",


        "gate":
        gate.gate_name,


        "status":
        gate.is_open

    })








# ==========================
# CLOSE GATE
# ==========================


@api_view(["POST"])
def close_gate(request, gate_id):


    try:


        gate = Gate.objects.get(

            id=gate_id

        )


    except Gate.DoesNotExist:


        return Response({

            "error":
            "Gate not found"

        },

        status=404

        )





    gate.is_open = False

    gate.save()



    return Response({

        "message":
        "Gate closed",


        "gate":
        gate.gate_name,


        "status":
        gate.is_open

    })








# ==========================
# WEB VIEWS
# ==========================


class SensorReadingListView(ListView):


    model = SensorData


    template_name = (
        "back1/sensor_readings.html"
    )


    context_object_name = (
        "sensors"
    )








class ParkingSlotListView(ListView):


    model = ParkingSlot


    template_name = (
        "back1/parking_slots.html"
    )


    context_object_name = (
        "slots"
    )








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