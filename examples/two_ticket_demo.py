"""Compare a current and stale synthetic ticket in one offline Django run."""

import json
from pathlib import Path

import django

django.setup()
from django.core.management import call_command  # noqa: E402
from jev_decisions.contracts import decide, fingerprint  # noqa: E402
from jev_decisions.services import enqueue, process_job  # noqa: E402
from tests.demoapp.models import Ticket  # noqa: E402

call_command("migrate", run_syncdb=True, verbosity=0)
fixture = json.loads((Path(__file__).parent / "synthetic-billing-response.json").read_text())
calls = []


def synthetic(pack, state):
    calls.append(state)
    return {"model": pack["model"], "inputFingerprint": fingerprint(state), "answers": fixture["answers"], **decide(pack, state, fixture["answers"])}


current = Ticket.objects.create(text="I was charged twice")
changed = Ticket.objects.create(text="I was charged twice")
current_job = enqueue(current, "support")
stale_job = enqueue(changed, "support")
changed.text = "The source ticket changed"
changed.save(update_fields=["text"])
current_result = process_job(current_job.pk, evaluator=synthetic)
stale_result = process_job(stale_job.pk, evaluator=synthetic)
assert current_result.status == "succeeded" and stale_result.status == "stale" and len(calls) == 1
print(json.dumps({"source": "synthetic SQLite tickets; no API call", "current": current_result.status, "changed": stale_result.status, "provider_calls": len(calls)}))
