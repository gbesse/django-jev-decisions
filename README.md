# Jev decisions for Django

Queue versioned model snapshots, reject stale results and review decision history in Django admin. Adds an explicit admin action to your existing models without changing their business data.

**v0.1.1 experimental alpha · MIT · Python 3.11+**. Tested with Django 5.2.17 and SQLite. Independent community integration.

## Install and configure

```sh
pip install 'git+https://github.com/gbesse/django-jev-decisions.git@v0.1.1'
```

Add `jev_decisions` to `INSTALLED_APPS` and run `python manage.py migrate`. Configure a server-side key and registered policies:

```python
# settings.py; load the supplied pack JSON from your application's configuration.
JEV_API_KEY = os.environ['TYPESAFE_API_KEY']
JEV_TIMEOUT_SECONDS = 30
JEV_RULES = {
    'support': {
        'model': 'support.Ticket',
        'pack': SUPPORT_TRIAGE_PACK,
        'state': 'support.decisions.ticket_state',
    }
}
# support/decisions.py
def ticket_state(ticket):
    return {'text': ticket.text}
```

Use the mixin in the existing model admin:

```python
from jev_decisions.admin import JevDecisionAdminMixin
class TicketAdmin(JevDecisionAdminMixin, admin.ModelAdmin):
    jev_rule = 'support'
```

Select objects and choose **Queue Jev evaluation**. Staff need change permission for the source model and `jev_decisions.add_decisionjob`. Run the queue consumer from your existing scheduler:

```sh
python manage.py process_jev_decisions --limit 20
```

Programmatic callers may use `enqueue(instance, 'support')`, then `process_job(job_id)`. Enqueue after your transaction commits. These APIs are for trusted server code; enforce business authorization in the caller. No signal automatically evaluates every model save.

Jobs move from queued to running, then succeeded, stale or failed. Source state and pack are checked before and after inference. The admin shows the read-only history. A database claim prevents simultaneous consumers processing one queued row. A worker crash can leave a running job; this alpha intentionally does not blindly retry it. Inspect the job and provider state before queueing a new snapshot. This is not a transactional guard for later business writes: revalidate inside your own write transaction.

Unexpected failures persist, log, email configured Django `ADMINS` and propagate. Configure your normal Django email backend. Full snapshots and answers are stored; apply host permissions and retention. No source object is published or modified automatically.

## Try the stale-snapshot guard offline

`DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m examples.stale_ticket_demo` queues a synthetic ticket, changes its source text, and shows that the old job becomes `stale` without invoking a provider. This uses in-memory SQLite and no API key. A production worker must still handle interrupted jobs and validate writes inside its own transaction.

## Verify from a clone, without packaging

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m django check
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m django test tests
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m django makemigrations jev_decisions --check --dry-run
DJANGO_SETTINGS_MODULE=tests.settings .venv/bin/python -m examples.offline_demo
```

Twelve tests exercise the real ORM/admin, permissions, claims, deleted/changed objects, a change during inference, error email capture, HTTP request shape, total timeout, model pinning and 38 DecisionPacks reference cases. HTTP judgments are synthetic; no live Jev call or PostgreSQL concurrency stress test was run. Native Python gate semantics derive from DecisionPacks; cross-language fingerprint identity is not promised for every numeric/Unicode edge case.

See [reuse and provenance](docs/reuse.md), [contributing](CONTRIBUTING.md) and [security](SECURITY.md).

[Recorded verification scope](docs/verification.md).
