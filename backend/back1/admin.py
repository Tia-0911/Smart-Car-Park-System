from django.contrib import admin
from django import forms
from .models import ParkingRate

from .models import (
    ParkingSlot,
    Booking,
    SensorData,
    Gate,
    Wallet,
    Transaction,
    Emergency
)



# ==========================
# Parking Slot Admin
# ==========================

@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):

    list_display = (
        "slot_number",
        "status",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
    )



# ==========================
# Booking Admin
# ==========================


class BookingAdminForm(forms.ModelForm):

    TIME_CHOICES = [

        (f"{hour:02d}:00", f"{hour:02d}:00")

        for hour in range(24)

    ]


    start_time = forms.ChoiceField(
        choices=TIME_CHOICES
    )


    end_time = forms.ChoiceField(
        choices=TIME_CHOICES
    )


    class Meta:

        model = Booking

        fields = "__all__"



    def clean(self):

        cleaned_data = super().clean()

        start = cleaned_data.get(
            "start_time"
        )

        end = cleaned_data.get(
            "end_time"
        )


        if start and end:

            if start >= end:

                raise forms.ValidationError(
                    "End time must be after start time."
                )


        return cleaned_data





@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    form = BookingAdminForm


    list_display = (

        "user",
        "parking_slot",
        "booking_date",
        "start_time",
        "end_time",
        "status",
        "created_at",

    )


    list_filter = (

        "booking_date",
        "parking_slot",
        "status",

    )


    search_fields = (

        "user__username",

    )





# ==========================
# Sensor Data Admin
# ==========================

@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):

    list_display = (

        "sensor_id",
        "sensor_type",
        "value",
        "status",
        "parking_slot",
        "created_at",

    )


    list_filter = (

        "sensor_type",
        "status",

    )





# ==========================
# Gate Admin
# ==========================

@admin.register(Gate)
class GateAdmin(admin.ModelAdmin):

    list_display = (

        "gate_name",
        "is_open",
        "created_at",
        "updated_at",

    )


    list_filter = (

        "is_open",

    )





# ==========================
# Wallet Admin
# ==========================

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):

    list_display = (

        "user",
        "balance",
        "created_at",
        "updated_at",

    )



# ==========================
# Transaction Admin
# ==========================

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    list_display = (

        "user",
        "transaction_type",
        "amount",
        "created_at",

    )


    list_filter = (

        "transaction_type",

    )





# ==========================
# Emergency Admin
# ==========================

@admin.register(Emergency)
class EmergencyAdmin(admin.ModelAdmin):

    list_display = (

        "emergency_type",
        "status",
        "created_at",
        "updated_at",

    )


    list_filter = (

        "emergency_type",
        "status",

    )
    
admin.site.register(ParkingRate)