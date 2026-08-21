from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("back1", "0018_alter_systemevent_event_type_parkingled_ledcommand_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS back1_parkingled (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    led_name VARCHAR(50) NOT NULL UNIQUE,
                    status VARCHAR(10) NOT NULL DEFAULT 'off',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    parking_slot_id BIGINT NOT NULL
                        REFERENCES back1_parkingslot(id)
                        ON DELETE CASCADE
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS back1_parkingled;
            """,
        ),
    ]