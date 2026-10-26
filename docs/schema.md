# Database Schema (9 tables)

customers, accounts, merchants, devices, transactions (idempotency_key UNIQUE),
transaction_events (append-only), risk_results, alerts, fraud_cases.

Reference implementation: see the SQLAlchemy models from the Phase 1 scaffold
(models.py). Member A owns the final version; changes need review from B and C.
