from django.contrib import admin
from .models import ParkingSlot, Booking, Gate


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ("slot_number", "is_available")
    list_filter = ("is_available",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("user_name", "parking_slot", "start_time", "end_time", "qr_code")
    list_filter = ("start_time", "end_time")


@admin.register(Gate)
class GateAdmin(admin.ModelAdmin):
    list_display = ("gate_name",)