"""Core tables. Add customers, merchants, devices, risk_results, alerts and fraud_cases
following the same pattern (see docs/schema.md)."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, ForeignKey

from app.db import Base


def new_id():
    return str(uuid.uuid4())


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=new_id)
    balance = Column(Float, default=0.0)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=new_id)
    idempotency_key = Column(String, unique=True, nullable=False)   # the duplicate guard
    sender_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    receiver_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    state = Column(String, nullable=False, default="INITIATED")
    created_at = Column(DateTime, default=datetime.utcnow)


class TransactionEvent(Base):
    """Append-only: never update or delete rows in this table."""
    __tablename__ = "transaction_events"
    id = Column(String, primary_key=True, default=new_id)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    from_state = Column(String)
    to_state = Column(String)
    detail = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
