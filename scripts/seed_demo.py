"""Seed the demo store (in-memory: only useful via the API process; run this to inspect what the seed produces).
For a running demo start the API with SEED_ON_START=true, or POST /admin/reset with the admin token."""
import sys
sys.path.insert(0, ".")
from app.seed import seed_demo
from app.leads.service import list_leads
from app.analytics.funnel import compute
print(seed_demo(reset=True))
for r in list_leads()[:8]:
    print(f"{r['score']:.3f}  {r['name'][:34]:34} {r['segment']:<20} {r['stage']:<8} {r['reason']:<18} {r['route']:<12} {r['status']:<10} {r['score_reasons']}")
print(compute()["kpis"])
