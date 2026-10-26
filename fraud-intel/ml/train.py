import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (roc_auc_score, average_precision_score, recall_score,
                             precision_score, f1_score, confusion_matrix)
from catboost import CatBoostClassifier
from ml.make_data import make_dataset

CAT = ["merchant_category", "device_type", "channel"]
df = make_dataset()
X, y = df.drop(columns="is_fraud"), df["is_fraud"]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y,
                                      random_state=0)


def report(name, proba):
    pred = (proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
    print(f"{name:19s} ROC-AUC {roc_auc_score(yte, proba):.3f}  "
          f"PR-AUC {average_precision_score(yte, proba):.3f}  "
          f"recall {recall_score(yte, pred):.2f}  precision {precision_score(yte, pred):.2f}  "
          f"F1 {f1_score(yte, pred):.2f}  TP {tp} FP {fp} FN {fn} TN {tn}")


# Baseline: logistic regression (categoricals one-hot encoded)
Xtr_oh = pd.get_dummies(Xtr, columns=CAT)
Xte_oh = pd.get_dummies(Xte, columns=CAT)
Xte_oh = Xte_oh.reindex(columns=Xtr_oh.columns, fill_value=0)
lr = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
lr.fit(Xtr_oh, ytr)

# Final: CatBoost (native categorical handling)
cb = CatBoostClassifier(iterations=200, depth=4, learning_rate=0.1,
                        auto_class_weights="Balanced", cat_features=CAT,
                        verbose=0, random_seed=0)
cb.fit(Xtr, ytr)

print("train rows", len(Xtr), "test rows", len(Xte), "test fraud", int(yte.sum()))
report("LogisticRegression", lr.predict_proba(Xte_oh)[:, 1])
report("CatBoost", cb.predict_proba(Xte)[:, 1])
imp = sorted(zip(cb.feature_names_, cb.get_feature_importance()), key=lambda t: -t[1])[:5]
print("top features:", [(n, round(float(v), 1)) for n, v in imp])
cb.save_model("fraud_model.cbm")
