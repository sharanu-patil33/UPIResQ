# End-to-End Test Scenarios (Member C owns results)

| # | Scenario | Expected outcome | Pass/Fail |
|---|----------|------------------|-----------|
| 1 | Normal successful payment | COMPLETED, APPROVE | |
| 2 | Debit succeeds, credit fails | RECONCILIATION_REQUIRED, alerts sent | |
| 3 | Debit succeeds, receiver times out | TIMEOUT -> status check -> reconcile | |
| 4 | Credit succeeds, confirmation lost | Detected, resolved to COMPLETED | |
| 5 | Debit fails | FAILED, user told nothing was deducted | |
| 6 | Invalid receiver | FAILED early | |
| 7 | Insufficient balance | FAILED early | |
| 8 | Duplicate request (same idempotency_key) | Existing txn returned, no double debit | |
| 9 | Concurrent duplicate requests | Exactly one transaction created | |
| 10 | High-risk transaction | BLOCK/REVIEW with visible reason | |
