from collections import defaultdict
from statistics import median, quantiles

MIN_SAMPLES = 5


def build_table(history):
    """history: list of {"reason": str, "minutes": float} from past stuck cases."""
    groups = defaultdict(list)
    for h in history:
        groups[h["reason"]].append(h["minutes"])
    table = {}
    for reason, mins in groups.items():
        if len(mins) >= 2:
            q = quantiles(mins, n=4)              # [p25, p50, p75]
            low, high = q[0], q[2]
        else:
            low = high = mins[0]
        table[reason] = {"median": median(mins), "low": low, "high": high, "n": len(mins)}
    return table


def estimate(reason, table):
    row = table.get(reason)
    if row is None or row["n"] < MIN_SAMPLES:
        return {"minutes": None, "confidence": "LOW",
                "message": "Not enough similar cases yet. We will update you when we know."}
    mid, low, high = round(row["median"]), round(row["low"]), round(row["high"])
    return {"minutes": mid, "range": (low, high), "confidence": "NORMAL", "based_on": row["n"],
            "message": f"Cases like this are usually resolved in about {mid} minutes "
                       f"(typically {low} to {high}). This is an estimate, not a guarantee."}
