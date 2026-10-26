import numpy as np
import pandas as pd

CATS = ["grocery", "food", "bills", "travel", "electronics", "gift_cards"]


def make_dataset(n=100000, fraud_rate=0.008, seed=42):
    """Synthetic data: decide fraud or normal first, then draw each feature from a
    different (overlapping) distribution for the two groups."""
    rng = np.random.default_rng(seed)
    fraud = rng.binomial(1, fraud_rate, n).astype(bool)
    f, g = fraud, ~fraud
    nf, ng = f.sum(), g.sum()

    def mix(fraud_draw, normal_draw):
        out = np.empty(n)
        out[f] = fraud_draw(nf)
        out[g] = normal_draw(ng)
        return out

    hour = np.empty(n, dtype=int)
    night = rng.random(nf) < 0.55                  # fraud skews to the night
    hour[f] = np.where(night, rng.integers(0, 5, nf), rng.integers(5, 24, nf))
    hour[g] = rng.choice(np.arange(24), ng, p=_day_profile())

    df = pd.DataFrame({
        "amount_ratio": mix(lambda k: rng.lognormal(0.9, 0.8, k),
                            lambda k: rng.lognormal(0, 0.5, k)),
        "hour": hour,
        "is_new_device": mix(lambda k: rng.binomial(1, 0.55, k),
                             lambda k: rng.binomial(1, 0.08, k)).astype(int),
        "is_new_receiver": mix(lambda k: rng.binomial(1, 0.75, k),
                               lambda k: rng.binomial(1, 0.22, k)).astype(int),
        "txn_count_1h": mix(lambda k: rng.poisson(2.0, k),
                            lambda k: rng.poisson(0.5, k)).astype(int),
        "failed_attempts_24h": mix(lambda k: rng.poisson(1.0, k),
                                   lambda k: rng.poisson(0.08, k)).astype(int),
        "distance_km": mix(lambda k: rng.exponential(80, k),
                           lambda k: rng.exponential(12, k)),
    })
    df["merchant_category"] = _choose(rng, f, g, CATS,
                                      [.10, .10, .05, .20, .25, .30], [.30, .25, .20, .10, .10, .05])
    df["device_type"] = _choose(rng, f, g, ["android", "ios", "web"],
                                [.55, .20, .25], [.65, .31, .04])
    df["channel"] = _choose(rng, f, g, ["qr", "app", "web"], [.15, .50, .35], [.45, .47, .08])
    df["is_fraud"] = fraud.astype(int)
    return df


def _choose(rng, f, g, values, p_fraud, p_normal):
    out = np.empty(len(f), dtype=object)
    out[f] = rng.choice(values, f.sum(), p=p_fraud)
    out[g] = rng.choice(values, g.sum(), p=p_normal)
    return out


def _day_profile():
    p = np.array([1]*5 + [2, 4, 6] + [8]*12 + [7, 6, 4, 2], dtype=float)
    return p / p.sum()


if __name__ == "__main__":
    d = make_dataset()
    print(d.shape, "fraud rate: %.2f%%" % (100 * d.is_fraud.mean()), "fraud rows:", d.is_fraud.sum())
    d.to_csv("data/synthetic_transactions.csv", index=False)
