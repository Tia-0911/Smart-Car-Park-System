from django.db import migrations


def create_default_gates(apps, schema_editor):
    Gate = apps.get_model("back1", "Gate")

    Gate.objects.get_or_create(
        gate_type="entrance",
        defaults={
            "gate_name": "Entrance Gate",
            "is_open": False,
        },
    )

    Gate.objects.get_or_create(
        gate_type="exit",
        defaults={
            "gate_name": "Exit Gate",
            "is_open": False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("back1", "0009_parkingrate"),
    ]

    operations = [
        migrations.RunPython(
            create_default_gates,
            migrations.RunPython.noop,
        ),
    ]
