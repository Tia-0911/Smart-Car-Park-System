from django.core.management.base import BaseCommand

from back1.services import process_booking_reminders, process_overstays, process_sensor_alerts


class Command(BaseCommand):
    help = "Process due booking reminders and update active parking overstays."

    def handle(self, *args, **options):
        process_sensor_alerts()
        reminders = process_booking_reminders()
        overstays = process_overstays()
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {reminders} reminder(s) and {overstays} overstay booking(s)."
            )
        )
