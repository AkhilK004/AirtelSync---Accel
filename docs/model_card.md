# Model card: lead propensity (`propensity-v3`)

**Purpose.** Ranks leads the advisor could not close by how likely they are to activate, so telesales / partners / field force call the best leads first. It is a ranking aid, not a forecast, and it never decides price, eligibility or KYC.

**Code.** Training and evaluation: `scripts/train_propensity.py` (source of truth, ~45 s). Features: `api/app/leads/features.py`. Scoring and reasons: `api/app/leads/propensity.py`. Live inputs: `api/app/leads/scoring.py`. Quality gates: `api/tests/test_propensity.py`. Full metrics: `data/derived/propensity_metrics.json`. Version and training time: `GET /health` -> `model`.

## Data and target
- 5,000 synthetic leads (`smb_leads.csv`, Apr-Jun 2026), target `activated` (7.4% base rate).
- Leakage guard: no column that is only known after lead creation (stage, outcome, drop reason, later dates, follow-up calls, bundle, value, churn, NPS, acquisition cost). This is asserted in tests.

## Inputs (8, all available when a live lead is scored)
| Feature | Live source |
|---|---|
| segment | advisor (business type + size -> rules engine) |
| city tier | advisor city -> `city_tiers.json` |
| lead source | channel (website / WhatsApp / partner code) |
| current internet | advisor current-tools chips (hotspot / home broadband / leased line; otherwise "Unknown") |
| has GSTIN | advisor |
| existing Accel customer | "Accel mobile" chip; production: subscriber lookup |
| employees (log), sites | advisor |

Deliberately excluded (measured, `docs/assumptions.md` A59): business type (overfits), preferred language (fairness), turnover / telecom spend / Udyam / products of interest (not collected live, so they would cause train/serve skew).

## Model
One-hot (categories with < 20 rows pooled) + standardised numerics -> `LogisticRegression(class_weight="balanced")`, with C chosen by 5-fold grid search over {0.01, 0.03, 0.1, 0.3, 1}. Probabilities are calibrated by undoing the balanced-weight prior shift. A linear model was chosen because every score has to come with plain-language reasons (top-3 coefficient x value). Gradient boosting did not beat it (CV AUC 0.713 vs 0.719).

## Evaluation
| Check | Result | Gate |
|---|---|---|
| Nested 5x5 repeated CV AUC | 0.719 ± 0.026 | ≥ 0.70 |
| Train - validation AUC gap (overfitting) | 0.019 | ≤ 0.04 |
| June time holdout AUC [bootstrap 95% CI] | 0.729 [0.690, 0.767] | lower bound > 0.65 |
| Top-decile lift (June) | 2.21x (16.5% vs 7.5%) | - |
| Calibration: decile ECE / Brier vs base-rate Brier | 0.022 / 0.0664 vs 0.0690 | ECE ≤ 0.03, beat base rate |
| Shuffled-label AUC (leak check) | 0.49 | 0.45-0.55 |
| Learning curve 1k / 2k / 3k / 4k rows | 0.696 / 0.709 / 0.715 / 0.720 | non-decreasing (no under-fitting) |
| vs previous v1 (paired folds) | +0.031 AUC, better on 96% of folds; June +0.034 [+0.008, +0.060] | better on ≥ 80% of folds |

## Gain chart (what a call centre plans with)
Calling leads in score order, out-of-fold over 5x5 CV (random calls hit 7.4 activations per 100 calls):

| Call the | Share of all activations captured | Activations per 100 calls | vs random | June holdout share |
|---|---|---|---|---|
| Top 10% (100 calls per 1,000 leads) | 24% | 17.6 | 2.39x | 22% |
| Top 20% (200 calls per 1,000 leads) | 44% | 16.3 | 2.21x | 45% |
| Top 30% (300 calls per 1,000 leads) | 58% | 14.3 | 1.94x | 56% |
| Top 50% (500 calls per 1,000 leads) | 81% | 12.0 | 1.62x | 83% |

Gated in `test_propensity.py`: each cut beats random by more than 1.2x and the top 30% captures at least 55%.

## Stage-aware scoring (v3)
Back-office leads sit at a funnel stage, so there is one model per stage reached (Contacted, Needs assessed, Quote accepted, KYC complete; same 8 inputs, no class weights). Ranking inside a stage is unchanged; calibration is what improves, so expected values compare across stages (A64).

| Lead has reached | Rows | Actual activation | AUC (stage / all-leads) | Brier (stage / all-leads) | ECE (stage / all-leads) |
|---|---|---|---|---|---|
| Contacted | 3,406 | 10.8% | 0.712 / 0.711 | 0.092 / 0.093 | 0.017 / 0.033 |
| Needs assessed | 1,974 | 18.6% | 0.700 / 0.699 | 0.141 / 0.154 | 0.029 / 0.104 |
| Quote accepted | 861 | 42.7% | 0.682 / 0.667 | 0.220 / 0.342 | 0.063 / 0.331 |
| KYC complete | 588 | 62.6% | 0.621 / 0.573 | 0.227 / 0.497 | 0.081 / 0.516 |

5x5 repeated CV; the all-leads model is trained on every lead outside the test fold, as in production.

## Known limits and how they are handled
- **The model learned the old sales process.** Lead source is its strongest input (WhatsApp ↓, referral ↑), and the advisor is meant to fix exactly the WhatsApp leak. Scores are therefore compared **within** a routing queue, and the model must be retrained on advisor-era leads.
- **Compliance.** A Cancelled / Suspended GSTIN converted as often as an active one in the data. A business rule overrides the model: those leads go to a compliance hold with expected value 0 (A61).
- **Action, not just a score.** After quote acceptance 16% of GSTIN-less leads activate vs 50% with a GSTIN, so a score alone cannot fix them. Those leads carry a `next_action` (KYC assist on the Udyam path; restore GSTIN for a Cancelled/Suspended one) in the back-office (A65).
- **Value, not just probability.** The back-office ranks by P(activate) x the segment's median monthly bundle value (A62).
- **Fairness.** Language is excluded. City tier stays in because it maps to product availability (catalogue eligibility), not to a person.
- **Ceiling.** An AUC around 0.72 is close to what this noisy synthetic outcome allows. Much higher numbers on this data usually mean leaked columns.

## Next model: advisor-era engagement (A66)
The CSV has no behaviour signals, so ~0.72 is its ceiling. The live system now logs counts per advisor journey: messages, questions asked, assumed answers, budget stated and budget gap, quote views, add-on toggles, WhatsApp shares, handoff requests, tracker views, KYC uploads and failures. `GET /backoffice/engagement` returns one row per journey (the 8 model inputs, these counts and the outcome) plus a `readiness` flag: **retrain once there are at least 300 journeys with at least 30 activations**. Until then these signals are shown in the lead drawer but do not change the score. The demo seed carries none of them (its leads come from the CSV).

## Does calling change the outcome? (holdout plan, not built)
The score predicts who will activate, not who activates *because* someone called. In production, leave a random 10% of leads in each routing queue uncalled (the control group), call the rest in score order, and compare activation after the install SLA. The difference is the true uplift; if it is small for the top-scored leads, they would have bought anyway, and calls should move down the list toward leads where a call changes the answer (for example GSTIN-less leads at the KYC stage). Log `called: true/false` on each lead and keep the control group out of every other campaign. A fixed random assignment (hash of the lead id) keeps it auditable. This needs advisor-era data and call logs, so it appears here and on the production-path diagram only.

## Production path (not built, PLAN rule 6)
Weekly drift check on input distributions (population stability index per feature; alert above 0.2). Monthly retrain on a time split. A challenger is promoted only if it passes every gate above and beats the champion on paired folds. Version and training time are already exposed on `/health`.
