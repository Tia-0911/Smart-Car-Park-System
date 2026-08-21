from django.core.management.base import BaseCommand
from back1.models import ParkingSlot, ParkingLED


class Command(BaseCommand):
    help = "Create the default 4 parking slots and their LEDs"

    def handle(self, *args, **kwargs):

        for i in range(1, 5):
            slot_number = f"A{i:02d}"
            led_name = f"{slot_number}_LED"

            slot, created = ParkingSlot.objects.get_or_create(
                slot_number=slot_number
            )

            led, led_created = ParkingLED.objects.get_or_create(
                parking_slot=slot,
                led_name=led_name
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created parking slot: {slot_number}"
                    )
                )

            if led_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created LED: {led_name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Parking setup completed."
            )
        )