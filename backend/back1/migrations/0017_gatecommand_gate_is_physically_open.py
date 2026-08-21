import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("back1", "0016_sensorreadinghistory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gate",
            name="is_physically_open",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.CreateModel(
            name="GateCommand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("open", "Open"), ("close", "Close")], max_length=10)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("executing", "Executing"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("expired", "Expired")], db_index=True, default="pending", max_length=12)),
                ("requested_via", models.CharField(choices=[("admin", "Admin"), ("customer", "Customer"), ("lifecycle", "Lifecycle")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gate_commands", to="back1.booking")),
                ("gate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hardware_commands", to="back1.gate")),
                ("requested_by_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_gate_commands", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at", "id"],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status__in", ["pending", "executing"])), fields=("gate", "action"), name="one_unresolved_gate_action")],
            },
        ),
    ]
