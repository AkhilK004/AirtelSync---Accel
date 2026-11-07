"""Gain chart for the slides from the saved training metrics (no re-training). Usage: cd api && python -m uv run python ../scripts/make_gain_chart.py"""
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

M = json.load(open("../data/derived/propensity_metrics.json"))
g = M["gains_cv_oof"]; h = M["time_holdout"]["gains"]
qs = [0.1, 0.2, 0.3, 0.5]
x = [0] + [q * 100 for q in qs] + [100]
cv = [0] + [g[f"top_{int(q * 100)}pct"]["share_of_activations"] * 100 for q in qs] + [100]
ho = [0] + [h[f"top_{int(q * 100)}pct"]["share_of_activations"] * 100 for q in qs] + [100]
plt.figure(figsize=(6.4, 4.2))
plt.plot([0, 100], [0, 100], "--", color="#999999", label="Calling at random")
plt.plot(x, cv, "-o", color="#E40000", label="Propensity model (cross-validated)")
plt.plot(x, ho, "-s", color="#444444", label="Propensity model (June holdout)")
for q, v in zip(qs, cv[1:5]):
    plt.annotate(f"{v:.0f}%", (q * 100, v), textcoords="offset points", xytext=(6, -12), fontsize=8)
plt.xlabel("Share of leads called (best first), %"); plt.ylabel("Share of all activations reached, %")
plt.title(f"Calling the top 30% of leads reaches {cv[3]:.0f}% of activations"); plt.legend(loc="lower right", fontsize=8)
plt.grid(alpha=0.2); plt.tight_layout()
out = Path("../docs/charts/gain_chart.png"); plt.savefig(out, dpi=160); print("wrote", out)
