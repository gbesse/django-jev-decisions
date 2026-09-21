"""Purpose: Implement the DecisionPacks v1 gate semantics in Python, with golden interoperability fixtures.
Derived from gbesse/decisionpacks, MIT, commit 3c90b6e667c16653b9a6ae00b376df9bddbd8461.
"""
import hashlib
import json
import math
import re
from copy import deepcopy

def require(value, message):
    if not value:
        raise ValueError(message)

def number(value):
    return type(value) in (int, float) and math.isfinite(value)

def portable(value):
    if value is None or type(value) in (str, bool): return value
    if number(value):
        require(abs(value) <= 9007199254740991, "Numbers must fit the interoperable safe range")
        return int(value) if float(value).is_integer() else value
    if isinstance(value, list): return [portable(x) for x in value]
    if isinstance(value, dict):
        require(all(isinstance(k, str) for k in value), "JSON keys must be strings")
        return {k: portable(v) for k, v in value.items()}
    raise ValueError("Expected finite JSON")

def fingerprint(value):
    return hashlib.sha256(json.dumps(portable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def path(value):
    require(isinstance(value, str) and value, "Invalid field path")
    parts = value.split(".")
    require(all(re.fullmatch(r"[a-zA-Z0-9_-]+", p) and p not in ("__proto__", "prototype", "constructor") for p in parts), "Unsafe field path")
    return parts

def get(value, field):
    for part in path(field):
        if not isinstance(value, dict) or part not in value: return None
        value = value[part]
    return value

def probability(value):
    require(number(value) and 0 <= value <= 1, "Invalid probability")

def validate_pack(pack):
    portable(pack)
    require(isinstance(pack, dict) and pack.get("schemaVersion") == 1, "Invalid pack schema")
    require(isinstance(pack.get("name"), str) and re.fullmatch(r"[a-z0-9][a-z0-9/-]*", pack["name"]), "Invalid pack name")
    require(isinstance(pack.get("version"), str) and re.fullmatch(r"\d+\.\d+\.\d+", pack["version"]), "Invalid pack version")
    require(isinstance(pack.get("model"), str) and pack["model"] and not re.search(r"latest|preview", pack["model"]), "Pin a model version")
    require(isinstance(pack.get("description"), str) and pack["description"], "Description required")
    inputs, questions = pack.get("inputs"), pack.get("questions")
    require(isinstance(inputs, dict) and inputs and isinstance(questions, dict) and questions and len(questions) <= 128, "Inputs and questions required")
    for field, kind in inputs.items(): path(field); require(kind in ("string", "number", "boolean"), "Invalid input type")
    for key, q in questions.items():
        require(len(path(key)) == 1 and isinstance(q, dict), "Invalid question id")
        require(q.get("type") in ("choice", "noul", "score") and isinstance(q.get("instructions"), str) and q["instructions"].strip(), "Invalid question")
        criteria = q.get("criteria")
        if q["type"] == "choice":
            require(isinstance(criteria, dict) and 2 <= len(criteria) <= 255, "Invalid choices")
            for option, description in criteria.items(): require(len(path(option)) == 1 and (description is None or isinstance(description, str)), "Invalid choice")
        elif q["type"] == "score": require(isinstance(criteria, list) and 2 <= len(criteria) <= 10 and all(isinstance(v, str) for v in criteria), "Invalid score rubric")
        elif criteria is not None: require(isinstance(criteria, dict) and all(k in ("true", "false") and isinstance(v, str) for k, v in criteria.items()), "Invalid noul criteria")
    require(isinstance(pack.get("fallback"), str) and pack["fallback"] and isinstance(pack.get("rules"), list), "Rules and fallback required")
    ids = set()
    for rule in pack["rules"]:
        require(isinstance(rule.get("id"), str) and rule["id"] and rule["id"] not in ids, "Invalid rule id"); ids.add(rule["id"])
        require(isinstance(rule.get("outcome"), str) and rule["outcome"] and isinstance(rule.get("all"), list) and rule["all"], "Invalid rule")
        for pred in rule["all"]:
            parts = path(pred.get("field")); value = pred.get("value")
            require(len(parts) > 1 and pred.get("op") in ("eq", "neq", "gt", "gte", "lt", "lte"), "Invalid predicate")
            require(type(value) in (str, bool) or number(value), "Predicate requires scalar")
            require(pred["op"] in ("eq", "neq") or number(value), "Ordered predicate requires number")
            if parts[0] == "state":
                field = ".".join(parts[1:]); require(field in inputs and matches_type(value, inputs[field]), "Undeclared or mistyped state predicate")
            else:
                require(parts[0] == "answers" and len(parts) >= 3 and parts[1] in questions, "Unknown answer predicate")
                q = questions[parts[1]]; field = ".".join(parts[2:])
                allowed = ["noul"] if q["type"] == "noul" else ["confidence", "choice" if q["type"] == "choice" else "score"] + ["probabilities." + str(k) for k in (q["criteria"] if q["type"] == "choice" else range(len(q["criteria"])))]
                require(field in allowed, "Invalid answer field")
                if field == "choice": require(isinstance(value, str) and value in q["criteria"], "Unknown predicate choice")
                elif field == "score": require(number(value), "Expected score number")
                else: probability(value)
    return pack

def matches_type(value, kind):
    return type(value) is str if kind == "string" else type(value) is bool if kind == "boolean" else number(value)

def validate_state(pack, state):
    portable(state); require(isinstance(state, dict), "State must be an object")
    for field, kind in pack["inputs"].items(): require(matches_type(get(state, field), kind), "Missing or mistyped input: " + field)

def validate_answers(questions, answers):
    portable(answers); require(isinstance(answers, dict) and answers.keys() == questions.keys(), "Answer set mismatch")
    for key, q in questions.items():
        a = answers[key]; require(isinstance(a, dict) and a.get("type") == q["type"], "Answer type mismatch")
        if q["type"] == "noul": probability(a.get("noul")); continue
        probability(a.get("confidence")); probs = a.get("probabilities")
        keys = set(q["criteria"]) if q["type"] == "choice" else {str(i) for i in range(len(q["criteria"]))}
        require(isinstance(probs, dict) and probs.keys() == keys, "Probability set mismatch")
        for value in probs.values(): probability(value)
        require(abs(sum(probs.values()) - 1) <= .001, "Probabilities must sum to one")
        if q["type"] == "choice": require(a.get("choice") in keys and probs[a["choice"]] >= max(probs.values()) - .001, "Invalid selected choice")
        else:
            expected = sum(int(k) * p for k, p in probs.items())
            require(number(a.get("score")) and 0 <= a["score"] <= len(keys)-1 and abs(a["score"]-expected) <= .01, "Invalid expected score")

def decide(pack, state, answers):
    validate_pack(pack); validate_state(pack, state); validate_answers(pack["questions"], answers)
    context = {"state": state, "answers": answers}
    def matches(pred):
        a, b = get(context, pred["field"]), pred["value"]
        if type(a) is not type(b) and not (number(a) and number(b)): return False
        if a is None: return False
        return {"eq": lambda: a == b, "neq": lambda: a != b, "gt": lambda: a > b, "gte": lambda: a >= b, "lt": lambda: a < b, "lte": lambda: a <= b}[pred["op"]]()
    for rule in pack["rules"]:
        if all(matches(p) for p in rule["all"]): return {"outcome": rule["outcome"], "ruleId": rule["id"]}
    return {"outcome": pack["fallback"], "ruleId": None}
