from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import Base, engine, SessionLocal
from app import models
from app.service import create_transaction, process_payment


app = FastAPI(title="UPIResQ Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


class TransactionRequest(BaseModel):
    idempotency_key: str
    sender_account_id: str
    receiver_account_id: str
    amount: float


def seed_accounts():
    db = SessionLocal()

    try:
        accounts = {
            "acc-alice": 5000.0,
            "acc-bob": 2000.0,
            "acc-chai": 1000.0,
        }

        for account_id, balance in accounts.items():
            if db.get(models.Account, account_id) is None:
                db.add(
                    models.Account(
                        id=account_id,
                        balance=balance,
                    )
                )

        db.commit()

    finally:
        db.close()


seed_accounts()


@app.get("/")
def root():
    return {"message": "UPIResQ backend is running"}


@app.post("/transactions")
def create_transaction_api(request: TransactionRequest):
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero",
        )

    db = SessionLocal()

    try:
        sender = db.get(models.Account, request.sender_account_id)
        receiver = db.get(models.Account, request.receiver_account_id)

        if sender is None:
            raise HTTPException(
                status_code=404,
                detail="Sender account not found",
            )

        if receiver is None:
            raise HTTPException(
                status_code=404,
                detail="Receiver account not found",
            )

        txn, new = create_transaction(
            db,
            request.idempotency_key,
            request.sender_account_id,
            request.receiver_account_id,
            request.amount,
        )

        if new:
            process_payment(db, txn)

        return {
            "transaction_id": txn.id,
            "state": txn.state,
            "new": new,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        db.close()


@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    db = SessionLocal()

    try:
        txn = db.get(models.Transaction, transaction_id)

        if txn is None:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        return {
            "id": txn.id,
            "idempotency_key": txn.idempotency_key,
            "sender": txn.sender_id,
            "receiver": txn.receiver_id,
            "amount": txn.amount,
            "state": txn.state,
            "created_at": txn.created_at,
        }

    finally:
        db.close()


@app.get("/payment-status/{transaction_id}")
def payment_status(transaction_id: str):
    db = SessionLocal()

    try:
        txn = db.get(models.Transaction, transaction_id)

        if txn is None:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        events = (
            db.query(models.TransactionEvent)
            .filter_by(transaction_id=transaction_id)
            .order_by(models.TransactionEvent.created_at)
            .all()
        )

        return {
            "id": txn.id,
            "state": txn.state,
            "amount": txn.amount,
            "sender": txn.sender_id,
            "receiver": txn.receiver_id,
            "timeline": [
                {
                    "from": event.from_state,
                    "to": event.to_state,
                    "detail": event.detail,
                    "created_at": event.created_at,
                }
                for event in events
            ],
        }

    finally:
        db.close()


@app.get("/accounts/{account_id}")
def get_account(account_id: str):
    db = SessionLocal()

    try:
        account = db.get(models.Account, account_id)

        if account is None:
            raise HTTPException(
                status_code=404,
                detail="Account not found",
            )

        return {
            "id": account.id,
            "balance": account.balance,
        }

    finally:
        db.close()


@app.get("/transactions")
def list_transactions(account_id: str = None):
    db = SessionLocal()

    try:
        query = db.query(models.Transaction)

        if account_id:
            query = query.filter(
                (models.Transaction.sender_id == account_id)
                | (models.Transaction.receiver_id == account_id)
            )

        transactions = (
            query
            .order_by(models.Transaction.created_at.desc())
            .all()
        )

        return [
            {
                "id": txn.id,
                "created_at": txn.created_at,
                "sender": txn.sender_id,
                "receiver": txn.receiver_id,
                "amount": txn.amount,
                "state": txn.state,
            }
            for txn in transactions
        ]

    finally:
        db.close()


@app.get("/logs/{transaction_id}")
def get_logs(transaction_id: str):
    db = SessionLocal()

    try:
        events = (
            db.query(models.TransactionEvent)
            .filter_by(transaction_id=transaction_id)
            .order_by(models.TransactionEvent.created_at)
            .all()
        )

        return [
            {
                "from": event.from_state,
                "to": event.to_state,
                "detail": event.detail,
                "created_at": event.created_at,
            }
            for event in events
        ]

    finally:
        db.close()


@app.get("/alerts")
def get_alerts():
    db = SessionLocal()

    try:
        alerts = (
            db.query(models.Alert)
            .order_by(models.Alert.created_at.desc())
            .all()
        )

        return [
            {
                "id": alert.id,
                "transaction_id": alert.transaction_id,
                "recipient": alert.recipient,
                "severity": alert.severity,
                "message": alert.message,
                "created_at": alert.created_at,
            }
            for alert in alerts
        ]

    finally:
        db.close()


@app.get("/cases")
def get_cases():
    db = SessionLocal()

    try:
        cases = (
            db.query(models.FraudCase)
            .order_by(models.FraudCase.created_at.desc())
            .all()
        )

        return [
            {
                "id": case.id,
                "transaction_id": case.transaction_id,
                "reason": case.reason,
                "severity": case.severity,
                "status": case.status,
                "action": case.action,
                "created_at": case.created_at,
            }
            for case in cases
        ]

    finally:
        db.close()