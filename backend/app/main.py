
"""The FastAPI app. Wraps the payment service in the HTTP contract (docs/architecture.md).
Run from the backend folder: uvicorn app.main:app --reload --port 8000
Then open http://127.0.0.1:8000/docs to try every endpoint.
"""

from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import simulators
from app.db import SessionLocal, init_db
from app.models import (
    Account,
    Alert,
    FraudCase,
    Transaction,
    TransactionEvent,
)
from app.service import create_transaction, process_payment


# ---------------------------------------------------------------- lifespan

@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="UPIResQ backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- database

def get_db():
    """One database session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------- request bodies

class PaymentIn(BaseModel):
    idempotency_key: str = Field(min_length=1)
    sender_account_id: str
    receiver_account_id: str
    amount: float = Field(gt=0)
    location: Optional[str] = None
    merchant_id: Optional[str] = None
    device_id: Optional[str] = None


class SimIn(BaseModel):
    sender: Literal["SUCCESS", "ERROR", "TIMEOUT"] = "SUCCESS"
    receiver: Literal["SUCCESS", "ERROR", "TIMEOUT", "LOST_ACK"] = "SUCCESS"


# ---------------------------------------------------------------- helpers

MESSAGES = {
    "COMPLETED": "Payment completed",
    "FAILED": "Payment failed",
    "RECONCILIATION_REQUIRED": "Payment under review",
}


def decision_for(db, txn):
    """Return the fraud decision, or APPROVE until the fraud engine is connected."""
    case = (
        db.query(FraudCase)
        .filter_by(transaction_id=txn.id)
        .one_or_none()
    )
    return case.decision if case else "APPROVE"


def get_transaction_or_404(db, tid):
    txn = db.get(Transaction, tid)
    if txn is None:
        raise HTTPException(status_code=404, detail="Unknown transaction")
    return txn


# ---------------------------------------------------------------- endpoints

@app.get("/health")
def health():
    return {"status": "ok"}


# Create a payment
@app.post("/transactions")
def post_transaction(p: PaymentIn, db: Session = Depends(get_db)):

    if p.sender_account_id == p.receiver_account_id:
        raise HTTPException(
            status_code=422,
            detail="Sender and receiver must be different",
        )

    for account_id in (p.sender_account_id, p.receiver_account_id):
        if db.get(Account, account_id) is None:
            raise HTTPException(
                status_code=422,
                detail=f"Account not found: {account_id}",
            )

    try:
        txn, is_new = create_transaction(
            db,
            p.idempotency_key,
            p.sender_account_id,
            p.receiver_account_id,
            p.amount,
            location=p.location,
            merchant_id=p.merchant_id,
            device_id=p.device_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err))

    if is_new:
        process_payment(db, txn)

    return {
        "transaction_id": txn.id,
        "state": txn.state,
        "decision": decision_for(db, txn),
        "duplicate": not is_new,
        "message": (
            MESSAGES.get(txn.state, "Payment in progress")
            if is_new
            else "Payment already received"
        ),
    }


# Get transaction details
@app.get("/transactions/{tid}")
def get_transaction(tid: str, db: Session = Depends(get_db)):
    t = get_transaction_or_404(db, tid)

    return {
        "id": t.id,
        "idempotency_key": t.idempotency_key,
        "sender_account_id": t.sender_account_id,
        "receiver_account_id": t.receiver_account_id,
        "merchant_id": t.merchant_id,
        "device_id": t.device_id,
        "amount": t.amount,
        "location": t.location,
        "state": t.state,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


# Get payment status and timeline
@app.get("/payment-status/{tid}")
def payment_status(tid: str, db: Session = Depends(get_db)):
    t = get_transaction_or_404(db, tid)

    events = (
        db.query(TransactionEvent)
        .filter_by(transaction_id=tid)
        .order_by(
            TransactionEvent.created_at,
            text("transaction_events.rowid"),
        )
        .all()
    )

    return {
        "transaction_id": t.id,
        "state": t.state,
        "timeline": [
            {
                "from": e.from_state,
                "to": e.to_state,
                "detail": e.detail or "",
                "at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


# Get saved alerts
@app.get("/alerts")
def get_alerts(
    transaction_id: Optional[str] = None,
    recipient_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve alerts saved in the database.

    Optional filters:
    - transaction_id: retrieve alerts for one transaction
    - recipient_type: retrieve alerts for a recipient such as SENDER, RECEIVER or OPS
    """

    query = db.query(Alert)

    if transaction_id:
        query = query.filter(Alert.transaction_id == transaction_id)

    if recipient_type:
        query = query.filter(Alert.recipient_type == recipient_type.upper())

    alerts = query.order_by(Alert.created_at.desc()).all()

    return {
        "alerts": [
            {
                "id": alert.id,
                "transaction_id": alert.transaction_id,
                "recipient_type": alert.recipient_type,
                "message": alert.message,
                "created_at": (
                    alert.created_at.isoformat()
                    if alert.created_at
                    else None
                ),
            }
            for alert in alerts
        ],
        "total": len(alerts),
    }


# Configure payment simulators
@app.post("/sim/config")
def set_simulators(c: SimIn):
    simulators.CONFIG["sender"] = c.sender
    simulators.CONFIG["receiver"] = c.receiver

    return {
        "sender": c.sender,
        "receiver": c.receiver,
    }
