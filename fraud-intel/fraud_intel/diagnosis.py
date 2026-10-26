# Rule-based failure diagnosis. A table, not a pile of if/else, so it can be
# printed as the decision table in the report. First matching row wins.
# Each row: (rule id, signals to match, outcome)

DEFAULTS = {"duplicate": False, "receiver_valid": True, "balance_ok": True,
            "debit": None, "credit": None, "status_check": None,
            "network_ok": True, "bank_up": True}


def out(reason, state, action, message, severity, alert_to):
    return {"reason": reason, "next_state": state, "action": action,
            "user_message": message, "severity": severity, "alert_to": alert_to}


RULES = [
    ("R01", {"duplicate": True},
     out("Duplicate request", "UNCHANGED", "Return the existing transaction, no new debit",
         "This payment was already received.", "LOW", [])),
    ("R02", {"receiver_valid": False},
     out("Invalid receiver account", "FAILED", "Reject before any debit",
         "Receiver details are wrong. Nothing was deducted.", "LOW", ["SENDER"])),
    ("R03", {"balance_ok": False},
     out("Insufficient balance", "FAILED", "Reject before any debit",
         "Balance is too low. Nothing was deducted.", "LOW", ["SENDER"])),
    ("R04", {"debit": "ERROR"},
     out("Sender bank declined the debit", "FAILED", "End the payment",
         "Payment failed. Nothing was deducted.", "LOW", ["SENDER"])),
    ("R05", {"debit": "TIMEOUT"},
     out("Sender bank did not answer", "TIMEOUT", "Run a debit status check before anything else",
         "We are checking your payment. Please do not retry yet.", "MEDIUM", ["SENDER", "OPS"])),
    ("R06", {"debit": "OK", "credit": "OK"},
     out("Normal success", "COMPLETED", "Confirm to both sides",
         "Payment completed.", "LOW", [])),
    ("R07", {"debit": "OK", "credit": "ERROR"},
     out("Receiver bank rejected the credit", "RECONCILIATION_REQUIRED",
         "Start the reversal workflow",
         "Money was deducted but not delivered. Do not retry; we are fixing it.",
         "HIGH", ["SENDER", "RECEIVER", "OPS"])),
    ("R08", {"debit": "OK", "credit": "TIMEOUT", "status_check": True},
     out("Credit applied, confirmation lost", "COMPLETED",
         "Update both sides from the status check",
         "Payment completed. The confirmation was delayed.", "LOW", ["SENDER", "RECEIVER"])),
    ("R09", {"debit": "OK", "credit": "TIMEOUT", "status_check": False},
     out("Receiver did not credit", "RECONCILIATION_REQUIRED",
         "Start the reversal workflow",
         "Money was deducted but not delivered. Do not retry; we are fixing it.",
         "HIGH", ["SENDER", "RECEIVER", "OPS"])),
    ("R10", {"debit": "OK", "credit": "TIMEOUT", "status_check": None, "bank_up": False},
     out("Receiver bank unavailable", "TIMEOUT", "Retry the status check later",
         "The receiver's bank is unavailable. Do not retry; this may take longer.",
         "HIGH", ["SENDER", "RECEIVER", "OPS"])),
    ("R11", {"debit": "OK", "credit": "TIMEOUT", "status_check": None, "network_ok": False},
     out("Network failure", "TIMEOUT", "Retry the status check with backoff",
         "Connection problem. We are checking your payment. Do not retry.",
         "MEDIUM", ["SENDER", "OPS"])),
    ("R12", {"debit": "OK", "credit": "TIMEOUT", "status_check": None},
     out("Receiver slow to respond", "TIMEOUT", "Run the credit status check now",
         "Your payment is pending. Do not retry.", "MEDIUM", ["SENDER"])),
]

FALLBACK = out("Unknown combination of signals", "RECONCILIATION_REQUIRED",
               "Send to manual review", "We are reviewing your payment.", "HIGH", ["OPS"])


def diagnose(signals):
    s = {**DEFAULTS, **signals}
    for rule_id, pattern, outcome in RULES:
        if all(s.get(k) == v for k, v in pattern.items()):
            return {"rule": rule_id, **outcome}
    return {"rule": "R99", **FALLBACK}
