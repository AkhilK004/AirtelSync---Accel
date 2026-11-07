# Findings (Phase 1)

Reproduce: `cd api && python -m uv run python ../scripts/eda.py` (tables), `../scripts/make_charts.py` (charts in `docs/charts/`), `../scripts/train_propensity.py` (model). All numbers from `data/raw/smb_leads.csv` via `loaders.py`.

## 1. Headline numbers reproduced
| Metric | Case | Data |
|---|---|---|
| Funnel (cumulative) | 5,000 / 3,406 / 1,974 / 861 / 588 / 368 | identical |
| Stage conversion | 68 / 58 / 44 / 68 / 63 % | identical |
| Lead -> activation days | 17.6 | 17.62 |
| Follow-up calls (activated) | 3 | 3.01 (non-activated: 0.88) |
| Cost per activation | ~Rs 15,000 | Rs 15,053 |
| Activation with GSTIN / without | 9.6% / 2.0% | 9.56% / 2.05% |
| Median bundle value | Rs 6,900 | Rs 6,900 (micro 2,470) |

## 2. Planted signals found
1. **GSTIN is the gate to the quote -> KYC step, not just to activation.** Quote accepted -> KYC complete: **81% with GSTIN vs 25% without**. Needs assessed -> quote accepted: 48% vs 33%. (chart `quote_to_kyc_by_gstin.png`). Without a GSTIN only 30 of 1,466 leads activate.
2. **Micro retail is the leak.** Needs -> quote: **32%** for micro vs 53% professional, 56% multi-site, 64% manufacturers. Activation 4.1% micro vs 11.1% / 11.0% / 12.8%. Micro is 54% of leads but 30% of activations, and has the highest 6-month churn (**22.7%** vs 8-14%). Median micro bundle Rs 2,470 against Rs 15,000 CAC -> loss-making via current channels.
3. **Channel economics are inverted.** Cost per activation: Field sales **Rs 24,335**, Channel partner **Rs 20,851**, Website Rs 6,352, Inbound Rs 5,113, Referral **Rs 4,099**, WhatsApp Rs 4,026. Referral also converts best (14.8% vs 7.4% avg). Field sales + partners = 55% of leads and 85% of spend. WhatsApp/Website leak early: Lead -> Contacted 41% / 55% vs ~72% others; WhatsApp needs -> quote 27%.
4. **Prior internet predicts activation and churn.** Mobile hotspot users: 4.5% activation, 24.7% churn. Home broadband: 22.1% churn. Business broadband: 9.3% activation, 8.3% churn. Leased line 15.0%, mixed per site 12.7% activation. (Hotspot/home users are the ones for whom fixed-wireless/low-tier bundles + advisor should be tuned.)
5. **Quote-accepted drops are all paperwork (273 leads).** Missing GST/Udyam document 94, paperwork too long 79, authorised signatory unavailable 53, document details did not match 47. This is the Smart KYC target: ~5.5% of all leads die here.
6. **Needs-assessed drops (1,113 leads, the 44% step) are quote problems:** Price too high 414, Competitor cheaper 207, Quote too complex 206, Quote too slow 179, Decided to wait 107. 385 of these (35%) are complexity/slowness -> fixable by an instant single-price quote.
7. **Pre-contact drops are lead quality/process:** Unreachable after 3 attempts 805, Wrong number 319, Not interested 470 (Lead stage); owner no time for visit 531, visit not scheduled by sales 296, locked-in 325, mobile-only 280 (Contacted). 827 leads (visit not done / no time) are lost to the field-visit model itself.
8. **Post-sale experience hurts retention.** Churn vs status-chase calls: 0-1 calls **5.9%**, 2-3 **12.7%**, 4-5 **23.0%** (NPS 7.5 -> 6.4). NPS falls from 7.3 (11-15 days) to 5.8 (>25 days); churn 22% above 25 days. A tracker that removes chasing and a shorter cycle protect retention.
9. **Cancelled/Suspended GSTINs got sold to.** 167 leads hold a Cancelled and 101 a Suspended GSTIN in the mock registry; 18 and 4 of them activated (10.8% / 4.0%). Cancelled GSTINs convert as well as Active ones (10.8% vs 9.7%). The KYC step must check registry **status**, not only presence. 22 activations are compliance exposure.
10. **Size:** activation 4.5% for <=2 employees, 10.7% for 11-25, 14.1% for 26-50. Telecom spend above ~Rs 1,950/month: 11% vs 4.5% below Rs 750. Turnover <40 lakh: 3.9%, 5-25 cr: 13.0%.
11. **Language:** Hindi/English/Bengali/Malayalam/Telugu ~8-9%; Tamil 4.3%, Punjabi 4.2%, Kannada 5.1% (small n 96-253; weak evidence).

## 3. Null / negative results (stated honestly)
- **Quote delay has no effect:** mean needs->quote days are 4.11 (activated) vs 4.04 (dropped); contacted->needs 2.96 vs 2.96. Delay days do not separate converters; the "Quote took too long" drop (179) is a stated reason only.
- **Bundle-fit vs segment targets does not predict churn.** 100% target-fit bundles churn 16.0%, 50-99% fit 9.5% (n=42); no mis-sold-churn signal. Only multi-site shows non-fit SKUs. Bundle size: single-category bundles churn 20.7% (n=29), 3-4 categories 12-13%; 5 categories 57% (n=7, too small).
- **Calendar months** are flat (7.1% / 7.5% / 7.5%): no time trend.
- Highest-churn SKUs among bought: P18 website 37.5% (n=16), P04 5G FWA 33.3% (n=9), P22 Secure Wi-Fi 22.6% (n=62), P15 WhatsApp API 22.2% (n=54). Small n except P22/P15.

## 4. Data-quality checks
No out-of-order stage dates; every activated lead has `kyc_complete_date`; `days_lead_to_activation` equals date difference for all 368; no duplicate lead ids / GSTINs / Udyam; all registry links valid; NPS 2-10; no non-positive bundle values. `business_name` repeats 3,066 times (synthetic generator; not a real duplicate key). Only data-quality issue relevant to modelling: 124 leads have null `current_internet`/`current_provider` (imputed "Unknown"). **No rows excluded from training.**

## 5. Propensity model (`app/leads/propensity.py`, `data/derived/propensity.joblib`)
- Target: `activated`. Features (known at creation/advisor): segment, business type, city tier, source, language, current internet, turnover band, has GSTIN, has Udyam, log employees, num sites, log telecom spend, # products of interest. **Excluded as leakage:** stage reached, outcome, drop reason, all later dates, days to activation, follow-up calls, bundle, value, setup, contract, churn, NPS, acquisition cost (list in `app/leads/features.py`; asserted in tests).
- Split: time-based. Train created < 2026-06-01 (3,296 rows), test June (1,704 rows, base rate 7.45%).
- LogisticRegression (class_weight balanced, C=0.3); probability re-calibrated by undoing the balanced prior shift.

| Model | AUC (test) | Top-decile lift | Top-decile activation rate |
|---|---|---|---|
| Logistic regression (shipped) | **0.695** | **2.21x** | 16.5% vs 7.5% base |
| HistGradientBoosting (comparison) | 0.677 | 1.89x | 14.1% |

Calibration on test (predicted mean vs actual, quintiles): 1.0%/0.9%, 2.7%/5.9%, 5.2%/7.6%, 8.9%/7.6%, 17.9%/15.2%. Ranking is monotonic; the middle is slightly under-predicted. Modest AUC is expected: the planted effects (GSTIN, segment, source, hotspot) are strong but outcome is noisy. Use for **ranking whom to call first**, not for forecasting.
- Reasons are the 3 largest coefficient x value contributions, e.g. `['Has GSTIN ↑', 'Tier-2 city ↓', 'Uses Business broadband ↓']`.

## 6. Charts (`docs/charts/`)
`funnel.png`, `activation_by_gstin.png`, `quote_to_kyc_by_gstin.png`, `activation_by_segment.png`, `activation_by_source.png`, `cac_by_source.png`, `churn_by_prior_internet.png`, `churn_by_followup_calls.png`.

## 7. Implications for build
GSTIN-less path must be first-class (Udyam + PAN/bill) and flagged as higher risk in propensity; micro bundles need a low-cost digital path (referral/WhatsApp-assisted, partner commission) rather than field visits; check GSTIN **status** in KYC; one instant transparent quote; tracker to cut status calls; route multi-site/manufacturers to field force.
