from rest_framework import serializers

from .models import (
    ParkingSlot,
    Booking,
    Gate,
    SensorData,
    Wallet,
    Transaction,
    Emergency
)



# ==========================
# Parking Slot Serializer
# ==========================

class ParkingSlotSerializer(serializers.ModelSerializer):

    class Meta:
        model = ParkingSlot
        fields = '__all__'





# ==========================
# Booking Serializer
# ==========================

class BookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Booking
        fields = '__all__'





# ==========================
# Gate Serializer
# ==========================

class GateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Gate
        fields = '__all__'





# ==========================
# Sensor Serializer
# ==========================

class SensorDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = SensorData
        fields = '__all__'





# ==========================
# Wallet Serializer
# ==========================

class WalletSerializer(serializers.ModelSerializer):

    class Meta:
        model = Wallet
        fields = '__all__'





# ==========================
# Transaction Serializer
# ==========================

class TransactionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Transaction
        fields = '__all__'





# ==========================
# Emergency Serializer
# ==========================

class EmergencySerializer(serializers.ModelSerializer):

    class Meta:
        model = Emergency
        fields = '__all__'