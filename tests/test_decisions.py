"""Purpose: Exercise database claims, stale checks, admin permissions and the actual bounded HTTP adapter."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.conf import settings
import httpx
from jev_decisions.contracts import decide, fingerprint
from jev_decisions.provider import evaluate, evaluate_async
from jev_decisions.services import enqueue, process_job
from .demoapp.models import Ticket
BASE = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((BASE / 'examples/synthetic-billing-response.json').read_text())

def synthetic(pack, state):
    return {'model': pack['model'], 'inputFingerprint': fingerprint(state), 'answers': deepcopy(FIXTURE['answers']), **decide(pack, state, FIXTURE['answers'])}

class DatabaseTests(TestCase):
    def setUp(self): self.ticket = Ticket.objects.create(text='Charged twice')
    def test_claim_and_history(self):
        job = enqueue(self.ticket, 'support')
        result = process_job(job.pk, evaluator=synthetic)
        self.assertEqual((result.status, result.outcome), ('succeeded', 'billing'))
        self.assertIsNone(process_job(job.pk, evaluator=lambda *_: self.fail('double inference')))
        self.ticket.refresh_from_db(); self.assertEqual(self.ticket.text, 'Charged twice')
    def test_changed_before_inference(self):
        job = enqueue(self.ticket, 'support'); self.ticket.text='Changed'; self.ticket.save()
        self.assertEqual(process_job(job.pk, evaluator=lambda *_: self.fail('stale input evaluated')).status, 'stale')
    def test_changed_during_inference(self):
        job = enqueue(self.ticket, 'support')
        def provider(pack, state):
            Ticket.objects.filter(pk=self.ticket.pk).update(text='Changed during inference')
            return synthetic(pack, state)
        result = process_job(job.pk, evaluator=provider)
        self.assertEqual(result.status, 'stale'); self.assertEqual(result.outcome, '')
        self.assertIsNotNone(result.result)
    def test_deleted_object_is_stale(self):
        job = enqueue(self.ticket, 'support'); self.ticket.delete()
        self.assertEqual(process_job(job.pk, evaluator=synthetic).status, 'stale')
    def test_provider_failure_is_persisted_reported_and_raised(self):
        job = enqueue(self.ticket, 'support')
        def fail(*_): raise RuntimeError('Provider unavailable')
        with self.assertLogs('jev_decisions', level='ERROR'), self.assertRaisesRegex(RuntimeError, 'unavailable'):
            process_job(job.pk, evaluator=fail)
        job.refresh_from_db(); self.assertEqual(job.status, 'failed')
        self.assertEqual(len(mail.outbox), 1); self.assertIn('[staging] DecisionError', mail.outbox[0].subject)
    def test_forged_provenance_is_rejected(self):
        job = enqueue(self.ticket, 'support')
        def forged(pack, state): return {**synthetic(pack, state), 'inputFingerprint':'wrong'}
        with self.assertLogs('jev_decisions', level='ERROR'), self.assertRaisesRegex(ValueError, 'provenance'):
            process_job(job.pk, evaluator=forged)
    def test_admin_history_requires_permission(self):
        job=enqueue(self.ticket, 'support')
        self.assertEqual(self.client.get('/admin/jev_decisions/decisionjob/').status_code, 302)
        user=get_user_model().objects.create_user('limited', password='fixture', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/jev_decisions/decisionjob/').status_code, 403)
        user.is_superuser=True; user.save()
        response=self.client.get('/admin/jev_decisions/decisionjob/')
        self.assertEqual(response.status_code, 200); self.assertContains(response, 'support')
    def test_admin_action_queues_selected_model(self):
        user=get_user_model().objects.create_superuser('admin', 'admin@example.invalid', 'fixture')
        self.client.force_login(user)
        response=self.client.post('/admin/demoapp/ticket/', {'action':'evaluate_with_jev', '_selected_action':[self.ticket.pk]})
        self.assertEqual(response.status_code, 302)
        from jev_decisions.models import DecisionJob
        self.assertEqual(DecisionJob.objects.count(), 1)

class ContractTests(SimpleTestCase):
    def test_http_contract_and_gate(self):
        def transport(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer fixture-key')
            self.assertEqual(json.loads(request.content)['model'], settings.JEV_RULES['support']['pack']['model'])
            self.assertEqual(request.extensions['timeout']['read'], 2)
            return httpx.Response(200, json=FIXTURE)
        result=evaluate(settings.JEV_RULES['support']['pack'], {'text':'Charged twice'}, api_key='fixture-key', timeout=2, transport=httpx.MockTransport(transport))
        self.assertEqual(result['outcome'], 'billing'); self.assertEqual(len(result['pack']['fingerprint']), 64)
    def test_model_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, 'model mismatch'):
            evaluate(settings.JEV_RULES['support']['pack'], {'text':'x'}, api_key='fixture', transport=httpx.MockTransport(lambda _:httpx.Response(200,json={**FIXTURE,'model':'unknown'})))
    def test_total_deadline_includes_slow_transport(self):
        async def slow(_): await asyncio.sleep(10); return httpx.Response(200,json=FIXTURE)
        with self.assertRaises(TimeoutError):
            asyncio.run(evaluate_async(settings.JEV_RULES['support']['pack'], {'text':'x'}, api_key='fixture', timeout=.01, transport=httpx.MockTransport(slow)))
    def test_reference_gate_cases(self):
        for case in json.loads((BASE/'tests/golden-decisions.json').read_text()):
            with self.subTest(case=case['name']): self.assertEqual(decide(case['pack'],case['state'],case['answers']),case['expected'])
