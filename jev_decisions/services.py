"""Purpose: Queue explicit model snapshots and reject stale results before committing a decision."""
import logging
import os
from copy import deepcopy
from django.apps import apps
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone
from django.utils.module_loading import import_string
from .contracts import fingerprint, require, validate_pack, validate_state, decide
from .models import DecisionJob
from .provider import evaluate
logger = logging.getLogger(__name__)

def rule_config(name):
    config = settings.JEV_RULES[name]
    validate_pack(config["pack"])
    builder = import_string(config["state"]) if isinstance(config["state"], str) else config["state"]
    return config, builder

def enqueue(instance, rule_name):
    config, builder = rule_config(rule_name)
    require(instance.pk is not None and instance._meta.label_lower == config["model"].lower(), "Rule does not belong to this saved model")
    pack, state = deepcopy(config["pack"]), deepcopy(builder(instance))
    validate_state(pack, state)
    require(len(str(state)) <= 100000, "Decision state exceeds size limit")
    return DecisionJob.objects.create(rule_name=rule_name, model_label=instance._meta.label_lower, object_pk=str(instance.pk), pack=pack, state=state, input_fingerprint=fingerprint(state))

def source_is_current(job):
    config, builder = rule_config(job.rule_name)
    if config["model"].lower() != job.model_label or fingerprint(config["pack"]) != fingerprint(job.pack): return False
    instance = apps.get_model(job.model_label).objects.filter(pk=job.object_pk).first()
    return instance is not None and fingerprint(builder(instance)) == job.input_fingerprint

def process_job(job_id, *, evaluator=None):
    # Compare-and-set prevents two consumers from claiming the same queued row, including on SQLite.
    if not DecisionJob.objects.filter(pk=job_id, status="queued").update(status="running"): return None
    job = DecisionJob.objects.get(pk=job_id)
    try:
        if not source_is_current(job):
            job.status = "stale"
        else:
            if evaluator is None:
                result = evaluate(job.pack, job.state, api_key=getattr(settings, "JEV_API_KEY", os.environ.get("TYPESAFE_API_KEY", "")), timeout=getattr(settings, "JEV_TIMEOUT_SECONDS", 30))
            else:
                result = evaluator(deepcopy(job.pack), deepcopy(job.state))
            require(result.get("model") == job.pack["model"] and result.get("inputFingerprint") == job.input_fingerprint, "Decision provenance mismatch")
            gate = decide(job.pack, job.state, result.get("answers"))
            require(result.get("outcome") == gate["outcome"] and result.get("ruleId") == gate["ruleId"], "Decision gate mismatch")
            job.result = result
            if source_is_current(job): job.status, job.outcome = "succeeded", result["outcome"]
            else: job.status = "stale"
        job.completed_at = timezone.now(); job.save()
        return job
    except Exception as error:
        job.status = "failed"; job.error = str(error); job.completed_at = timezone.now(); job.save()
        logger.exception("Jev decision job %s failed", job.pk)
        if settings.ADMINS:
            mail_admins(f"[django-jev-decisions][{getattr(settings, 'JEV_ENVIRONMENT', 'prod')}] DecisionError", f"Job {job.pk}: {type(error).__name__}: {error}", fail_silently=False)
        raise
