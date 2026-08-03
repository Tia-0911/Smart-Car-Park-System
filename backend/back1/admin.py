from django.contrib import admin
from django import forms

from .models import ParkingSlot, Booking, SensorData, Gate



# ==========================
# Parking Slot Admin
# ==========================

@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):

    list_display = (
        "slot_number",
        "status",
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

        "sensor_type",

        "value",

        "parking_slot",

        "created_at",

    )


    list_filter = (

        "sensor_type",

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

    )


    list_filter = (

        "is_open",

    )