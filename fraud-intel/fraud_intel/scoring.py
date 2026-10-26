from concurrent.futures import ThreadPoolExecutor, as_completed
from fraud_intel.checks import CHECKS
from ml.model import ml_probability

WEIGHTS = {"amount": 0.25, "location": 0.20, "velocity": 0.20,
           "behavior": 0.15, "merchant": 0.10, "device": 0.10}
APPROVE_MAX, REVIEW_MAX = 30, 70          # 0-30 approve, 31-70 review, 71-100 block

EXECUTOR = ThreadPoolExecutor(max_workers=10, thread_name_prefix="fraud")


def load_context(txn):
    """Phase 1 stub. Later: read the customer profile from the database."""
    return {"usual_amount": 2000, "home_location": "Hubballi",
            "known_devices": {"dev-1"}, "recent_count": 0,
            "typical_hours": (8, 22), "merchant_risk": 10}


def run_sequential(txn, ctx):
    return [fn(txn, ctx) for fn in CHECKS.values()]


def run_concurrent(txn, ctx):
    futures = [EXECUTOR.submit(fn, txn, ctx) for fn in CHECKS.values()]
    return [f.result() for f in as_completed(futures)]


def aggregate(results):
    total = sum(r["score"] * WEIGHTS[r["check"]] for r in results)
    if total <= APPROVE_MAX:
        decision = "APPROVE"
    elif total <= REVIEW_MAX:
        decision = "REVIEW"
    else:
        decision = "BLOCK"
    return round(total, 1), decision


RULE_SHARE = 0.6        # final = 0.6 x rule score + 0.4 x model score (team decision)


def decide(score):
    if score <= APPROVE_MAX:
        return "APPROVE"
    return "REVIEW" if score <= REVIEW_MAX else "BLOCK"


def score_transaction(txn, ctx=None, concurrent=True):
    ctx = ctx or load_context(txn)
    results = run_concurrent(txn, ctx) if concurrent else run_sequential(txn, ctx)
    results.sort(key=lambda r: list(CHECKS).index(r["check"]))
    rule_total, rule_decision = aggregate(results)
    prob = ml_probability(txn, ctx)
    if prob is None:                                  # no model file: rules only
        return {"decision": rule_decision, "score": rule_total, "ml_score": None, "checks": results}
    final = round(RULE_SHARE * rule_total + (1 - RULE_SHARE) * prob * 100, 1)
    return {"decision": decide(final), "score": final, "rule_score": rule_total,
            "ml_score": round(prob * 100, 1), "checks": results}
