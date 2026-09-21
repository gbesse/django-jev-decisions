"""Purpose: Demonstrate a real SQLite-backed Django decision with synthetic provider judgments."""
import json
from pathlib import Path
import django
django.setup()
from django.core.management import call_command
from jev_decisions.contracts import decide, fingerprint
from jev_decisions.services import enqueue, process_job
from tests.demoapp.models import Ticket
call_command('migrate',run_syncdb=True,verbosity=0)
fixture=json.loads((Path(__file__).parent/'synthetic-billing-response.json').read_text())
def synthetic(pack,state):
    return {'model':pack['model'],'inputFingerprint':fingerprint(state),'answers':fixture['answers'],**decide(pack,state,fixture['answers'])}
ticket=Ticket.objects.create(text='I was charged twice')
result=process_job(enqueue(ticket,'support').pk,evaluator=synthetic)
print(json.dumps({'synthetic':True,'status':result.status,'outcome':result.outcome,'sourceUnchanged':Ticket.objects.get(pk=ticket.pk).text==ticket.text}))
