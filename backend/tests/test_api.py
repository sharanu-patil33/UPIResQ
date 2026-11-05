"""Tests the HTTP endpoints. Run from backend/:   python -m pytest tests/ -v"""
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import simulators
from app.db import SessionLocal
from app.main import app
from app.models import Account, Customer, Transaction

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_simulators():
    simulators.CONFIG["sender"] = simulators.CONFIG["receiver"] = "SUCCESS"
    yield
    simulators.CONFIG["sender"] = simulators.CONFIG["receiver"] = "SUCCESS"


@pytest.fixture
def ids():
    """A fresh sender (balance 5000), receiver (balance 0) and a poor sender (balance 100)."""
    db = SessionLocal()
    owner = Customer(name="API Test", email=f"{uuid.uuid4()}@example.com")
    db.add(owner)
    db.commit()
    made = {}
    for name, balance in (("sender", 5000), ("receiver", 0), ("poor", 100)):
        acc = Account(customer_id=owner.id, account_number=str(uuid.uuid4()), balance=balance)
        db.add(acc)
        db.commit()
        made[name] = acc.id
    db.close()
    return made


def pay(ids, amount=1000, key=None, sender="sender", receiver="receiver"):
    return client.post("/transactions", json={
        "idempotency_key": key or str(uuid.uuid4()),
        "sender_account_id": ids[sender], "receiver_account_id": ids[receiver], "amount": amount})


def balance(account_id):
    db = SessionLocal()
    value = db.get(Account, account_id).balance
    db.close()
    return value


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_normal_payment_follows_the_contract(ids):
    r = pay(ids)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"transaction_id", "state", "decision", "duplicate", "message"}
    assert body["state"] == "COMPLETED" and body["decision"] == "APPROVE" and body["duplicate"] is False
    assert balance(ids["sender"]) == 4000 and balance(ids["receiver"]) == 1000


def test_timeline_lists_every_step_in_order(ids):
    tid = pay(ids).json()["transaction_id"]
    status = client.get(f"/payment-status/{tid}").json()
    assert status["state"] == "COMPLETED"
    assert [(e["from"], e["to"]) for e in status["timeline"]] == [
        ("INITIATED", "PROCESSING"), ("PROCESSING", "DEBITED"), ("DEBITED", "CREDIT_PENDING"),
        ("CREDIT_PENDING", "CREDITED"), ("CREDITED", "COMPLETED")]


def test_transaction_details(ids):
    tid = pay(ids, amount=250).json()["transaction_id"]
    t = client.get(f"/transactions/{tid}").json()
    assert t["amount"] == 250 and t["sender_account_id"] == ids["sender"] and t["state"] == "COMPLETED"


def test_duplicate_key_returns_the_same_payment_and_debits_once(ids):
    key = str(uuid.uuid4())
    first, second = pay(ids, key=key).json(), pay(ids, key=key).json()
    assert second["duplicate"] is True and second["transaction_id"] == first["transaction_id"]
    assert balance(ids["sender"]) == 4000


def test_same_key_with_different_amount_is_409(ids):
    key = str(uuid.uuid4())
    pay(ids, amount=100, key=key)
    assert pay(ids, amount=200, key=key).status_code == 409


@pytest.mark.parametrize("amount", [0, -5])
def test_amount_must_be_positive(ids, amount):
    assert pay(ids, amount=amount).status_code == 422


def test_sender_and_receiver_must_differ(ids):
    assert pay(ids, receiver="sender").status_code == 422


def test_unknown_receiver_is_422_and_nothing_is_stored(ids):
    key = str(uuid.uuid4())
    r = client.post("/transactions", json={"idempotency_key": key, "sender_account_id": ids["sender"],
                                          "receiver_account_id": "no-such-account", "amount": 10})
    assert r.status_code == 422
    db = SessionLocal()
    assert db.query(Transaction).filter_by(idempotency_key=key).count() == 0
    db.close()


def test_receiver_error_needs_reconciliation_and_money_is_held(ids):
    client.post("/sim/config", json={"sender": "SUCCESS", "receiver": "ERROR"})
    r = pay(ids).json()
    assert r["state"] == "RECONCILIATION_REQUIRED" and r["message"] == "Payment under review"
    assert balance(ids["sender"]) == 4000 and balance(ids["receiver"]) == 0     # debited, not credited


def test_lost_confirmation_still_completes(ids):
    client.post("/sim/config", json={"sender": "SUCCESS", "receiver": "LOST_ACK"})
    assert pay(ids).json()["state"] == "COMPLETED"
    assert balance(ids["receiver"]) == 1000


def test_debit_error_fails_and_balance_is_unchanged(ids):
    client.post("/sim/config", json={"sender": "ERROR", "receiver": "SUCCESS"})
    assert pay(ids).json()["state"] == "FAILED"
    assert balance(ids["sender"]) == 5000


def test_insufficient_balance_fails_and_balance_is_unchanged(ids):
    assert pay(ids, amount=500, sender="poor").json()["state"] == "FAILED"
    assert balance(ids["poor"]) == 100


def test_unknown_ids_are_404():
    assert client.get("/transactions/nope").status_code == 404
    assert client.get("/payment-status/nope").status_code == 404


def test_sim_config_switches_and_validates():
    assert client.post("/sim/config", json={"sender": "SUCCESS", "receiver": "TIMEOUT"}).json() == \
        {"sender": "SUCCESS", "receiver": "TIMEOUT"}
    assert client.post("/sim/config", json={"sender": "LOST_ACK", "receiver": "SUCCESS"}).status_code == 422
    assert client.post("/sim/config", json={"sender": "SUCCESS", "receiver": "BROKEN"}).status_code == 422


def test_browser_apps_on_another_port_are_allowed_by_cors():
    r = client.get("/health", headers={"Origin": "http://localhost:5500"})
    assert r.headers["access-control-allow-origin"] == "*"


def test_twenty_simultaneous_requests_with_one_key_create_one_payment(ids):
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(20) as pool:
        results = [f.result() for f in [pool.submit(pay, ids, 100, key) for _ in range(20)]]
    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
    bodies = [r.json() for r in results]
    assert len({b["transaction_id"] for b in bodies}) == 1
    assert sum(1 for b in bodies if b["duplicate"] is False) == 1
    assert balance(ids["sender"]) == 4900                              # debited exactly once
