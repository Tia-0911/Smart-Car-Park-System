from django import forms

from .models import Booking, ParkingSlot



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

class BookingForm(forms.ModelForm):


    booking_date = forms.DateField(

        widget=forms.DateInput(

            attrs={
                "type": "date",
                "class": "form-control"
            }

        )

    )



    start_time = forms.ChoiceField(

        choices=TIME_CHOICES,

        widget=forms.Select(

            attrs={
                "class": "form-control"
            }

        )

    )



    end_time = forms.ChoiceField(

        choices=TIME_CHOICES,

        widget=forms.Select(

            attrs={
                "class": "form-control"
            }

        )

    )



    class Meta:


        model = Booking


        fields = [

            "parking_slot",
            "booking_date",
            "start_time",
            "end_time"

        ]



        widgets = {


            "parking_slot": forms.Select(

                attrs={
                    "class": "form-control"
                }

            )


        }



    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)



        # แสดง parking slot ทั้งหมด
        # ระบบจะตรวจว่าง/เต็มจากวันที่และเวลาใน views

        self.fields["parking_slot"].queryset = (
            ParkingSlot.objects.all()
        )