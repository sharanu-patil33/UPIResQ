"""Database models for the simulated UPI payment platform."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text

from app.db import Base


def new_id():
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=new_id)

    name = Column(String, nullable=False)

    phone = Column(
        String,
        unique=True,
        nullable=False,
    )

    # Authentication
    email = Column(
        String,
        unique=True,
        nullable=False,
    )

    password_hash = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=new_id)

    customer_id = Column(
        String,
        ForeignKey("customers.id"),
        nullable=True,
    )

    balance = Column(
        Float,
        default=0.0,
    )


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, default=new_id)

    name = Column(
        String,
        nullable=False,
    )

    risk_score = Column(
        Float,
        default=10.0,
    )


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=new_id)

    customer_id = Column(
        String,
        ForeignKey("customers.id"),
        nullable=True,
    )

    device_identifier = Column(
        String,
        unique=True,
        nullable=False,
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(
        String,
        primary_key=True,
        default=new_id,
    )

    # Prevent duplicate payments
    idempotency_key = Column(
        String,
        unique=True,
        nullable=False,
    )

    sender_id = Column(
        String,
        ForeignKey("accounts.id"),
        nullable=False,
    )

    receiver_id = Column(
        String,
        ForeignKey("accounts.id"),
        nullable=False,
    )

    amount = Column(
        Float,
        nullable=False,
    )

    # Fraud / transaction context
    location = Column(
        String,
        nullable=True,
    )

    merchant_id = Column(
        String,
        ForeignKey("merchants.id"),
        nullable=True,
    )

    device_id = Column(
        String,
        ForeignKey("devices.id"),
        nullable=True,
    )

    state = Column(
        String,
        nullable=False,
        default="INITIATED",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class TransactionEvent(Base):
    """Append-only transaction state history."""

    __tablename__ = "transaction_events"

    id = Column(
        String,
        primary_key=True,
        default=new_id,
    )

    transaction_id = Column(
        String,
        ForeignKey("transactions.id"),
        nullable=False,
    )

    from_state = Column(String)

    to_state = Column(String)

    detail = Column(Text)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class RiskResult(Base):
    __tablename__ = "risk_results"

    id = Column(
        String,
        primary_key=True,
        default=new_id,
    )

    transaction_id = Column(
        String,
        ForeignKey("transactions.id"),
        nullable=False,
    )

    decision = Column(
        String,
        nullable=False,
    )

    score = Column(
        Float,
        nullable=False,
    )

    rule_score = Column(
        Float,
        nullable=True,
    )

    ml_score = Column(
        Float,
        nullable=True,
    )

    details = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(
        String,
        primary_key=True,
        default=new_id,
    )

    transaction_id = Column(
        String,
        ForeignKey("transactions.id"),
        nullable=True,
    )

    recipient = Column(
        String,
        nullable=False,
    )

    severity = Column(
        String,
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class FraudCase(Base):
    __tablename__ = "fraud_cases"

    id = Column(
        String,
        primary_key=True,
        default=new_id,
    )

    transaction_id = Column(
        String,
        ForeignKey("transactions.id"),
        nullable=False,
    )

    reason = Column(
        String,
        nullable=False,
    )

    severity = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="OPEN",
    )

    action = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )