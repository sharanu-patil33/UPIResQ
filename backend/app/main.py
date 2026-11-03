from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from hashlib import sha256
import secrets
import uuid

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


# -----------------------------
# Request models
# -----------------------------

class RegisterRequest(BaseModel):
    name: str
    phone: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TransactionRequest(BaseModel):
    idempotency_key: str
    sender_account_id: str
    receiver_account_id: str
    amount: float


# -----------------------------
# Authentication helpers
# -----------------------------

def hash_password(password):
    return sha256(password.encode("utf-8")).hexdigest()


def create_session_token():
    return secrets.token_urlsafe(32)


# Simple in-memory sessions for the simulated project.
# A production system would use persistent sessions/JWT.
SESSIONS = {}


# -----------------------------
# Seed demo accounts
# -----------------------------

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


# -----------------------------
# Root
# -----------------------------

@app.get("/")
def root():
    return {
        "message": "UPIResQ backend is running",
        "version": "1.0",
    }


# -----------------------------
# Register
# -----------------------------

@app.post("/auth/register")
def register(request: RegisterRequest):
    if len(request.name.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Name must contain at least 2 characters",
        )

    if len(request.phone.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid phone number",
        )

    if len(request.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters",
        )

    db = SessionLocal()

    try:
        existing_phone = (
            db.query(models.Customer)
            .filter_by(phone=request.phone.strip())
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=409,
                detail="Phone number already registered",
            )

        existing_email = (
            db.query(models.Customer)
            .filter_by(email=request.email.lower().strip())
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=409,
                detail="Email already registered",
            )

        customer = models.Customer(
            name=request.name.strip(),
            phone=request.phone.strip(),
            email=request.email.lower().strip(),
            password_hash=hash_password(request.password),
        )

        db.add(customer)
        db.flush()

        account = models.Account(
            customer_id=customer.id,
            balance=1000.0,
        )

        db.add(account)
        db.commit()

        return {
            "message": "Account created successfully",
            "customer_id": customer.id,
            "account_id": account.id,
            "name": customer.name,
            "email": customer.email,
            "balance": account.balance,
        }

    finally:
        db.close()


# -----------------------------
# Login
# -----------------------------

@app.post("/auth/login")
def login(request: LoginRequest):
    db = SessionLocal()

    try:
        customer = (
            db.query(models.Customer)
            .filter_by(email=request.email.lower().strip())
            .first()
        )

        if customer is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if customer.password_hash != hash_password(request.password):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        account = (
            db.query(models.Account)
            .filter_by(customer_id=customer.id)
            .first()
        )

        token = create_session_token()
        SESSIONS[token] = customer.id

        return {
            "message": "Login successful",
            "token": token,
            "customer_id": customer.id,
            "account_id": account.id if account else None,
            "name": customer.name,
            "email": customer.email,
            "balance": account.balance if account else 0.0,
        }

    finally:
        db.close()


# -----------------------------
# Current user
# -----------------------------

@app.get("/auth/me")
def current_user(token: str):
    customer_id = SESSIONS.get(token)

    if not customer_id:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    db = SessionLocal()

    try:
        customer = db.get(models.Customer, customer_id)

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        account = (
            db.query(models.Account)
            .filter_by(customer_id=customer.id)
            .first()
        )

        return {
            "customer_id": customer.id,
            "account_id": account.id if account else None,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "balance": account.balance if account else 0.0,
        }

    finally:
        db.close()


# -----------------------------
# Logout
# -----------------------------

@app.post("/auth/logout")
def logout(token: str):
    SESSIONS.pop(token, None)

    return {
        "message": "Logged out successfully",
    }


# -----------------------------
# Create transaction
# -----------------------------

@app.post("/transactions")
def create_transaction_api(request: TransactionRequest):
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero",
        )

    db = SessionLocal()

    try:
        sender = db.get(
            models.Account,
            request.sender_account_id,
        )

        receiver = db.get(
            models.Account,
            request.receiver_account_id,
        )

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
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    finally:
        db.close()


# -----------------------------
# Transaction details
# -----------------------------

@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    db = SessionLocal()

    try:
        txn = db.get(
            models.Transaction,
            transaction_id,
        )

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


# -----------------------------
# Payment status + timeline
# -----------------------------

@app.get("/payment-status/{transaction_id}")
def payment_status(transaction_id: str):
    db = SessionLocal()

    try:
        txn = db.get(
            models.Transaction,
            transaction_id,
        )

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


# -----------------------------
# Account
# -----------------------------

@app.get("/accounts/{account_id}")
def get_account(account_id: str):
    db = SessionLocal()

    try:
        account = db.get(
            models.Account,
            account_id,
        )

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


# -----------------------------
# Transaction history
# -----------------------------

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


# -----------------------------
# Logs
# -----------------------------

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


# -----------------------------
# Alerts
# -----------------------------

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


# -----------------------------
# Fraud cases
# -----------------------------

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