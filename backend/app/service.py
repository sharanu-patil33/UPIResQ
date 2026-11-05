
from sqlalchemy.exc import IntegrityError

from app.models import Transaction, TransactionEvent, Account, Alert
from app import simulators


# Allowed payment state transitions
ALLOWED = {
    "INITIATED": {"PROCESSING", "FAILED"},
    "PROCESSING": {"DEBITED", "FAILED", "TIMEOUT"},
    "DEBITED": {"CREDIT_PENDING"},
    "CREDIT_PENDING": {
        "CREDITED",
        "TIMEOUT",
        "RECONCILIATION_REQUIRED"
    },
    "CREDITED": {"COMPLETED"},
    "TIMEOUT": {
        "CREDITED",
        "RECONCILIATION_REQUIRED",
        "FAILED"
    },
    "RECONCILIATION_REQUIRED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}


# Alert recipients for important payment states
ALERT_RECIPIENTS = {
    "FAILED": ["SENDER"],
    "RECONCILIATION_REQUIRED": ["SENDER", "RECEIVER", "OPS"],
}


def transition(db, txn, new_state, detail=""):
    """Change payment state, record event and save required alerts."""

    if new_state not in ALLOWED[txn.state]:
        raise ValueError(
            f"Illegal transition {txn.state} -> {new_state}"
        )

    previous_state = txn.state

    # Record payment state change
    db.add(
        TransactionEvent(
            transaction_id=txn.id,
            event_type="STATE_CHANGE",
            from_state=previous_state,
            to_state=new_state,
            detail=detail
        )
    )

    # Create alerts for important payment states
    recipients = ALERT_RECIPIENTS.get(new_state, [])

    for recipient in recipients:
        db.add(
            Alert(
                transaction_id=txn.id,
                recipient_type=recipient,
                message=(
                    detail
                    or f"Payment {txn.id} status changed to {new_state}"
                )
            )
        )

    # Update transaction state
    txn.state = new_state

    # Save transaction event, alerts and state together
    db.commit()


def create_transaction(
    db,
    key,
    sender_account_id,
    receiver_account_id,
    amount,
    location=None,
    merchant_id=None,
    device_id=None
):
    """Create a transaction with idempotency protection."""

    txn = Transaction(
        idempotency_key=key,
        sender_account_id=sender_account_id,
        receiver_account_id=receiver_account_id,
        amount=amount,
        location=location,
        merchant_id=merchant_id,
        device_id=device_id
    )

    db.add(txn)

    try:
        db.commit()
        return txn, True

    except IntegrityError:
        db.rollback()

        existing = (
            db.query(Transaction)
            .filter_by(idempotency_key=key)
            .one_or_none()
        )

        if existing is None:
            raise

        same = (
            existing.sender_account_id,
            existing.receiver_account_id,
            existing.amount
        ) == (
            sender_account_id,
            receiver_account_id,
            amount
        )

        if not same:
            raise ValueError(
                "Idempotency key reused with different details"
            )

        return existing, False


def process_payment(db, txn):
    """Process payment using sender and receiver bank simulators."""

    sender = db.get(Account, txn.sender_account_id)

    # Check sender balance
    if sender.balance < txn.amount:
        transition(
            db,
            txn,
            "FAILED",
            "Insufficient balance"
        )
        return txn

    # Start payment processing
    transition(db, txn, "PROCESSING")

    # Debit sender account
    d = simulators.debit(
        txn.id,
        txn.sender_account_id,
        txn.amount
    )

    if d["status"] != "OK":
        transition(
            db,
            txn,
            "FAILED",
            f"Debit {d['code']}"
        )
        return txn

    sender.balance -= txn.amount

    transition(db, txn, "DEBITED")
    transition(db, txn, "CREDIT_PENDING")

    # Credit receiver account
    c = simulators.credit(
        txn.id,
        txn.receiver_account_id,
        txn.amount
    )

    if c["status"] == "OK":

        receiver = db.get(Account, txn.receiver_account_id)
        receiver.balance += txn.amount

        transition(db, txn, "CREDITED")
        transition(db, txn, "COMPLETED")

    elif c["status"] == "ERROR":

        transition(
            db,
            txn,
            "RECONCILIATION_REQUIRED",
            f"Credit {c['code']}"
        )

    else:
        # Receiver timeout: check payment status
        transition(
            db,
            txn,
            "TIMEOUT",
            "No credit response"
        )

        status = simulators.status_check(txn.id)

        if status["credited"]:

            receiver = db.get(
                Account,
                txn.receiver_account_id
            )

            receiver.balance += txn.amount

            transition(
                db,
                txn,
                "CREDITED",
                "Found by status check"
            )

            transition(db, txn, "COMPLETED")

        else:

            transition(
                db,
                txn,
                "RECONCILIATION_REQUIRED",
                "No credit after status check"
            )

    return txn
