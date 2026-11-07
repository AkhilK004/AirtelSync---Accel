"""Run advisor scenarios. In-process by default (uses LLM_PROVIDER env); --base-url runs against a deployed API.
Usage (from api/):  python -m uv run python ../scripts/run_scenarios.py [--provider fake|gemini] [--base-url https://...]"""
import argparse
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--base-url")
ap.add_argument("--provider", choices=["fake", "gemini"])
ap.add_argument("--only")
a = ap.parse_args()
if a.provider:
    os.environ["LLM_PROVIDER"] = a.provider
os.environ.setdefault("MOCK_LATENCY_MS_MAX", "0")
sys.path.insert(0, ".")

from app.advisor.scenario_runner import HttpClient, LocalClient, load_scenarios, run_scenario  # noqa: E402

client = HttpClient(a.base_url) if a.base_url else LocalClient()
sc = [s for s in load_scenarios() if not a.only or a.only in s["name"]]
bad = 0
for s in sc:
    try:
        f = run_scenario(client, s)
    except Exception as e:  # noqa: BLE001
        f = [f"EXC {type(e).__name__}: {e}"]
    print(("PASS " if not f else "FAIL ") + s["name"] + ("" if not f else "  <- " + "; ".join(f)))
    bad += bool(f)
print(f"\n{len(sc) - bad}/{len(sc)} passed")
sys.exit(1 if bad else 0)
