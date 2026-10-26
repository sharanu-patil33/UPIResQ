"""Runs the Streamlit app headlessly against the mock API and checks every page."""
import os, threading, time
import uvicorn, requests
from streamlit.testing.v1 import AppTest
import mock_api

os.environ["API_BASE"] = "http://127.0.0.1:8766"
server = uvicorn.Server(uvicorn.Config(mock_api.app, port=8766, log_level="error"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started: time.sleep(0.1)

API = os.environ["API_BASE"]
def pay(key, amt, mode="SUCCESS"):
    requests.post(API + "/sim/config", json={"sender": "SUCCESS", "receiver": mode})
    requests.post(API + "/transactions", json={"idempotency_key": key, "sender_account_id": "acc-alice",
                                               "receiver_account_id": "acc-bob", "amount": amt})
pay("a", 1000); pay("b", 500, "TIMEOUT"); pay("c", 25000); pay("d", 60000)

at = AppTest.from_file("ops-dashboard/app.py", default_timeout=30).run()
assert not at.exception, at.exception
print("Overview metrics:", {m.label: m.value for m in at.metric})
for name in ["Reconciliation queue", "Fraud cases", "Alerts", "Transaction detail", "Demo controls"]:
    at.sidebar.radio[0].set_value(name).run()
    assert not at.exception, (name, at.exception)
    print(f"{name:22s} ok | tables: {len(at.dataframe)} | warnings: {len(at.warning)} | errors: {len(at.error)}")
    assert len(at.error) == 0
at.sidebar.radio[0].set_value("Reconciliation queue").run()
assert any("Why:" in w.value for w in at.warning), "diagnosis explanation missing"
print("Reconciliation page shows the diagnosis reason:", [w.value[:60] for w in at.warning][0], "...")
at.sidebar.radio[0].set_value("Demo controls").run()
at.selectbox[1].set_value("LOST_ACK"); at.button[1].click().run() if len(at.button) > 1 else at.button[0].click().run()
print("Simulator now:", requests.post(API + "/sim/config", json={"sender": "SUCCESS", "receiver": "SUCCESS"}).json())
print("Dashboard test: all pages rendered without errors")
