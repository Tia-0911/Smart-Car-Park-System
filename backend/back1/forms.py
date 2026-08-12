from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Booking, ParkingSlot
from .services import booking_range_has_ended


class CustomerRegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class CustomerProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicate = User.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )
        return email



# ==========================
# Time Dropdown 24 Hours
# ==========================

TIME_CHOICES = []


for hour in range(24):

    time = f"{hour:02d}:00"

    TIME_CHOICES.append(
        (time, time)
    )



# ==========================
# Booking Form
# ==========================

class BookingForm(forms.Form):


    booking_date = forms.DateField(

        widget=forms.DateInput(

            attrs={
                "type": "date",
                "class": "form-control"
            }

        )

    )



    start_time = forms.TimeField(

        widget=forms.Select(

            attrs={
                "class": "form-control"
            }, choices=TIME_CHOICES

        )

    )



    end_time = forms.TimeField(

        widget=forms.Select(

            attrs={
                "class": "form-control"
            }, choices=TIME_CHOICES

        )

    )



    def clean_booking_date(self):
        booking_date = self.cleaned_data["booking_date"]
        if booking_date < timezone.localdate():
            raise forms.ValidationError("Booking date cannot be in the past.")
        return booking_date

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        booking_date = cleaned.get("booking_date")
        if booking_date and end and booking_range_has_ended(booking_date, end):
            raise forms.ValidationError("This booking time has already ended.")
        return cleaned


class AdminBookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("booking_date", "start_time", "end_time", "parking_slot", "status")
        widgets = {"booking_date": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_time"), cleaned.get("end_time")
        slot, day = cleaned.get("parking_slot"), cleaned.get("booking_date")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        if self.instance.pk and self.instance.status in ["active", "parked", "completed", "overtime"]:
            for field in ("booking_date", "start_time", "end_time", "parking_slot"):
                if field in self.changed_data:
                    raise forms.ValidationError("Lifecycle time and space cannot be changed for active or completed bookings.")
        if slot and day and start and end:
            if not slot.is_enabled or slot.is_under_maintenance or slot.is_backup:
                raise forms.ValidationError("Selected parking space is not usable.")
            conflicts = Booking.objects.filter(
                parking_slot=slot, booking_date=day,
                start_time__lt=end, end_time__gt=start,
                status__in=["pending", "confirmed", "active", "parked"],
            ).exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise forms.ValidationError("This parking space conflicts with another booking.")
        return cleaned


class AdminCustomerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "is_active")
