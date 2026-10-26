import time
from fraud_intel.scoring import score_transaction, load_context


def make_txns(n):
    return [{"id": f"t{i}", "amount": 1000 + i, "location": "Hubballi", "hour": 14,
             "merchant_id": "m1", "device_id": "dev-1"} for i in range(n)]


def timed(concurrent, txns, ctx):
    t0 = time.time()
    for t in txns:
        score_transaction(t, ctx, concurrent=concurrent)
    return time.time() - t0


if __name__ == "__main__":
    txns = make_txns(20); ctx = load_context(None)
    seq = timed(False, txns, ctx)
    con = timed(True, txns, ctx)
    print(f"transactions: {len(txns)}")
    print(f"sequential : {seq:.2f} s  ({seq / len(txns) * 1000:.0f} ms each)")
    print(f"concurrent : {con:.2f} s  ({con / len(txns) * 1000:.0f} ms each)")
    print(f"speed-up   : {seq / con:.1f}x")
