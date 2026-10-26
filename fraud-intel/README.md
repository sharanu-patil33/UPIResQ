# Fraud-Intel — Fraud Checks, ML Model & Reconciliation Diagnosis (Member B)

You own the two "smart" parts of the system, and they are deliberately different
kinds of smart — don't blur them together:

- **Diagnosis (why is this transaction stuck?)** — rule-based, real-time, no
  training data. Lives in `reconciliation/`.
- **Fraud risk + recovery time (statistical questions)** — ML, trained on
  historical/synthetic data. Lives in `ml/`.

## Task Checklist

### Phase 1 — Core Skeleton
- [ ] Write the 6 fraud checks as plain, independent functions in `checks/`:
      amount, location, velocity, behavior, merchant, device. Each returns
      `(score, reason)`. Run them **sequentially** first — get the logic right
      before threading.
- [ ] Build the reconciliation decision table in `reconciliation/` as a plain
      function: given signals (debit confirmed? credit confirmed? timed out?
      retry count?), return the likely reason + next action. Table-driven, not a
      pile of if/else — this needs to be presentable as an actual decision table
      in the report.
- [ ] Agree the function signatures with Member A so they can call into these
      directly (or via an internal API — decide which, as a team, in Phase 0).

### Phase 2 — Happy Path
- [ ] Backend calls your check functions per transaction and gets back real
      scores; confirm end to end with Member A using real transaction data, not
      your own test stubs.

### Phase 3 — The Real Contribution
- [ ] Swap the 6 sequential fraud checks for a shared `ThreadPoolExecutor`:
      `executor.submit(fn, txn)` per check, collect with `as_completed()`.
      **Benchmark it** — run the same batch sequential vs concurrent, record both
      timings. This comparison is your concurrency proof for the viva; don't skip it.
- [ ] Log thread name + start/end time per check into `risk_results` (coordinate
      the exact fields with Member A's schema).
- [ ] Generate (or source) a synthetic fraud dataset — categorical + imbalanced,
      matching real UPI data shape (see `data/README.md` for the schema to use).
      Train CatBoost as the fraud model; evaluate with ROC-AUC and recall, not
      plain accuracy, given the class imbalance.
- [ ] Build the recovery-time estimator: bucket your own simulator's past stuck
      transactions by failure type, compute average/median time-to-resolution per
      bucket. Start simple (bucketed medians) before reaching for a regression model.

### Phase 4 — Integration Hardening
- [ ] Confirm the reconciliation engine's output format matches exactly what
      Frontend's ops dashboard expects (reason, severity, recommended action —
      agree the exact field names).
- [ ] Re-run the sequential-vs-concurrent benchmark on the final checks (not the
      Phase 3 draft version) and save the numbers for the report.

## Key Design Notes
- Keep `reconciliation/` free of ML entirely. If you're tempted to add a model
  there, that's a sign it belongs in `ml/` instead — the diagnosis engine's whole
  value is being instant and explainable with zero training data.
- Weights for the fraud-check aggregation (`checks/`) should sum to 1.0 and live
  in one place, not scattered across functions — makes it easy to tune and to
  explain in the report.
