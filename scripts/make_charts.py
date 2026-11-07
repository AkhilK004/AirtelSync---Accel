import sys; sys.path.insert(0, ".")
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, pandas as pd
from app.data.loaders import get_data
L = get_data().leads; A = L[L.activated]; OUT = Path("../docs/charts"); OUT.mkdir(parents=True, exist_ok=True)
C1, C2 = "#E40000", "#444444"
def save(name): plt.tight_layout(); plt.savefig(OUT / name, dpi=160); plt.close()
order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
idx = L.stage_reached.map({s: i for i, s in enumerate(order)})
cnt = [int((idx >= i).sum()) for i in range(6)]
plt.figure(figsize=(7, 4)); b = plt.barh(order[::-1], cnt[::-1], color=C1)
for r, v, i in zip(b, cnt[::-1], range(6)):
    pct = "" if i == 5 else f"  ({cnt[::-1][i]/cnt[::-1][i+1]:.0%} of prev)"
    plt.text(v + 40, r.get_y() + r.get_height()/2, f"{v:,}{pct}", va="center", fontsize=8)
plt.xlim(0, 6500); plt.title("Funnel: 5,000 leads -> 368 activations (7.4%)"); save("funnel.png")
def bar(series, title, fn, fmt="{:.1%}", h=3.6):
    plt.figure(figsize=(7, h)); ax = series.sort_values().plot.barh(color=C1)
    for p, v in zip(ax.patches, series.sort_values()): ax.text(v, p.get_y() + p.get_height()/2, " " + fmt.format(v), va="center", fontsize=8)
    ax.set_ylabel(""); plt.title(title); save(fn)
bar(L.groupby(L.has_gstin.map({True: "Has GSTIN", False: "No GSTIN"})).activated.mean(), "Activation rate: GSTIN vs none", "activation_by_gstin.png", h=2.4)
bar(L.groupby("segment").activated.mean(), "Activation rate by segment", "activation_by_segment.png")
bar(L.groupby("lead_source").activated.mean(), "Activation rate by lead source", "activation_by_source.png")
cac = L.groupby("lead_source").acquisition_cost_inr.sum() / L.groupby("lead_source").activated.sum()
bar(cac, "Cost per activation by source (Rs)", "cac_by_source.png", fmt="{:,.0f}")
gq = L.assign(g=L.has_gstin.map({True: "GSTIN", False: "No GSTIN"}))
q = gq.groupby("g").apply(lambda x: ((x.stage_reached.map({s: i for i, s in enumerate(order)}) >= 4).sum()) / ((x.stage_reached.map({s: i for i, s in enumerate(order)}) >= 3).sum()), include_groups=False)
bar(q, "Quote accepted -> KYC complete, by GSTIN", "quote_to_kyc_by_gstin.png", fmt="{:.0%}", h=2.4)
ch = A.groupby("current_internet").churned_within_6_months.mean()
bar(ch, "6-month churn by customer's prior internet", "churn_by_prior_internet.png")
calls = A.groupby(pd.cut(A.customer_follow_up_calls, [-1, 1, 3, 5, 20], labels=["0-1", "2-3", "4-5", "6+"]), observed=True).churned_within_6_months.mean()
bar(calls, "6-month churn vs status-chase calls", "churn_by_followup_calls.png", h=2.8)
print(sorted(p.name for p in OUT.iterdir()))
