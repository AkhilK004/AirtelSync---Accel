# Business case — slide outline (10 slides)

Every figure is from `docs/findings.md` or `docs/slide_numbers.json` (regenerate: `python -m uv run python ../scripts/slide_numbers.py`). **Targets are targets, not forecasts.** Charts are in `docs/charts/`.

> **Check against the case brief:** PLAN.md says the deck must answer "the 5 key questions" but does not list them. This outline assumes: Q1 who is the target customer, Q2 what do we sell and at what price, Q3 how do we get them live fast, Q4 which channel owns which lead, Q5 how do we measure success. If the brief's questions differ, re-map the slide titles.

---
### 1. The problem: 5,000 leads, 368 activations
- Funnel 5,000 → 3,406 → 1,974 → 861 → 588 → **368** (7.4%). Steepest drop: needs assessed → quote accepted, **44%**.
- Lead → activation **17.6 days**, **3 status chases** per customer, **₹15,053** blended cost per activation vs ₹6,900 median monthly bundle.
- Where it leaks: 1,113 leads lost after needs assessment (price 414, competitor 207, quote too complex 206, quote too slow 179, wait 107); 273 lost at quote-accepted, **all paperwork**.
- Chart: `funnel.png`.

### 2. Who first, and why (Q1)
| Order | Segment | Evidence |
|---|---|---|
| 1 beachhead | **Professional offices** | 11.1% activation, ₹10.7k cost per activation, ₹6,575 median value, 13.8% churn, payback ~1.6 months of revenue |
| 2 | **Micro retail** via partners / WhatsApp / referral | 54% of leads, 4.1% activation, **₹20.0k** cost per activation vs ₹2,470 value: only works with a low-cost digital path |
| 3 (phase 2) | **Multi-site** | 11.0%, ₹28k median value, payback < 1 month; assisted by field force |
| 4 | **Manufacturers** | 12.8%, ₹15.9k value; always field-led (site survey) |
- Chart: `segment_economics.png`, `activation_by_segment.png`.
- **GSTIN is the gate:** quote accepted → KYC complete is **81% with GSTIN vs 25% without**; activation 9.6% vs 2.0% → GSTIN-less path (Udyam) is first-class, and registry **status** is checked (22 activations went to Cancelled / Suspended GSTINs).

### 3. Bundles and pricing (Q2)
Four bundles from the real catalogue. One monthly price, GST included, add-ons toggle with dependencies handled.
| Bundle | Example | Monthly (ex GST) | Monthly (incl. 18% GST) | Setup (incl. GST) | Contract |
|---|---|---|---|---|---|
| Dukaan Starter | kirana, 2 staff, tier 2 | ₹1,448 | **₹1,708.64** | ₹0 | 12 m |
| Pro Office | clinic, 6 staff, tier 1 | ₹3,369 | **₹3,975.42** | ₹0 | 12 m |
| Multi-Site Connect | 4 restaurants, 40 staff | ₹9,388 | **₹11,077.84** | ₹7,080 | 12 m |
| Factory Connect | auto parts, 80 staff (assisted) | ₹41,880 | **₹49,418.40** | ₹17,700 | 24 m |
- **Pricing rule (show it):** unit price = midpoint of the catalogue range, rounded to the rupee; quantity per site / user as in activated bundles; GST on top. Calibrated: activated bundle value ÷ midpoint total has median **0.99**, 74% within ±5%.
- No savings claim: median current telecom spend (micro ₹900) is below the bundle, because the bundle adds fibre, SIMs and services. The value is one bill, one plan that fits, in your language.

### 4. Journey before vs after (Q3)
| | Today | Udyam Digital |
|---|---|---|
| Discovery | field visit / call | advisor chat in hi / en / mr, 5 questions |
| Quote | 3–5 days, complex | instant, single transparent price |
| KYC | paper chase, 94 missing-document drops | lookup + upload, decision in minutes, fix instructions |
| Status | 3 calls | tracker + WhatsApp-style updates |
| Time to activate | **17.6 days** | target ≤ 5 days (digital lines live at once) |

### 5. The product (demo screens + architecture)
Screens: advisor chat → quote with toggles → checkout → consent + KYC → tracker → back-office. Architecture: `charts/architecture.png`. Principle: **the LLM never decides price, eligibility or KYC**; it extracts and phrases.

### 6. Smart KYC and compliance
- Lookup-first prefill, quality gate, GSTIN checksum, registry status, certificate-vs-registry, name / address / signatory / bill-recency checks, deterministic decision (approved / action required / manual review / rejected), fix instruction in the owner's language.
- Consent screen: 3 languages, granular, marketing off, append-only ledger.
- Evidence: **12 specimen applicants, 12/12 decisions match** the draft answer key (includes cancelled GSTIN, blur, checksum error, tampered certificate, stale bill, missing Udyam certificate; offline fixture run and live Gemini vision run both 12/12). *Say plainly in the pitch that the extraction behind this run is a transcription fixture and the answer key is a draft until verified.*

### 7. Channel model (Q4)
- **Field force:** multi-site, manufacturers, assisted leads (site survey).
- **Partners:** leads with their code or in their cities; attribution preserved for commission.
- **Telesales:** the rest, sorted by expected monthly value (propensity x typical bundle value). Propensity v3: scored per funnel stage so late leads rank correctly (calibration error at KYC stage 0.52 -> 0.08); nested-CV AUC 0.72, June holdout 0.73 (95% CI 0.69-0.77); **calling the top 30% of leads reaches 58% of activations** (chart: `gain_chart.png`); trained only on facts the advisor collects; language deliberately excluded (fairness). Leads without a GSTIN at the KYC stage get a concrete task: offer the Udyam path (16% activate vs 50% with a GSTIN).
- **Compliance hold:** a Cancelled / Suspended GSTIN is never pushed to sales, however likely to convert (22 such activations in the data).
- **Credit sharing:** digital sales in a territory are credited to that territory's field team (protects against channel conflict).
- Why: field sales cost ₹24.3k and partners ₹20.9k per activation vs referral ₹4.1k, inbound ₹5.1k, website ₹6.4k: send the people only where a visit is needed.
- Charts: `cac_by_source.png`, `gain_chart.png`.

### 8. Unit economics
| Segment | Cost per activation today | Median monthly value | Revenue payback |
|---|---|---|---|
| Micro retail | ₹20.0k | ₹2,470 | 8.1 months |
| Professional | ₹10.7k | ₹6,575 | 1.6 |
| Manufacturer | ₹15.3k | ₹15,910 | 1.0 |
| Multi-site | ₹15.6k | ₹28,080 | 0.6 |
- Target cost per activation **≤ ₹6k** is anchored on what low-touch channels already achieve (website ₹6.4k, inbound ₹5.1k, referral ₹4.1k, WhatsApp ₹4.0k). Payback is on **revenue** (no margin data in the pack).

### 9. Metrics, targets and rollout (Q5)
| Metric | Today | Target | Measured by |
|---|---|---|---|
| Lead → activation | 7.4% | 14% | funnel panel |
| Needs → quote accepted | 44% | 65% | funnel panel |
| Time to activate | 17.6 d | ≤ 5 d | order events |
| Status chases / order | 3 | < 0.5 | tracker views per order |
| Cost per activation | ₹15k | ≤ ₹6k | finance |
| Guardrail | 6-month churn | not worse | cohort |
- Rollout: pilot in 2 cities (professional offices + partner-led micro retail) → 10 cities → national; multi-site and manufacturers stay field-led.

### 10. Risks and mitigations
| Risk | Mitigation |
|---|---|
| LLM error or manipulation | deterministic engine owns price / eligibility / KYC; reply post-check; injection tests |
| Document fraud | registry cross-checks, checksum, tamper signal to human review |
| Channel conflict | territory credit sharing, partner attribution |
| Language quality | hi / en / mr UI reviewed by native speakers (**not yet done**), template fallbacks |
| Telecom SIM KYC rules | SIM activation stays a regulated step; DigiLocker / e-sign in production |
| Data breach | minimisation, no photo storage, 1-day review TTL, India-only processing |
| Untested at scale | live Gemini run and load test still to do |
