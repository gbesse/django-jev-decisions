"""Purpose: Persist queued decisions and their provenance independently of the application's source models."""
import uuid
from django.db import models
class DecisionJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_name = models.CharField(max_length=200)
    model_label = models.CharField(max_length=200)
    object_pk = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default="queued", choices=[(v, v) for v in ("queued", "running", "succeeded", "failed", "stale")], db_index=True)
    pack = models.JSONField()
    state = models.JSONField()
    input_fingerprint = models.CharField(max_length=64)
    result = models.JSONField(null=True, blank=True)
    outcome = models.CharField(max_length=200, blank=True, db_index=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.rule_name}: {self.model_label}/{self.object_pk} ({self.status})"
