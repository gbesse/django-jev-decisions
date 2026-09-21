"""Purpose: Process an explicitly bounded batch of queued jobs without requiring a task-queue service."""
from django.core.management.base import BaseCommand, CommandError
from jev_decisions.models import DecisionJob
from jev_decisions.services import process_job
class Command(BaseCommand):
    help = "Process queued Jev decisions; provider failures remain visible and stop the command."
    def add_arguments(self, parser): parser.add_argument("--limit", type=int, default=20)
    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000: raise CommandError("limit must be 1–1000")
        ids = list(DecisionJob.objects.filter(status="queued").order_by("created_at").values_list("pk", flat=True)[:limit])
        for job_id in ids:
            result = process_job(job_id)
            if result: self.stdout.write(f"{result.pk}: {result.status} {result.outcome}")
