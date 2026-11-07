"""Run the full KYC pipeline (extraction -> checks -> decision) on every specimen applicant and compare with docs/kyc_expected.csv.
Usage (from api/): python -m uv run python ../scripts/eval_kyc.py [--provider fake|gemini]   (exit code 1 on any mismatch)"""
import argparse
import csv
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--provider", choices=["fake", "gemini"])
ap.add_argument("--expected", default="../docs/kyc_expected.csv")
a = ap.parse_args()
if a.provider:
    os.environ["LLM_PROVIDER"] = a.provider
sys.path.insert(0, ".")

from app.data.loaders import get_data  # noqa: E402
from app.kyc.pipeline import evaluate, process_document  # noqa: E402
from app.kyc.quality import sniff_mime  # noqa: E402
from app.models.kyc import KycApplication  # noqa: E402

expected = {r["applicant_id"]: r for r in csv.DictReader(open(a.expected, encoding="utf-8"))}
rows, bad = [], 0
for aid, files in sorted(get_data().kyc.items()):
    app = KycApplication(order_id=aid, path="gstin")
    for f in files:
        data = Path(f.path).read_bytes()
        ex, checks, _ = process_document(f.doc_type, data, sniff_mime(data) or "image/png")
        app.docs[f.doc_type], app.doc_checks[f.doc_type] = ex, checks
    checks, dec = evaluate(app)
    codes = sorted({c.code for c in checks if c.status in ("FAIL", "WARN")})
    exp = expected[aid]
    exp_codes = sorted(x for x in exp["expected_issue_codes"].split("|") if x)
    ok = dec.status == exp["expected_decision"] and codes == exp_codes
    bad += not ok
    rows.append((aid, exp["expected_decision"], dec.status, "|".join(codes) or "-", "✓" if ok else "✗  expected codes: " + ("|".join(exp_codes) or "-")))
w = [max(len(str(r[i])) for r in rows + [("applicant", "expected", "predicted", "issue codes", "match")]) for i in range(4)]
print("  ".join(h.ljust(w[i]) for i, h in enumerate(["applicant", "expected", "predicted", "issue codes"])) + "  match")
for r in rows:
    print("  ".join(str(r[i]).ljust(w[i]) for i in range(4)) + "  " + r[4])
print(f"\n{len(rows) - bad}/{len(rows)} match")
sys.exit(1 if bad else 0)
