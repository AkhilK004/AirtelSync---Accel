"""Train + evaluate the propensity model (source of truth). Usage: cd api && python -m uv run python ../scripts/train_propensity.py

Evaluation protocol (docs/model_card.md):
  1. Nested CV: outer 5x5 repeated stratified folds; inner 5-fold grid search picks C. Reports AUC, PR-AUC, top-decile lift,
     train-vs-validation gap (overfitting check).
  2. Paired comparison against the previous (v1) feature spec on identical folds.
  3. Time holdout: train Apr-May, test June, with bootstrap 95% CI and calibration (Brier, log-loss, decile ECE).
  4. Sanity: shuffled-label AUC must be ~0.5 (no leakage through the pipeline); learning curve (under-fitting check).
  5. Final model: refit on all rows with the C chosen by grid search on all rows.
Quality gates live in api/tests/test_propensity.py.
"""
import json, sys, time, warnings
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, ".")
warnings.filterwarnings("ignore", category=UserWarning)
import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GridSearchCV, RepeatedStratifiedKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from app.data.loaders import get_data
from app.leads.features import CATEGORICAL, FEATURES, NUMERIC, build_features

MODEL_VERSION = "propensity-v3"
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0]
MIN_CATEGORY_COUNT = 20     # rarer categories are pooled so they cannot get their own noisy weight
SEED = 42
OUT = Path("../data/derived"); OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()

L = get_data().leads
X, y = build_features(L), L["activated"].astype(int).to_numpy()
train_t = (L.created_date < "2026-06-01").to_numpy()   # time split: Apr-May train, June test


def make(cat=CATEGORICAL, num=NUMERIC, C=0.1, kind="lr"):
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=MIN_CATEGORY_COUNT, sparse_output=False), cat),
                             ("num", StandardScaler(), num)])
    clf = (LogisticRegression(class_weight="balanced", C=C, max_iter=3000) if kind == "lr" else
           HistGradientBoostingClassifier(max_depth=2, learning_rate=0.03, max_iter=300, min_samples_leaf=80, l2_regularization=1.0, random_state=0))
    return Pipeline([("pre", pre), ("clf", clf)])


def tuned():
    return GridSearchCV(make(), {"clf__C": C_GRID}, scoring="roc_auc", cv=StratifiedKFold(5, shuffle=True, random_state=SEED))


def lift(yt, p, q=0.1):
    k = max(1, int(len(p) * q)); return float(yt[np.argsort(-p)[:k]].mean() / yt.mean())


def prior_shift(p, pi):
    """Undo class_weight='balanced' (which trains as if the prior were 0.5) so probabilities match the real base rate pi."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return 1 / (1 + np.exp(-(np.log(p / (1 - p)) - np.log((1 - pi) / pi))))


def ece(yt, p, bins=10):
    q = pd.qcut(p, bins, labels=False, duplicates="drop")
    return float(sum(abs(p[q == k].mean() - yt[q == k].mean()) * np.mean(q == k) for k in np.unique(q)))


# v1 spec (shipped before), for the paired comparison
_v1 = L.assign(_n=L.products_of_interest.fillna("").map(lambda s: len([p for p in s.split(";") if p])))
X_v1 = pd.DataFrame({"segment": L.segment, "business_type": L.business_type, "city_tier_c": L.city_tier.astype(str), "lead_source": L.lead_source,
                     "preferred_language": L.preferred_language, "current_internet": L.current_internet.fillna("Unknown"),
                     "annual_turnover_band": L.annual_turnover_band, "has_gstin_c": np.where(L.has_gstin, "Y", "N"), "has_udyam_c": np.where(L.has_udyam, "Y", "N"),
                     "employee_count_log": np.log1p(L.employee_count), "num_sites": L.num_sites, "telecom_spend_log": np.log1p(L.monthly_telecom_spend_inr),
                     "n_interest": _v1._n})
V1_CAT = ["segment", "business_type", "city_tier_c", "lead_source", "preferred_language", "current_internet", "annual_turnover_band", "has_gstin_c", "has_udyam_c"]
V1_NUM = ["employee_count_log", "num_sites", "telecom_spend_log", "n_interest"]
make_v1 = lambda: Pipeline([("pre", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), V1_CAT), ("num", StandardScaler(), V1_NUM)])),
                            ("clf", LogisticRegression(class_weight="balanced", max_iter=2000, C=0.3))])

# ---------------------------------------------------------------- 1+2. nested repeated CV, paired vs v1
outer = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=SEED)
rows, chosen_C = [], []
oof_sum, oof_n = np.zeros(len(y)), np.zeros(len(y))   # out-of-fold predictions averaged over repeats -> gain chart
for tr, te in outer.split(X, y):
    g = tuned().fit(X.iloc[tr], y[tr]); chosen_C.append(g.best_params_["clf__C"])
    p, pt = g.predict_proba(X.iloc[te])[:, 1], g.predict_proba(X.iloc[tr])[:, 1]
    p1 = make_v1().fit(X_v1.iloc[tr], y[tr]).predict_proba(X_v1.iloc[te])[:, 1]
    oof_sum[te] += p; oof_n[te] += 1
    rows.append({"auc": roc_auc_score(y[te], p), "train_auc": roc_auc_score(y[tr], pt), "pr_auc": average_precision_score(y[te], p),
                 "lift": lift(y[te], p), "auc_v1": roc_auc_score(y[te], p1)})
R = pd.DataFrame(rows)
d = R.auc - R.auc_v1
cv = {"folds": len(R), "auc_mean": round(R.auc.mean(), 4), "auc_sd": round(R.auc.std(), 4), "train_auc_mean": round(R.train_auc.mean(), 4),
      "overfit_gap": round((R.train_auc - R.auc).mean(), 4), "pr_auc_mean": round(R.pr_auc.mean(), 4), "top_decile_lift_mean": round(R.lift.mean(), 2),
      "base_rate": round(float(y.mean()), 4), "chosen_C_counts": {str(c): chosen_C.count(c) for c in sorted(set(chosen_C))}}
paired = {"v1_auc_mean": round(R.auc_v1.mean(), 4), "delta_auc_mean": round(d.mean(), 4), "delta_auc_sd": round(d.std(), 4),
          "share_folds_v2_better": round(float((d > 0).mean()), 3)}



def gains(yt, p, queue_sizes=(0.1, 0.2, 0.3, 0.5)):
    """Call-centre view: calling the top q of leads captures what share of all activations, and how many activations per 100 calls."""
    o = np.argsort(-p); out = {}
    for q in queue_sizes:
        k = max(1, int(len(p) * q)); hit = float(yt[o[:k]].sum())
        out[f"top_{int(q * 100)}pct"] = {"calls_per_1000_leads": k * 1000 // len(p), "share_of_activations": round(hit / yt.sum(), 3),
                                          "activations_per_100_calls": round(100 * hit / k, 1), "lift_vs_random_calls": round((hit / k) / yt.mean(), 2)}
    return out


gains_cv = gains(y, oof_sum / oof_n)

# HGB comparison (record only; the shipped model stays linear for explainable reasons)
hgb = [roc_auc_score(y[te], make(kind="hgb").fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1])
       for tr, te in RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=SEED).split(X, y)]

# ---------------------------------------------------------------- 3. time holdout + bootstrap CI + calibration
g_t = tuned().fit(X[train_t], y[train_t]); C_t = g_t.best_params_["clf__C"]
yt = y[~train_t]; pi_t = float(y[train_t].mean())
raw_t = g_t.predict_proba(X[~train_t])[:, 1]; p_t = prior_shift(raw_t, pi_t)
p_t1 = make_v1().fit(X_v1[train_t], y[train_t]).predict_proba(X_v1[~train_t])[:, 1]
rng = np.random.default_rng(SEED); bs, bsd = [], []
for _ in range(2000):
    i = rng.integers(0, len(yt), len(yt))
    if 0 < yt[i].sum() < len(i):
        a = roc_auc_score(yt[i], p_t[i]); bs.append(a); bsd.append(a - roc_auc_score(yt[i], p_t1[i]))
cal = pd.DataFrame({"p": p_t, "y": yt}); cal["bin"] = pd.qcut(cal.p, 5, duplicates="drop")
time_holdout = {"n_train": int(train_t.sum()), "n_test": int((~train_t).sum()), "base_rate_test": round(float(yt.mean()), 4), "C": C_t,
                "auc": round(roc_auc_score(yt, p_t), 4), "auc_ci95": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
                "v1_auc": round(roc_auc_score(yt, p_t1), 4), "delta_vs_v1": round(roc_auc_score(yt, p_t) - roc_auc_score(yt, p_t1), 4),
                "delta_vs_v1_ci95": [round(float(np.percentile(bsd, 2.5)), 4), round(float(np.percentile(bsd, 97.5)), 4)],
                "top_decile_lift": round(lift(yt, p_t), 2), "top_decile_rate": round(float(yt[np.argsort(-p_t)[:len(yt) // 10]].mean()), 4),
                "pr_auc": round(average_precision_score(yt, p_t), 4),
                "brier": round(brier_score_loss(yt, p_t), 4), "brier_base_rate_only": round(brier_score_loss(yt, np.full(len(yt), pi_t)), 4),
                "log_loss": round(log_loss(yt, p_t), 4), "ece_decile": round(ece(yt, p_t), 4),
                "calibration_quintiles": cal.groupby("bin", observed=True).agg(pred_mean=("p", "mean"), actual=("y", "mean")).round(3).reset_index(drop=True).to_dict("records")}

time_holdout["gains"] = gains(yt, p_t)

# ---------------------------------------------------------------- 4. sanity: shuffled labels, learning curve
ys = np.random.default_rng(SEED).permutation(y)
shuffled_auc = round(roc_auc_score(ys[~train_t], make(C=C_t).fit(X[train_t], ys[train_t]).predict_proba(X[~train_t])[:, 1]), 4)
curve = []
for frac in (0.25, 0.5, 0.75, 1.0):
    a = []
    for tr, te in RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=SEED).split(X, y):
        tr = np.random.default_rng(SEED).choice(tr, int(len(tr) * frac), replace=False)
        a.append(roc_auc_score(y[te], make(C=C_t).fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1]))
    curve.append({"n_train": int(len(y) * 0.8 * frac), "cv_auc": round(float(np.mean(a)), 4)})

# ---------------------------------------------------------------- 4b. stage-aware models (A64)
# P(activate | lead already reached funnel stage k), k = 1 Contacted .. 4 KYC complete. Same 8 features, rows that reached k only,
# no class weights (probabilities are natively calibrated), C tuned on log-loss. Compared per stage with the all-leads model on the same rows.
STAGES = {1: "Contacted", 2: "Needs assessed", 3: "Quote accepted", 4: "KYC complete"}
rank = L.stage_reached.map({n: i for i, n in enumerate(["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"])}).to_numpy()
make_stage = lambda C=0.1: Pipeline([("pre", make().named_steps["pre"]), ("clf", LogisticRegression(C=C, max_iter=3000))])
tuned_stage = lambda: GridSearchCV(make_stage(), {"clf__C": C_GRID}, scoring="neg_log_loss", cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
stage_metrics, stage_final = {}, {}
for k, name in STAGES.items():
    idx = np.where(rank >= k)[0]; yk = y[idx]; Xk = X.iloc[idx]
    rs = []
    for tr, te in RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=SEED).split(Xk, yk):
        g = tuned_stage().fit(Xk.iloc[tr], yk[tr]); ps = g.predict_proba(Xk.iloc[te])[:, 1]
        train_all = np.setdiff1d(np.arange(len(y)), idx[te])            # all-leads model: every lead except this test fold (as in production)
        gl = make().fit(X.iloc[train_all], y[train_all])
        pg = prior_shift(gl.predict_proba(Xk.iloc[te])[:, 1], float(y.mean()))   # exactly what v2 would output for these leads
        rs.append({"auc": roc_auc_score(yk[te], ps), "auc_global": roc_auc_score(yk[te], pg), "brier": brier_score_loss(yk[te], ps),
                   "brier_global": brier_score_loss(yk[te], pg), "brier_base": brier_score_loss(yk[te], np.full(len(te), yk[tr].mean())),
                   "ece": ece(yk[te], ps, bins=5), "ece_global": ece(yk[te], pg, bins=5)})
    R2 = pd.DataFrame(rs).mean()
    gk = tuned_stage().fit(Xk, yk); stage_final[str(k)] = gk.best_estimator_
    stage_metrics[str(k)] = {"stage": name, "n": int(len(idx)), "base_rate": round(float(yk.mean()), 4), "C": gk.best_params_["clf__C"],
                             **{c: round(float(R2[c]), 4) for c in R2.index}}

# ---------------------------------------------------------------- 5. final model on all rows
g_all = tuned().fit(X, y); C_final = g_all.best_params_["clf__C"]
final = g_all.best_estimator_
metrics = {"model_version": MODEL_VERSION, "features": FEATURES, "C_final": C_final, "nested_cv": cv, "paired_vs_v1": paired,
           "hgb_cv_auc_mean": round(float(np.mean(hgb)), 4), "stage_models": stage_metrics, "gains_cv_oof": gains_cv, "time_holdout": time_holdout, "shuffled_label_auc": shuffled_auc, "learning_curve": curve,
           "calibration_method": "class_weight=balanced + analytic prior shift to the training base rate"}
trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
joblib.dump({"pipeline": final, "features": FEATURES, "metrics": metrics, "prior": float(y.mean()), "model_version": MODEL_VERSION,
             "trained_at": trained_at, "n_rows": int(len(y)), "stage_pipelines": stage_final}, OUT / "propensity.joblib")
json.dump({"model_version": MODEL_VERSION, "categorical": CATEGORICAL, "numeric": NUMERIC, "target": "activated", "C": C_final,
           "min_category_count": MIN_CATEGORY_COUNT, "split": "nested 5x5 repeated CV + time holdout (train created<2026-06-01, test June)"},
          open(OUT / "feature_schema.json", "w"), indent=2)
json.dump(metrics, open(OUT / "propensity_metrics.json", "w"), indent=2)
print(json.dumps(metrics, indent=2))
for q, g in gains_cv.items():
    print(f"  call {q:10s} ({g['calls_per_1000_leads']:3d}/1000 leads): captures {g['share_of_activations']:.0%} of activations, {g['activations_per_100_calls']} activations per 100 calls (random: {100 * y.mean():.1f})")
for k, m_ in stage_metrics.items():
    print(f"  stage {m_['stage']:15s} n={m_['n']:4d} base {m_['base_rate']:.1%}: AUC {m_['auc']:.3f} (all-leads {m_['auc_global']:.3f})  Brier {m_['brier']:.3f} (all-leads {m_['brier_global']:.3f})  ECE {m_['ece']:.3f} (all-leads {m_['ece_global']:.3f})")
print(f"[{MODEL_VERSION}] nested CV AUC {cv['auc_mean']} (gap {cv['overfit_gap']}), June AUC {time_holdout['auc']} {time_holdout['auc_ci95']}, "
      f"vs v1 {paired['delta_auc_mean']:+} ({paired['share_folds_v2_better']:.0%} folds), ECE {time_holdout['ece_decile']}, C={C_final}, {time.time() - t0:.0f}s")
