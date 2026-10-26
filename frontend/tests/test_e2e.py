"""End-to-end checks of the 10 payment scenarios through the HTTP API.
Run against the mock:   pytest tests/ -v
Run against the real backend:
    API_BASE=http://localhost:8000 SENDER=... RECEIVER=... pytest tests/ -v
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

API = os.environ.get("API_BASE", "http://localhost:8000")
SENDER = os.environ.get("SENDER", "acc-alice")
RECEIVER = os.environ.get("RECEIVER", "acc-bob")
POOR_SENDER = os.environ.get("POOR_SENDER", "acc-chai")      # an account with a small balance
# An amount that must trigger BLOCK. Agree the trigger with Members 1 and 2.
RISKY_AMOUNT = float(os.environ.get("RISKY_AMOUNT", "60000"))


def set_sim(sender="SUCCESS", receiver="SUCCESS"):
    body = {"sender": sender, "receiver": receiver}
    requests.post(f"{API}/sim/config", json=body).raise_for_status()


def pay(amount=1000, key=None, sender=SENDER, receiver=RECEIVER):
    body = {"idempotency_key": key or str(uuid.uuid4()), "sender_account_id": sender,
            "receiver_account_id": receiver, "amount": amount}
    return requests.post(f"{API}/transactions", json=body)


def timeline_states(tid):
    return [e["to"] for e in requests.get(f"{API}/payment-status/{tid}").json()["timeline"]]


@pytest.fixture(autouse=True)
def reset_sim():
    set_sim()
    yield
    set_sim()


def test_01_normal_payment():
    r = pay().json()
    assert r["state"] == "COMPLETED" and r["duplicate"] is False


def test_02_debit_ok_credit_fails():
    set_sim(receiver="ERROR")
    r = pay().json()
    assert r["state"] == "RECONCILIATION_REQUIRED"
    everything = requests.get(f"{API}/alerts").json()
    alerts = [a for a in everything if a["transaction_id"] == r["transaction_id"]]
    assert {a["recipient"] for a in alerts} >= {"SENDER", "OPS"}


def test_03_receiver_times_out():
    set_sim(receiver="TIMEOUT")
    r = pay().json()
    assert r["state"] == "RECONCILIATION_REQUIRED"
    status = requests.get(f"{API}/payment-status/{r['transaction_id']}").json()
    assert status.get("recovery"), "stuck payment should carry a recovery estimate"


def test_04_credit_applied_confirmation_lost():
    set_sim(receiver="LOST_ACK")
    assert pay().json()["state"] == "COMPLETED"


def test_05_debit_fails():
    set_sim(sender="ERROR")
    assert pay().json()["state"] == "FAILED"


def test_06_invalid_receiver():
    assert pay(receiver="no-such-account").status_code == 422


def test_07_insufficient_balance():
    r = pay(amount=9000, sender=POOR_SENDER).json()
    assert r["state"] == "FAILED"


def test_08_duplicate_request():
    key = str(uuid.uuid4())
    first, second = pay(key=key).json(), pay(key=key).json()
    assert second["duplicate"] is True
    assert first["transaction_id"] == second["transaction_id"]


def test_09_concurrent_duplicates():
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(20) as pool:
        results = [f.result().json() for f in [pool.submit(pay, 100, key) for _ in range(20)]]
    assert len({r["transaction_id"] for r in results}) == 1
    assert sum(1 for r in results if r["duplicate"] is False) == 1


def test_10_fraud_block():
    r = pay(amount=RISKY_AMOUNT).json()
    assert r["decision"] == "BLOCK" and r["state"] == "FAILED"
    states = timeline_states(r["transaction_id"])
    assert "PROCESSING" not in states, "a blocked payment must not be debited"
