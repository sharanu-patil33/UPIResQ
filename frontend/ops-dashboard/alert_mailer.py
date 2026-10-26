"""Optional: email new alerts. Do this LAST; dashboard and app alerts matter more.
With no SMTP settings it only prints what it would send (dry run).
Settings (environment): API_BASE, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM,
                        MAIL_SENDER, MAIL_RECEIVER, MAIL_OPS  (addresses for each recipient type)"""
import os
import smtplib
import time
from email.message import EmailMessage

import requests

API = os.environ.get("API_BASE", "http://localhost:8000")
ADDRESS = {"SENDER": os.environ.get("MAIL_SENDER", "sender@example.com"),
           "RECEIVER": os.environ.get("MAIL_RECEIVER", "receiver@example.com"),
           "OPS": os.environ.get("MAIL_OPS", "ops@example.com")}


def build(alert):
    msg = EmailMessage()
    msg["Subject"] = f"Payment update ({alert['transaction_id'][:8]})"
    msg["From"] = os.environ.get("MAIL_FROM", "payments@example.com")
    msg["To"] = ADDRESS[alert["recipient"]]
    msg.set_content(alert["message"])
    return msg


def deliver(msg):
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"[dry run] to {msg['To']}: {msg['Subject']} | {msg.get_content().strip()}")
        return
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


def run_once(seen):
    for a in requests.get(f"{API}/alerts", timeout=5).json():
        key = (a["transaction_id"], a["recipient"], a["at"])
        if key not in seen:
            deliver(build(a))
            seen.add(key)


if __name__ == "__main__":
    seen = set()
    while True:
        run_once(seen)
        time.sleep(5)
