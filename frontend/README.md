# Frontend — UPI App, Ops Dashboard & Integration (Member C)

You own everything a human looks at, plus the job of proving the whole system works
together. Two separate UIs, two separate audiences:

- `upi-app/` — what a **customer** sees: send money, track a payment, view history.
- `ops-dashboard/` — what the **operations team** sees: suspicious transactions,
  reconciliation queue, alerts, logs.

## Task Checklist

### Phase 1 — Core Skeleton
- [ ] `upi-app/`: static screens for Send Money, Transaction Status, Payment History.
      Use mock JSON for now — do not wait for the backend.
- [ ] `ops-dashboard/` (Streamlit): empty layout with KPI cards (approved / review /
      blocked / reconciliation cases / duplicates) and a transactions table.

### Phase 2 — Happy Path
- [ ] Point `upi-app/` at the real `POST /transactions` and `GET /transactions/{id}`.
      A payment sent from the UI must produce a real decision from the backend.
- [ ] Show the live state of a payment (e.g. DEBITED → CREDIT_PENDING → CREDITED),
      polling or WebSocket, your choice — agree with Member A.

### Phase 3 — The Real Contribution
- [ ] Alert banners in `upi-app/` for stuck cases: plain-language message, a
      "don't retry" warning, and the estimated recovery time from Member B.
- [ ] `ops-dashboard/`: reconciliation queue page, fraud cases page, alerts page,
      per-transaction detail page showing risk breakdown + payment timeline +
      **why** it was flagged (the diagnosis reason, not just the label).
- [ ] Alert delivery: dashboard alerts first; email (smtplib) last — least important
      for grading.

### Phase 4 — Integration Hardening (your main job here)
- [ ] Own `docs/test-scenarios.md`: run all 10 scenarios end to end through the UI,
      record pass/fail and screenshots.
- [ ] File issues (GitHub Issues) against Member A / Member B for anything that breaks
      the agreed API contract.

## Key Design Notes
- Never hardcode transaction logic in the UI. If the UI is deciding what a state
  means, that logic belongs in the backend.
- The ops dashboard should explain, not just display: every flagged row needs a
  visible reason.

---

## Starter code in this folder (tested reference)

    pip install -r requirements.txt
    uvicorn mock_api:app --port 8000                  # mock backend (or the real backend on the same port)
    cd upi-app && python -m http.server 5500          # open http://localhost:5500
    cd ops-dashboard && streamlit run app.py          # operations dashboard

Tests:

    pytest tests/ -v                                  # 10 end-to-end scenarios (backend on :8000)
    node test_logic.js                                # pure UI logic
    npm install && node test_ui.js                    # app page in a simulated browser (mock on :8765)
    python test_dashboard.py                          # dashboard pages, headless

Point the app at another backend by editing `upi-app/config.js`; set `API_BASE` for the dashboard and tests.
The real backend must enable CORS and provide `GET /transactions` and `GET /accounts/{id}` (see docs/architecture.md).
