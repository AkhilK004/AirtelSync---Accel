"""Train propensity model (source of truth). Usage: cd api && python -m uv run python ../scripts/train_propensity.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from app.data.loaders import get_data
from app.leads.features import CATEGORICAL, FEATURES, NUMERIC, build_features

OUT = Path("../data/derived"); OUT.mkdir(parents=True, exist_ok=True)
L = get_data().leads
X, y = build_features(L), L["activated"].astype(int)
# time-based split: train Apr-May, test Jun
train = L.created_date < "2026-06-01"; test = ~train
pre = lambda: ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL), ("num", StandardScaler(), NUMERIC)])
def make(kind):
    clf = LogisticRegression(class_weight="balanced", max_iter=2000, C=0.3) if kind == "lr" else HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, random_state=0)
    return Pipeline([("pre", pre()), ("clf", clf)])

def lift(y_true, p, q=0.1):
    k = max(1, int(len(p) * q)); idx = np.argsort(-p)[:k]
    return float(y_true.iloc[idx].mean() / y_true.mean())

metrics = {"n_train": int(train.sum()), "n_test": int(test.sum()), "base_rate_test": float(y[test].mean())}
for kind in ("lr", "hgb"):
    m = make(kind).fit(X[train], y[train]); p = m.predict_proba(X[test])[:, 1]
    metrics[kind] = {"auc": round(roc_auc_score(y[test], p), 4), "top_decile_lift": round(lift(y[test], p), 2),
                     "top_decile_rate": round(float(y[test].iloc[np.argsort(-p)[:max(1, len(p)//10)]].mean()), 4)}
    if kind == "lr":
        pi = float(y[train].mean()); p = 1 / (1 + np.exp(-(np.log(p / (1 - p)) - np.log((1 - pi) / pi))))  # prior-shift undo of class_weight=balanced
        cal = pd.DataFrame({"p": p, "y": y[test].values}); cal["bin"] = pd.qcut(cal.p, 5, duplicates="drop")
        metrics["lr_calibration_quintiles"] = cal.groupby("bin", observed=True).agg(pred_mean=("p", "mean"), actual=("y", "mean")).round(3).reset_index(drop=True).to_dict("records")
# final model: refit on all data
final = make("lr").fit(X, y)
joblib.dump({"pipeline": final, "features": FEATURES, "metrics": metrics, "prior": float(y.mean())}, OUT / "propensity.joblib")
json.dump({"categorical": CATEGORICAL, "numeric": NUMERIC, "target": "activated", "split": "train created<2026-06-01, test June"}, open(OUT / "feature_schema.json", "w"), indent=2)
json.dump(metrics, open(OUT / "propensity_metrics.json", "w"), indent=2)
print(json.dumps(metrics, indent=2))
