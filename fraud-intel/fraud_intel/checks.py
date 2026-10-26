import time
import threading

# Simulated latency (seconds) of the lookup each check makes, e.g. a device
# reputation service or a geo lookup. This waiting is what threads overlap.
LATENCY = {"amount": 0.05, "location": 0.15, "velocity": 0.10,
           "behavior": 0.20, "merchant": 0.08, "device": 0.12}


def _lookup(name):
    time.sleep(LATENCY[name])


def _result(name, score, reason, t0):
    return {"check": name, "score": score, "reason": reason,
            "thread": threading.current_thread().name,
            "start": t0, "end": time.time()}


def check_amount(txn, ctx):
    t0 = time.time(); _lookup("amount")
    ratio = txn["amount"] / max(ctx["usual_amount"], 1)
    if ratio <= 1.5:
        return _result("amount", 0, "Amount close to usual", t0)
    if ratio <= 3:
        return _result("amount", 40, f"{ratio:.1f}x the usual amount", t0)
    return _result("amount", 90, f"{ratio:.1f}x the usual amount, highly unusual", t0)


def check_location(txn, ctx):
    t0 = time.time(); _lookup("location")
    if not txn.get("location") or not ctx.get("home_location"):
        return _result("location", 20, "Not enough location data", t0)
    if txn["location"] == ctx["home_location"]:
        return _result("location", 0, "Matches home location", t0)
    return _result("location", 70, f"New location {txn['location']}", t0)


def check_velocity(txn, ctx):
    t0 = time.time(); _lookup("velocity")
    n = ctx["recent_count"]                      # transactions in last 10 minutes
    if n <= 2:
        return _result("velocity", 0, f"{n} recent transactions, normal", t0)
    if n <= 5:
        return _result("velocity", 50, f"{n} transactions in 10 min, elevated", t0)
    return _result("velocity", 85, f"{n} transactions in 10 min, very high", t0)


def check_behavior(txn, ctx):
    t0 = time.time(); _lookup("behavior")
    start, end = ctx["typical_hours"]
    odd_hour = not (start <= txn["hour"] <= end)
    big = txn["amount"] > 2 * ctx["usual_amount"]
    if odd_hour and big:
        return _result("behavior", 80, "Unusual hour and unusual amount", t0)
    if odd_hour or big:
        return _result("behavior", 40, "Unusual hour or amount", t0)
    return _result("behavior", 0, "Fits the usual pattern", t0)


def check_merchant(txn, ctx):
    t0 = time.time(); _lookup("merchant")
    if not txn.get("merchant_id"):
        return _result("merchant", 0, "Person-to-person transfer", t0)
    risk = ctx["merchant_risk"]
    return _result("merchant", risk, f"Merchant risk level {risk}", t0)


def check_device(txn, ctx):
    t0 = time.time(); _lookup("device")
    if not txn.get("device_id"):
        return _result("device", 40, "No device information", t0)
    if txn["device_id"] in ctx["known_devices"]:
        return _result("device", 0, "Recognised device", t0)
    return _result("device", 55, "New or unrecognised device", t0)


CHECKS = {"amount": check_amount, "location": check_location,
          "velocity": check_velocity, "behavior": check_behavior,
          "merchant": check_merchant, "device": check_device}
