# UPI Payment Failure Diagnosis, Reconciliation and Fraud Risk Monitoring System

A simulated UPI-style payment platform for a college mini project. It looks like a normal payment app
(send money, track a payment, see history). Two features sit underneath:

1. **Fraud-risk detection:** six fraud checks run at the same time in a thread pool, plus a trained model,
   and decide Approve / Review / Block.
2. **Failure diagnosis and reconciliation:** when money is debited but the receiver is not credited, a payment
   state machine and a rule-based decision table explain why it is stuck, what to do next, and roughly
   when it will resolve. Duplicate payments are blocked with idempotency keys.

An operations dashboard shows suspicious payments, the reconciliation queue, alerts and logs.

> This is a simulation. Sender bank, receiver bank and gateway are simulated. It is not real UPI, and no real
> bank or NPCI data is used. Fraud data is synthetic, so model scores demonstrate the method, not real-world accuracy.

## Team and tracks

| Track | Folder | Owner | Builds |
|---|---|---|---|
| Payment core | `backend/` | Member 1 | Database, payment APIs, state machine, idempotency, bank simulators |
| Fraud and diagnosis | `fraud-intel/` | Member 2 | Six threaded fraud checks, fraud model, diagnosis table, recovery-time estimate |
| UI and operations | `frontend/` | Member 3 | UPI app, ops dashboard, alerts, end-to-end tests |
| Guide | n/a | Guide | Reviews, phase sign-offs, demo and viva readiness |

Each folder has a `README.md` with that member's phase-by-phase checklist. Detailed work assignments are PDFs in
`docs/reports/`.

## Repository layout

    backend/        FastAPI backend pieces: models, simulators, state machine, idempotent create
    fraud-intel/    fraud checks + thread pool, diagnosis rules, recovery estimate, ML training
    frontend/       UPI app (HTML/JS), Streamlit ops dashboard, mock backend, end-to-end tests
    docs/           architecture, schema, test scenarios, reports (PDF/Word), diagrams
    scripts/        test_all.sh runs every test suite
    .github/        pull request and issue templates

## Current status

What exists and is tested:
- **backend/**: tables, bank simulators (SUCCESS, ERROR, TIMEOUT, LOST_ACK), state machine, idempotent create,
  payment flow. 11 tests pass, including 20 threads sending the same key creating one row.
- **fraud-intel/**: six checks, thread pool, scoring, 12-rule diagnosis table, recovery estimator, synthetic
  data and model training. 19 tests pass. Concurrent run is about 3.5x faster than sequential in the reference benchmark.
- **frontend/**: UPI app, ops dashboard, mock backend, 10 end-to-end scenarios. All pass against the **mock** backend.

Still to do (the team's work):
- **Member 1:** wrap the service in FastAPI endpoints (`POST /transactions`, `GET /payment-status/{id}`, and the rest of the
  contract in `docs/architecture.md`), plus the extra endpoints Member 3 needs and CORS.
- **Integration:** call `fraud-intel` from the backend (fraud score before debit, diagnosis and recovery when stuck), then run
  `frontend/tests` against the real backend instead of the mock.

## Quick start

    git clone <your-repo-url>
    cd upi-fraud-diagnosis-mini-project

    pip install -r backend/requirements.txt -r fraud-intel/requirements.txt -r frontend/requirements.txt
    bash scripts/test_all.sh                           # runs every test suite

Run each part (see the folder READMEs for details):

    cd frontend && uvicorn mock_api:app --port 8000     # mock backend (replace with the real one later)
    cd frontend/upi-app && python -m http.server 5500   # UPI app at http://localhost:5500
    cd frontend/ops-dashboard && streamlit run app.py   # operations dashboard

Train the fraud model (optional; without it scoring uses the rules only):

    cd fraud-intel && python -m ml.make_data && python -m ml.train

## Git workflow

- `main`: always demo-ready. Nobody commits directly.
- `dev`: integration branch. Everyone merges here by pull request.
- `feature/<member>-<task>`: for example `feature/member1-idempotency`.
- Every pull request needs a review from a different member. The guide merges `dev` into `main` at phase checkpoints.
- Changes to the API contract or schema need all three members' agreement. See `CONTRIBUTING.md`.

## Documentation

- `docs/architecture.md`: system design, state machine, API contract
- `docs/schema.md`: database tables
- `docs/test-scenarios.md`: the 10 end-to-end scenarios and results
- `docs/reports/`: project report, member work assignments, related work, requirements, explanations
