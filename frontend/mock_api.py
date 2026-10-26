"""Mock backend so Member 3 can build and test the screens before Member 1 is ready.
Run:  uvicorn mock_api:app --port 8000
Follows the agreed contract, plus GET /transactions and GET /accounts/{id}."""
import threading
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Mock payment API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ACCOUNTS = {"acc-alice": {"name": "Alice", "balance": 50000.0},
            "acc-bob": {"name": "Bob", "balance": 30000.0},
            "acc-chai": {"name": "Chai Stall", "balance": 8000.0}}
SIM = {"sender": "SUCCESS", "receiver": "SUCCESS"}
TXNS, KEYS, EVENTS, RISK, DIAG = {}, {}, {}, {}, {}
ALERTS, CASES = [], []
LOCK = threading.Lock()      # the real backend uses a DB unique constraint instead
STUCK = {"RECONCILIATION_REQUIRED", "TIMEOUT"}


class PaymentIn(BaseModel):
    idempotency_key: str
    sender_account_id: str
    receiver_account_id: str
    amount: float
    location: Optional[str] = None


class SimIn(BaseModel):
    sender: str = "SUCCESS"
    receiver: str = "SUCCESS"


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def move(tid, new, detail=""):
    t = TXNS[tid]
    EVENTS[tid].append({"from": t["state"], "to": new, "detail": detail, "at": now()})
    t["state"] = new


def alert(tid, who, msg):
    ALERTS.append({"transaction_id": tid, "recipient": who, "message": msg, "at": now()})


@app.post("/transactions")
def create(p: PaymentIn):
    with LOCK:
        return _create(p)


def _create(p: PaymentIn):
    if p.idempotency_key in KEYS:
        t = TXNS[KEYS[p.idempotency_key]]
        return {"transaction_id": t["id"], "state": t["state"], "decision": t["decision"],
                "duplicate": True, "message": "Payment already received"}
    if p.amount <= 0 or p.sender_account_id == p.receiver_account_id:
        raise HTTPException(422, "Amount must be positive and receiver must differ from sender")
    if p.receiver_account_id not in ACCOUNTS or p.sender_account_id not in ACCOUNTS:
        raise HTTPException(422, "Account not found")
    tid = str(uuid.uuid4())
    KEYS[p.idempotency_key] = tid
    decision = "BLOCK" if p.amount >= 50000 else "REVIEW" if p.amount >= 20000 else "APPROVE"
    score = {"BLOCK": 83.0, "REVIEW": 52.0, "APPROVE": 8.0}[decision]
    TXNS[tid] = {"id": tid, "created_at": now(), "sender": p.sender_account_id,
                 "receiver": p.receiver_account_id, "amount": p.amount, "state": "INITIATED",
                 "decision": decision, "score": score}
    EVENTS[tid] = []
    RISK[tid] = {"decision": decision, "score": score, "checks": [
        {"check": "amount", "score": 90 if decision != "APPROVE" else 0, "reason": "Amount vs usual"},
        {"check": "location", "score": 0, "reason": "Matches home location"},
        {"check": "velocity", "score": 0, "reason": "Normal"},
        {"check": "behavior", "score": 40 if decision != "APPROVE" else 0, "reason": "Usual pattern"},
        {"check": "merchant", "score": 0, "reason": "Person-to-person"},
        {"check": "device", "score": 0, "reason": "Recognised device"}]}
    if decision != "APPROVE":
        CASES.append({"transaction_id": tid, "decision": decision, "score": score, "status": "OPEN"})
    sender = ACCOUNTS[p.sender_account_id]
    if decision == "BLOCK":
        move(tid, "FAILED", "Blocked by fraud check")
    elif sender["balance"] < p.amount:
        move(tid, "FAILED", "Insufficient balance")
    else:
        move(tid, "PROCESSING")
        if SIM["sender"] != "SUCCESS":
            move(tid, "FAILED", "Debit failed")
        else:
            sender["balance"] -= p.amount
            move(tid, "DEBITED"); move(tid, "CREDIT_PENDING")
            if SIM["receiver"] in ("SUCCESS", "LOST_ACK"):
                ACCOUNTS[p.receiver_account_id]["balance"] += p.amount
                move(tid, "CREDITED"); move(tid, "COMPLETED")
            else:
                move(tid, "RECONCILIATION_REQUIRED", "No credit from receiver bank")
                DIAG[tid] = {"reason": "Receiver did not credit", "severity": "HIGH",
                             "action": "Start the reversal workflow",
                             "user_message": "Money was deducted but not delivered. Do not retry; we are fixing it."}
                for who in ("SENDER", "RECEIVER", "OPS"):
                    alert(tid, who, DIAG[tid]["user_message"])
    t = TXNS[tid]
    return {"transaction_id": tid, "state": t["state"], "decision": decision, "duplicate": False,
            "message": "Payment " + t["state"].lower().replace("_", " ")}


@app.get("/transactions")
def list_transactions(account_id: Optional[str] = None, state: Optional[str] = None):
    rows = [t for t in TXNS.values()
            if (not account_id or account_id in (t["sender"], t["receiver"]))
            and (not state or t["state"] == state)]
    return sorted(rows, key=lambda t: t["created_at"], reverse=True)


@app.get("/transactions/{tid}")
def get_one(tid: str):
    if tid not in TXNS:
        raise HTTPException(404, "Unknown transaction")
    return TXNS[tid]


@app.get("/payment-status/{tid}")
def status(tid: str):
    if tid not in TXNS:
        raise HTTPException(404, "Unknown transaction")
    out = {"transaction_id": tid, "state": TXNS[tid]["state"], "timeline": EVENTS[tid]}
    if tid in DIAG:
        out["diagnosis"] = DIAG[tid]
        out["recovery"] = {"message": "Cases like this are usually resolved in about 38 minutes "
                                      "(typically 28 to 51). This is an estimate, not a guarantee."}
    return out


@app.get("/risk/{tid}")
def risk(tid: str):
    if tid not in RISK:
        raise HTTPException(404, "No risk result")
    return RISK[tid]


@app.get("/alerts")
def alerts():
    return list(reversed(ALERTS))


@app.get("/cases")
def cases():
    return CASES


@app.get("/logs/{tid}")
def logs(tid: str):
    return EVENTS.get(tid, [])


@app.get("/accounts/{aid}")
def account(aid: str):
    if aid not in ACCOUNTS:
        raise HTTPException(404, "Unknown account")
    return {"id": aid, **ACCOUNTS[aid]}


@app.post("/sim/config")
def sim(c: SimIn):
    SIM.update(sender=c.sender, receiver=c.receiver)
    return SIM
