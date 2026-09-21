"""Purpose: Call the pinned Jev contract with explicit network timeouts and no implicit retries."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4
import httpx
from .contracts import decide, fingerprint, require, validate_pack, validate_state

async def evaluate_async(pack, state, *, api_key, timeout=30, transport=None):
    pack, state = deepcopy(pack), deepcopy(state)
    validate_pack(pack); validate_state(pack, state)
    require(isinstance(api_key, str) and api_key, "Set JEV_API_KEY or TYPESAFE_API_KEY")
    require(type(timeout) in (int, float) and 0 < timeout <= 300, "Invalid timeout")
    started = monotonic()
    # asyncio supplies a total deadline in addition to httpx's per-network-operation timeouts.
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=False, transport=transport) as client:
            response = await client.post("https://api.typesafe.ai/v1/systemone", headers={"Authorization": "Bearer " + api_key}, json={"model": pack["model"], "questions": pack["questions"], "state": state})
            response.raise_for_status(); result = response.json()
    require(result.get("model") == pack["model"], "Provider model mismatch")
    gate = decide(pack, state, result.get("answers"))
    return {"schemaVersion": 1, "id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "model": pack["model"], "pack": {"name": pack["name"], "version": pack["version"], "fingerprint": fingerprint(pack)}, "questionFingerprint": fingerprint({"model": pack["model"], "questions": pack["questions"]}), "inputFingerprint": fingerprint(state), "answers": result["answers"], "latencyMs": round((monotonic()-started)*1000, 2), **gate}

def evaluate(pack, state, **options):
    return asyncio.run(evaluate_async(pack, state, **options))
