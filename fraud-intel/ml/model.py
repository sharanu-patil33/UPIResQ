import os
import pandas as pd
from catboost import CatBoostClassifier

ORDER = ["amount_ratio", "hour", "is_new_device", "is_new_receiver", "txn_count_1h",
         "failed_attempts_24h", "distance_km", "merchant_category", "device_type", "channel"]
_model = None
HERE = os.path.dirname(__file__)


def load_model(path=os.path.join(HERE, "..", "fraud_model.cbm")):
    global _model
    if _model is None and os.path.exists(path):
        _model = CatBoostClassifier(); _model.load_model(path)
    return _model


def build_features(txn, ctx):
    return {"amount_ratio": txn["amount"] / max(ctx["usual_amount"], 1),
            "hour": txn["hour"],
            "is_new_device": int(txn.get("device_id") not in ctx["known_devices"]),
            "is_new_receiver": int(txn.get("receiver_id")
                                   not in ctx.get("known_receivers", set())),
            "txn_count_1h": ctx.get("count_1h", ctx["recent_count"]),
            "failed_attempts_24h": ctx.get("failed_attempts", 0),
            "distance_km": ctx.get("distance_km", 0.0),
            "merchant_category": ctx.get("merchant_category", "grocery"),
            "device_type": ctx.get("device_type", "android"),
            "channel": ctx.get("channel", "app")}


def ml_probability(txn, ctx):
    """Fraud probability from the model, or None if no trained model file exists."""
    model = load_model()
    if model is None:
        return None
    row = pd.DataFrame([build_features(txn, ctx)])[ORDER]
    return float(model.predict_proba(row)[0, 1])
