#!/usr/bin/env bash
# Runs every test suite in the project. Run from the project root:  bash scripts/test_all.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
step() { echo; echo "=== $1 ==="; }

step "backend (Member 1)"
(cd "$ROOT/backend" && python -m pytest tests/ -q) || fail=1

step "fraud-intel (Member 2)"
(cd "$ROOT/fraud-intel" && python -m pytest tests/ -q) || fail=1

step "frontend: logic (Member 3)"
(cd "$ROOT/frontend" && node test_logic.js) || fail=1

step "frontend: end-to-end scenarios against the mock backend"
cd "$ROOT/frontend"
python -m uvicorn mock_api:app --port 8000 --log-level warning > /dev/null 2>&1 &
UV=$!
sleep 2
python -m pytest tests/ -q || fail=1
kill $UV 2>/dev/null; wait $UV 2>/dev/null

step "frontend: dashboard pages"
(cd "$ROOT/frontend" && python test_dashboard.py 2>&1 | grep -E "Dashboard test|Traceback|Error") || fail=1

echo
if [ $fail -eq 0 ]; then echo "ALL SUITES PASSED"; else echo "SOME SUITES FAILED"; fi
exit $fail
