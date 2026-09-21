"""Purpose: Create the durable Jev decision history table."""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DecisionJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("rule_name", models.CharField(max_length=200)),
                ("model_label", models.CharField(max_length=200)),
                ("object_pk", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("succeeded", "succeeded"),
                            ("failed", "failed"),
                            ("stale", "stale"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("pack", models.JSONField()),
                ("state", models.JSONField()),
                ("input_fingerprint", models.CharField(max_length=64)),
                ("result", models.JSONField(blank=True, null=True)),
                (
                    "outcome",
                    models.CharField(blank=True, db_index=True, max_length=200),
                ),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
