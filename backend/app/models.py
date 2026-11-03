"""All 9 tables. Matches docs/schema.md and the ER diagram (docs/images/ER-Diagram.png)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey

from app.db import Base


def new_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    avg_txn_amount = Column(Float, nullable=False, default=0.0)   # Amount check
    home_location = Column(String)                                # Location check
    created_at = Column(DateTime, default=utcnow)


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=new_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    account_number = Column(String, unique=True, nullable=False)
    balance = Column(Float, nullable=False, default=0.0)


class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    risk_level = Column(Integer, nullable=False, default=0)       # 0 to 100


class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, default=new_id)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    device_fingerprint = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    first_seen = Column(DateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=new_id)
    idempotency_key = Column(String, unique=True, nullable=False)  # the duplicate guard
    sender_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    receiver_account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    merchant_id = Column(String, ForeignKey("merchants.id"))       # optional
    device_id = Column(String, ForeignKey("devices.id"))           # optional
    amount = Column(Float, nullable=False)
    location = Column(String)
    state = Column(String, nullable=False, default="INITIATED")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class TransactionEvent(Base):
    """Append-only: never update or delete rows in this table."""
    __tablename__ = "transaction_events"
    id = Column(String, primary_key=True, default=new_id)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    event_type = Column(String, nullable=False, default="STATE_CHANGE")
    from_state = Column(String)
    to_state = Column(String)
    detail = Column(String)
    created_at = Column(DateTime, default=utcnow)


class RiskResult(Base):
    """One row per fraud check (Member 2 fills these)."""
    __tablename__ = "risk_results"
    id = Column(String, primary_key=True, default=new_id)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    check_name = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    reason = Column(String)
    thread_name = Column(String)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=new_id)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    recipient_type = Column(String, nullable=False)                # SENDER, RECEIVER or OPS
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class FraudCase(Base):
    __tablename__ = "fraud_cases"
    id = Column(String, primary_key=True, default=new_id)
    transaction_id = Column(String, ForeignKey("transactions.id"),
                            nullable=False, unique=True)           # at most one case per payment
    decision = Column(String, nullable=False)                      # REVIEW or BLOCK
    total_score = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="OPEN")        # OPEN, REVIEWED or CLOSED
    created_at = Column(DateTime, default=utcnow)
