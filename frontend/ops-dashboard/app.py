import os
import pandas as pd
import requests
import streamlit as st

API = os.environ.get("API_BASE", "http://localhost:8000")
st.set_page_config(page_title="Payments Operations", layout="wide")


def call(method, path, **kw):
    """Call the backend. Show a clear message instead of crashing if it is down."""
    try:
        r = requests.request(method, API + path, timeout=5, **kw)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend problem on {path}: {e}")
        return None


def short(i):
    return i[:8]


def transaction_table(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["id"] = df["id"].map(short)
    return df[["id", "created_at", "sender", "receiver", "amount", "state", "decision", "score"]]


def explain(tid):
    """Why was this payment flagged? Risk breakdown, diagnosis, timeline, alerts."""
    status = call("GET", f"/payment-status/{tid}")
    risk = call("GET", f"/risk/{tid}")
    if status:
        st.subheader(f"State: {status['state']}")
        diag = status.get("diagnosis")
        if diag:
            st.warning(f"**Why:** {diag['reason']}  |  **Severity:** {diag['severity']}  |  "
                       f"**Action:** {diag['action']}")
        if status.get("recovery"):
            st.info(status["recovery"]["message"])
        st.write("Payment timeline")
        st.dataframe(pd.DataFrame(status["timeline"]))
    if risk:
        st.write(f"Fraud decision: **{risk['decision']}** (score {risk['score']})")
        checks = pd.DataFrame(risk["checks"])
        st.dataframe(checks)
        st.bar_chart(checks.set_index("check")["score"])
    alerts = [a for a in (call("GET", "/alerts") or []) if a["transaction_id"] == tid]
    if alerts:
        st.write("Alerts sent")
        st.dataframe(pd.DataFrame(alerts))


def pick(rows, label):
    if not rows:
        st.write("Nothing to show.")
        return None
    labels = {f"{short(r['id'])}  {r['state']}  Rs. {r['amount']}": r["id"] for r in rows}
    return labels[st.selectbox(label, list(labels))]


page = st.sidebar.radio("Page", ["Overview", "Reconciliation queue", "Fraud cases",
                                 "Alerts", "Transaction detail", "Demo controls"])
if st.sidebar.button("Refresh"):
    st.rerun()

txns = call("GET", "/transactions") or []

if page == "Overview":
    st.title("Payments overview")
    count = lambda s: sum(1 for t in txns if t["state"] == s)
    cols = st.columns(5)
    cols[0].metric("Total", len(txns))
    cols[1].metric("Completed", count("COMPLETED"))
    cols[2].metric("Failed", count("FAILED"))
    cols[3].metric("Need reconciliation", count("RECONCILIATION_REQUIRED") + count("TIMEOUT"))
    flagged = sum(1 for t in txns if t["decision"] in ("REVIEW", "BLOCK"))
    cols[4].metric("Review or blocked", flagged)
    st.dataframe(transaction_table(txns))

elif page == "Reconciliation queue":
    st.title("Reconciliation queue")
    stuck = [t for t in txns if t["state"] in ("RECONCILIATION_REQUIRED", "TIMEOUT")]
    st.write(f"{len(stuck)} payment(s) need attention")
    chosen = pick(stuck, "Open a case")
    if chosen:
        explain(chosen)

elif page == "Fraud cases":
    st.title("Fraud cases")
    cases = call("GET", "/cases") or []
    st.dataframe(pd.DataFrame(cases))
    chosen = pick([t for t in txns if t["decision"] in ("REVIEW", "BLOCK")], "Open a case")
    if chosen:
        explain(chosen)

elif page == "Alerts":
    st.title("Alerts")
    alerts = call("GET", "/alerts") or []
    who = st.selectbox("Recipient", ["ALL", "SENDER", "RECEIVER", "OPS"])
    shown = [a for a in alerts if who == "ALL" or a["recipient"] == who]
    st.dataframe(pd.DataFrame(shown))

elif page == "Transaction detail":
    st.title("Transaction detail")
    chosen = pick(txns, "Choose a transaction")
    if chosen:
        explain(chosen)

else:
    st.title("Demo controls")
    st.write("Switch how the simulated banks behave. The next payment will follow these settings.")
    modes = ["SUCCESS", "ERROR", "TIMEOUT", "LOST_ACK"]
    sender = st.selectbox("Sender bank", modes[:3])
    receiver = st.selectbox("Receiver bank", modes)
    if st.button("Apply"):
        out = call("POST", "/sim/config", json={"sender": sender, "receiver": receiver})
        if out:
            st.success(f"Now: sender {out['sender']}, receiver {out['receiver']}")
