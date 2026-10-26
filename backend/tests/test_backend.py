"""Backend reference tests. Run from backend/:   python -m pytest tests/ -v"""
import os
import threading

os.environ["DATABASE_URL"] = "sqlite:///./test_upi.db"
if os.path.exists("test_upi.db"):
    os.remove("test_upi.db")

import pytest

from app.db import Base, engine, SessionLocal
from app.models import Account, Transaction, TransactionEvent
from app import simulators
from app.service import create_transaction, process_payment, transition

Base.metadata.create_all(engine)


@pytest.fixture(scope="module")
def accounts():
    db = SessionLocal()
    a, b = Account(balance=5000), Account(balance=0)
    db.add_all([a, b]); db.commit()
    ids = (a.id, b.id)
    db.close()
    return ids


def run(accounts, key, sender="SUCCESS", receiver="SUCCESS", amount=1000):
    simulators.CONFIG["sender"], simulators.CONFIG["receiver"] = sender, receiver
    db = SessionLocal()
    txn, new = create_transaction(db, key, accounts[0], accounts[1], amount)
    if new:
        process_payment(db, txn)
    out = (txn.state, new)
    db.close()
    return out


def test_success(accounts):
    assert run(accounts, "k1") == ("COMPLETED", True)


def test_credit_error_needs_reconciliation(accounts):
    assert run(accounts, "k2", receiver="ERROR")[0] == "RECONCILIATION_REQUIRED"


def test_receiver_timeout_needs_reconciliation(accounts):
    assert run(accounts, "k3", receiver="TIMEOUT")[0] == "RECONCILIATION_REQUIRED"


def test_lost_ack_completes_after_status_check(accounts):
    assert run(accounts, "k4", receiver="LOST_ACK")[0] == "COMPLETED"


def test_debit_error_fails(accounts):
    assert run(accounts, "k5", sender="ERROR")[0] == "FAILED"


def test_insufficient_balance_fails(accounts):
    assert run(accounts, "k6", amount=999999)[0] == "FAILED"


def test_duplicate_key_returns_existing(accounts):
    run(accounts, "k7")
    assert run(accounts, "k7") == ("COMPLETED", False)


def test_same_key_different_details_rejected(accounts):
    run(accounts, "k8", amount=100)
    with pytest.raises(ValueError):
        run(accounts, "k8", amount=200)


def test_illegal_transition_rejected(accounts):
    db = SessionLocal()
    txn = db.query(Transaction).filter_by(idempotency_key="k1").one()
    with pytest.raises(ValueError):
        transition(db, txn, "PROCESSING")
    db.close()


def test_every_state_change_is_logged(accounts):
    db = SessionLocal()
    txn = db.query(Transaction).filter_by(idempotency_key="k1").one()
    events = db.query(TransactionEvent).filter_by(transaction_id=txn.id).count()
    db.close()
    # PROCESSING, DEBITED, CREDIT_PENDING, CREDITED, COMPLETED
    assert events == 5


def test_concurrent_duplicates_create_one_row(accounts):
    simulators.CONFIG["sender"] = simulators.CONFIG["receiver"] = "SUCCESS"
    created = []

    def worker():
        db = SessionLocal()
        try:
            _, new = create_transaction(db, "same-key", accounts[0], accounts[1], 10)
            created.append(new)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    db = SessionLocal()
    rows = db.query(Transaction).filter_by(idempotency_key="same-key").count()
    db.close()
    assert rows == 1 and created.count(True) == 1
