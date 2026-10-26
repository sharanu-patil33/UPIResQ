# Architecture

```
UPI App (frontend/upi-app)        Ops Dashboard (frontend/ops-dashboard)
          \                         /
           \                       /
            Backend API (FastAPI)  -- backend/
              |-- Payment state machine + idempotency
              |-- Sender bank simulator / Receiver bank simulator
              |-- DB (SQLite -> Postgres later)
              |
              |-- calls --> fraud-intel/
                              |-- checks/          6 fraud checks (ThreadPoolExecutor)
                              |-- ml/              fraud model + recovery-time estimator
                              |-- reconciliation/  rule-based diagnosis (no ML)
              |
              Alert engine --> sender / receiver / ops
```

## Two engines, kept separate on purpose
- Diagnosis (why is it stuck?) = rules, real-time, no training data.
- Fraud + recovery time = ML, trained on historical/synthetic data.

## Payment state machine
INITIATED -> PROCESSING -> DEBITED -> CREDIT_PENDING -> CREDITED -> COMPLETED
Failure branches: TIMEOUT, FAILED, RECONCILIATION_REQUIRED.
Every transition is an append-only row in transaction_events.

## Integration contract (lock in Phase 0)
- POST /transactions            body: idempotency_key, sender_account_id, receiver_account_id, amount, location, merchant_id?, device_id?
- GET  /transactions/{id}
- GET  /risk/{id}
- GET  /payment-status/{id}
- GET  /alerts, /cases, /logs/{id}

## Additions requested by Member 3 (agree in Phase 0)
- `GET /transactions?account_id=&state=` returns a list: id, created_at, sender, receiver, amount, state, decision, score.
- `GET /accounts/{id}` returns the balance.
- `GET /payment-status/{id}` may also include `diagnosis` (reason, severity, action, user_message) and `recovery` (message).
- The backend enables CORS so the browser app can call it.
- Tests need a repeatable way to trigger a fraud BLOCK (for example a fixed risky amount).
