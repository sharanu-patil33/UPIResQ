"""Checks that the database matches the ER diagram."""
import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import engine, SessionLocal
from app.models import (Customer, Account, Merchant, Transaction, TransactionEvent, FraudCase)
from seed import seed

NINE = {"customers", "accounts", "merchants", "devices", "transactions",
        "transaction_events", "risk_results", "alerts", "fraud_cases"}


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def uid():
    return str(uuid.uuid4())


def make_pair(db):
    """A customer with two accounts, for tests that need somewhere to send money."""
    owner = Customer(name="Owner", email=f"{uid()}@example.com")
    db.add(owner)
    db.flush()
    a = Account(customer_id=owner.id, account_number=uid(), balance=100)
    b = Account(customer_id=owner.id, account_number=uid(), balance=0)
    db.add_all([a, b])
    db.commit()
    return a, b


def test_all_nine_tables_exist():
    assert NINE <= set(inspect(engine).get_table_names())


def test_transactions_has_the_columns_in_the_er_diagram():
    cols = {c["name"] for c in inspect(engine).get_columns("transactions")}
    assert {"idempotency_key", "sender_account_id", "receiver_account_id", "merchant_id",
            "device_id", "amount", "location", "state", "created_at", "updated_at"} <= cols


def test_email_must_be_unique(db):
    email = f"{uid()}@example.com"
    db.add(Customer(name="One", email=email))
    db.commit()
    db.add(Customer(name="Two", email=email))
    with pytest.raises(IntegrityError):
        db.commit()


def test_account_must_belong_to_a_real_customer(db):
    db.add(Account(customer_id="no-such-customer", account_number=uid(), balance=0))
    with pytest.raises(IntegrityError):
        db.commit()


def test_merchant_and_device_are_optional_on_a_transaction(db):
    a, b = make_pair(db)
    txn = Transaction(idempotency_key=uid(), sender_account_id=a.id,
                      receiver_account_id=b.id, amount=10)
    db.add(txn)
    db.commit()
    assert txn.merchant_id is None and txn.device_id is None and txn.state == "INITIATED"


def test_unknown_merchant_is_rejected(db):
    a, b = make_pair(db)
    db.add(Transaction(idempotency_key=uid(), sender_account_id=a.id,
                       receiver_account_id=b.id, merchant_id="no-such-merchant", amount=10))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_payment_has_at_most_one_fraud_case(db):
    a, b = make_pair(db)
    txn = Transaction(idempotency_key=uid(), sender_account_id=a.id,
                      receiver_account_id=b.id, amount=10)
    db.add(txn)
    db.commit()
    db.add(FraudCase(transaction_id=txn.id, decision="REVIEW", total_score=55))
    db.commit()
    db.add(FraudCase(transaction_id=txn.id, decision="BLOCK", total_score=90))
    with pytest.raises(IntegrityError):
        db.commit()


def test_events_record_their_type(db):
    a, b = make_pair(db)
    txn = Transaction(idempotency_key=uid(), sender_account_id=a.id,
                      receiver_account_id=b.id, amount=10)
    db.add(txn)
    db.commit()
    db.add(TransactionEvent(transaction_id=txn.id, from_state="INITIATED", to_state="PROCESSING"))
    db.commit()
    event = db.query(TransactionEvent).filter_by(transaction_id=txn.id).one()
    assert event.event_type == "STATE_CHANGE"


def test_seed_adds_demo_data_once(db):
    first = seed(db)
    assert first is True
    assert seed(db) is False                      # second run changes nothing
    assert db.get(Account, "acc-alice").balance == 50000
    assert db.get(Account, "acc-chai").balance == 8000
    assert db.get(Merchant, "m-gift").risk_level == 80
    assert db.query(Customer).filter(Customer.id.like("cust-%")).count() == 3
