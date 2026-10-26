// Pure helper functions: no page access, so they are easy to test with Node.
const FINAL_STATES = ["COMPLETED", "FAILED", "RECONCILIATION_REQUIRED"];
const STUCK_STATES = ["TIMEOUT", "RECONCILIATION_REQUIRED"];

function isFinal(state) {
  return FINAL_STATES.includes(state);
}

function isStuck(state) {
  return STUCK_STATES.includes(state);
}

// The screen decides how a state LOOKS. What a state MEANS comes from the backend.
function describeState(state) {
  const map = {
    COMPLETED: { title: "Payment completed", tone: "ok" },
    FAILED: { title: "Payment failed", tone: "bad" },
    RECONCILIATION_REQUIRED: { title: "Payment under review", tone: "warn" },
    TIMEOUT: { title: "Checking your payment", tone: "warn" },
  };
  return map[state] || { title: "Payment in progress", tone: "info" };
}

function makeKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "key-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}

function formatMoney(n) {
  return "Rs. " + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function validateAmount(text) {
  const n = Number(text);
  if (!text || Number.isNaN(n) || n <= 0) return "Enter an amount above zero";
  return null;
}

if (typeof module !== "undefined") {
  module.exports = { isFinal, isStuck, describeState, makeKey, formatMoney, validateAmount };
}
