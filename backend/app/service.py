from sqlalchemy.exc import IntegrityError

from app.models import Transaction, TransactionEvent, Account
from app import simulators

ALLOWED = {
    "INITIATED": {"PROCESSING", "FAILED"},
    "PROCESSING": {"DEBITED", "FAILED", "TIMEOUT"},
    "DEBITED": {"CREDIT_PENDING"},
    "CREDIT_PENDING": {"CREDITED", "TIMEOUT", "RECONCILIATION_REQUIRED"},
    "CREDITED": {"COMPLETED"},
    "TIMEOUT": {"CREDITED", "RECONCILIATION_REQUIRED", "FAILED"},
    "RECONCILIATION_REQUIRED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}


def transition(db, txn, new_state, detail=""):
    if new_state not in ALLOWED[txn.state]:
        raise ValueError(f"Illegal transition {txn.state} -> {new_state}")
    db.add(TransactionEvent(transaction_id=txn.id, from_state=txn.state,
                            to_state=new_state, detail=detail))
    txn.state = new_state
    db.commit()


def create_transaction(db, key, sender_id, receiver_id, amount):
    txn = Transaction(idempotency_key=key, sender_id=sender_id,
                      receiver_id=receiver_id, amount=amount)
    db.add(txn)
    try:
        db.commit()
        return txn, True                      # newly created
    except IntegrityError:
        db.rollback()
        existing = db.query(Transaction).filter_by(idempotency_key=key).one()
        same = (existing.sender_id, existing.receiver_id, existing.amount) == \
               (sender_id, receiver_id, amount)
        if not same:
            raise ValueError("Idempotency key reused with different details")
        return existing, False                # duplicate request


def process_payment(db, txn):
    sender = db.get(Account, txn.sender_id)
    if sender.balance < txn.amount:
        transition(db, txn, "FAILED", "Insufficient balance")
        return txn
    transition(db, txn, "PROCESSING")
    d = simulators.debit(txn.id, txn.sender_id, txn.amount)
    if d["status"] != "OK":
        transition(db, txn, "FAILED", f"Debit {d['code']}")
        return txn
    sender.balance -= txn.amount
    transition(db, txn, "DEBITED")
    transition(db, txn, "CREDIT_PENDING")
    c = simulators.credit(txn.id, txn.receiver_id, txn.amount)
    if c["status"] == "OK":
        db.get(Account, txn.receiver_id).balance += txn.amount
        transition(db, txn, "CREDITED"); transition(db, txn, "COMPLETED")
    elif c["status"] == "ERROR":
        transition(db, txn, "RECONCILIATION_REQUIRED", f"Credit {c['code']}")
    else:                                     # timeout: ask the receiver bank
        transition(db, txn, "TIMEOUT", "No credit response")
        if simulators.status_check(txn.id)["credited"]:
            receiver = db.get(Account, txn.receiver_id)
            receiver.balance += txn.amount
            transition(db, txn, "CREDITED", "Found by status check")
            transition(db, txn, "COMPLETED")
        else:
            transition(db, txn, "RECONCILIATION_REQUIRED", "No credit after status check")
    return txn
