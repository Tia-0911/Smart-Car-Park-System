from rest_framework import serializers
from .models import ParkingSlot, Booking, Gate


class ParkingSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParkingSlot
        fields = '__all__'


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'


class GateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gate
        fields = '__all__'