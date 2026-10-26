import time

CONFIG = {"sender": "SUCCESS", "receiver": "SUCCESS", "delay": 0.1, "timeout": 0.5}
_credited = set()          # transaction ids the receiver bank really credited


def debit(txn_id, account_id, amount):
    mode = CONFIG["sender"]
    if mode == "ERROR":
        return {"status": "ERROR", "code": "DEBIT_FAILED"}
    if mode == "TIMEOUT":
        time.sleep(CONFIG["timeout"])
        return {"status": "TIMEOUT", "code": "NO_RESPONSE"}
    time.sleep(CONFIG["delay"])
    return {"status": "OK", "code": "00"}


def credit(txn_id, account_id, amount):
    mode = CONFIG["receiver"]
    if mode == "ERROR":
        return {"status": "ERROR", "code": "CREDIT_FAILED"}
    if mode == "TIMEOUT":                      # never applied, caller gives up
        time.sleep(CONFIG["timeout"])
        return {"status": "TIMEOUT", "code": "NO_RESPONSE"}
    if mode == "LOST_ACK":                     # applied, but confirmation lost
        _credited.add(txn_id)
        time.sleep(CONFIG["timeout"])
        return {"status": "TIMEOUT", "code": "NO_RESPONSE"}
    time.sleep(CONFIG["delay"])                # SUCCESS
    _credited.add(txn_id)
    return {"status": "OK", "code": "00"}


def status_check(txn_id):
    return {"credited": txn_id in _credited}
