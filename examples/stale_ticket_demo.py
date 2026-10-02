"""Demonstrate stale source rejection before synthetic inference starts."""
import json

import django

django.setup()
from django.core.management import call_command  # noqa: E402
from jev_decisions.services import enqueue, process_job  # noqa: E402
from tests.demoapp.models import Ticket  # noqa: E402

call_command("migrate", run_syncdb=True, verbosity=0)
ticket = Ticket.objects.create(text="Please review the duplicate charge")
job = enqueue(ticket, "support")
ticket.text = "The source ticket changed after queueing"
ticket.save(update_fields=["text"])
provider_called = False


def should_not_run(*_):
    global provider_called
    provider_called = True
    raise AssertionError("Stale input reached the provider")


result = process_job(job.pk, evaluator=should_not_run)
assert result.status == "stale" and not provider_called
print(json.dumps({"source": "synthetic in-memory ticket; no API call", "status": result.status, "provider_called": provider_called}))
