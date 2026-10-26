"""Run from fraud-intel/:   python -m pytest tests/ -v"""
import random

import pytest

from fraud_intel.diagnosis import diagnose
from fraud_intel.recovery import build_table, estimate
from fraud_intel.scoring import score_transaction, load_context

DIAGNOSIS_CASES = [
    ("normal success",      {"debit": "OK", "credit": "OK"}, "COMPLETED"),
    ("credit error",        {"debit": "OK", "credit": "ERROR"}, "RECONCILIATION_REQUIRED"),
    ("timeout, no check",   {"debit": "OK", "credit": "TIMEOUT"}, "TIMEOUT"),
    ("timeout, no credit",  {"debit": "OK", "credit": "TIMEOUT", "status_check": False}, "RECONCILIATION_REQUIRED"),
    ("ack lost",            {"debit": "OK", "credit": "TIMEOUT", "status_check": True}, "COMPLETED"),
    ("debit error",         {"debit": "ERROR"}, "FAILED"),
    ("debit timeout",       {"debit": "TIMEOUT"}, "TIMEOUT"),
    ("invalid receiver",    {"receiver_valid": False}, "FAILED"),
    ("low balance",         {"balance_ok": False}, "FAILED"),
    ("duplicate",           {"duplicate": True, "debit": "OK", "credit": "OK"}, "UNCHANGED"),
    ("network failure",     {"debit": "OK", "credit": "TIMEOUT", "network_ok": False}, "TIMEOUT"),
    ("bank down",           {"debit": "OK", "credit": "TIMEOUT", "bank_up": False}, "TIMEOUT"),
    ("unknown combination", {"debit": "OK", "credit": "WEIRD"}, "RECONCILIATION_REQUIRED"),
]


@pytest.mark.parametrize("name,signals,expected", DIAGNOSIS_CASES)
def test_diagnosis(name, signals, expected):
    assert diagnose(signals)["next_state"] == expected


def test_stuck_cases_tell_sender_not_to_retry():
    out = diagnose({"debit": "OK", "credit": "ERROR"})
    assert "do not retry" in out["user_message"].lower()
    assert set(out["alert_to"]) == {"SENDER", "RECEIVER", "OPS"}


NORMAL = {"id": "a", "amount": 1200, "location": "Hubballi", "hour": 14,
          "merchant_id": "m1", "device_id": "dev-1"}
RISKY = {"id": "b", "amount": 9500, "location": "Mumbai", "hour": 3,
         "merchant_id": "m9", "device_id": "dev-9"}


def test_normal_payment_is_approved():
    assert score_transaction(NORMAL)["decision"] == "APPROVE"


def test_risky_payment_is_not_approved_and_every_check_has_a_reason():
    r = score_transaction(RISKY)
    assert r["decision"] in ("REVIEW", "BLOCK")
    assert len(r["checks"]) == 6 and all(c["reason"] for c in r["checks"])


def test_six_checks_run_in_parallel_in_different_threads():
    r = score_transaction(NORMAL, load_context(None))
    starts = [c["start"] for c in r["checks"]]
    assert max(starts) - min(starts) < 0.05          # started together
    assert len({c["thread"] for c in r["checks"]}) == 6


def test_concurrent_is_faster_than_sequential():
    import time
    ctx = load_context(None)
    t0 = time.time(); score_transaction(NORMAL, ctx, concurrent=False); seq = time.time() - t0
    t0 = time.time(); score_transaction(NORMAL, ctx, concurrent=True); con = time.time() - t0
    assert con < seq / 2


def test_recovery_estimate_needs_enough_cases():
    random.seed(1)
    history = [{"reason": "Network failure", "minutes": random.uniform(2, 10)} for _ in range(25)]
    history += [{"reason": "Receiver bank unavailable", "minutes": 3.0} for _ in range(2)]
    table = build_table(history)
    assert estimate("Network failure", table)["minutes"] is not None
    assert "estimate" in estimate("Network failure", table)["message"].lower()
    assert estimate("Receiver bank unavailable", table)["minutes"] is None     # too few cases
    assert estimate("Never seen", table)["minutes"] is None
