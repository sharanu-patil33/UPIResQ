# Backend — Payment Core (Member A)

You own the ground truth: the database, the payment APIs, the state machine, and the
fake banks. Every other track calls into what you build here.

## Task Checklist

### Phase 1 — Core Skeleton
- [ ] Set up FastAPI app + SQLAlchemy + SQLite (`app/core/db.py`)
- [ ] Build all 9 DB models (`app/models/`): customers, accounts, merchants, devices,
      transactions, transaction_events, risk_results, alerts, fraud_cases
- [ ] Build sender bank simulator and receiver bank simulator
      (`app/simulators/`) — each should accept a configurable delay and a
      configurable failure mode (success / timeout / error / slow), so the rest of
      the team can trigger every failure case on demand for testing.
- [ ] `POST /transactions` endpoint that creates a transaction row (no fraud/state
      logic yet — just persist it and return an ID).

### Phase 2 — Happy Path
- [ ] Wire `POST /transactions` to call the sender simulator (debit), then the
      receiver simulator (credit), and update `Transaction.state` accordingly.
- [ ] `GET /transactions/{id}` and `GET /payment-status/{id}` return real data.
- [ ] Call out to Fraud-Intel's check function(s) per transaction (agree the Python
      function signature with Member B — don't just wait for their final version,
      stub it yourself and swap it in later).

### Phase 3 — The Real Contribution
- [ ] Add `idempotency_key` column with a DB-level **unique constraint** (not an
      application if-check) on `transactions`. A repeat key should return the
      existing transaction, not create a new row — test this under concurrent
      requests, not just sequentially.
- [ ] Implement the full state machine: `INITIATED → PROCESSING → DEBITED →
      CREDIT_PENDING → CREDITED → COMPLETED`, plus `TIMEOUT / FAILED /
      RECONCILIATION_REQUIRED`. Every transition writes a row to
      `transaction_events` (append-only, never update/delete existing rows).
- [ ] Debit-check and credit-check run as independent threads/tasks that each
      verify their side and flag `RECONCILIATION_REQUIRED` on timeout/mismatch.

### Phase 4 — Integration Hardening
- [ ] `GET /alerts`, `GET /cases`, `GET /logs/{id}` endpoints for Frontend's ops
      dashboard.
- [ ] Confirm every endpoint matches the API contract agreed in Phase 0 exactly —
      field names, types, status codes. Frontend and Fraud-Intel are coding against
      this contract without reading your implementation.
- [ ] Load-test the idempotency constraint: fire the same idempotency_key twice
      concurrently, confirm only one transaction is ever created.

## Key Design Notes
- Use `check_same_thread=False` on the SQLite engine — you'll have multiple threads
  touching the DB once Member B's concurrent fraud checks and your own debit/credit
  threads are both running.
- Don't put fraud-scoring logic here — call into `fraud-intel/` instead. Keep this
  track's responsibility strictly to: persistence, state, idempotency, simulated
  bank behavior.
