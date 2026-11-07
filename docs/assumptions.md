# Assumptions & deviations from PLAN.md

| # | Item | Decision |
|---|---|---|
| A1 | Data location | Dataset copied to `data/raw/` (original `YTL_TrackA_Udyam_Digital_Data/` left untouched). |
| A2 | City tiers | Data has tiers 1 and 2 only (plan assumed 3). Tier-3 handling in advisor = treat unknown city as the least-served tier (2) with an assumption note. |
| A3 | Price range meaning | **Resolved:** unit price = midpoint of [min,max], rounded half-up to a whole rupee (`PRICE_POINT_RULE=midpoint`). Calibrated on 368 activated leads: bundle value / sum(midpoint x qty) has median 0.992 (min-rule 1.14, max-rule 0.88); 74% within +/-5%. Show this rule on the pricing slide. |
| A4 | Dependencies | `requires_one_of` is OR semantics (at least one SKU). Plan's "closure" is adapted accordingly. |
| A5 | Size limits | Catalogue has only `min_employees`/`min_sites` (no max). Plan's `SIZE_TOO_LARGE` code is unused. |
| A6 | Languages | Data has 10 languages; UI ships en, hi, mr per plan. Others fall back to English/Hindi. |
| A7 | Whether prices include GST | **Resolved: exclusive.** `monthly_bundle_value_inr` of activated leads equals the pre-GST midpoint total (A3), so GST (18%, config) is added on top, rounded half-up in paise. |
| A8 | Tooling | `uv` not installed system-wide; installed via `pip install uv`, invoked as `python -m uv`. Python 3.12 managed by uv. |
| A9 | shadcn toast | shadcn deprecated `toast`; `sonner` used instead. |
| A10 | GSTIN checksum | 100% of registry passes -> enforced as FAIL (PLAN rule 4). |
| A11 | "Today" | 2026-07-15 (`settings.TODAY`) for bill recency / expiry checks. |
| A12 | Git | `web/` was created with its own `.git` by create-next-app; handled in phase commit (see README of phase report). |
| A13 | Quantity semantics | Calibrated on activated bundles: `bundle_products` qty is the billed quantity; per-site products have qty = number of sites (95% for per-site); setup fee = setup x qty (100% match, so **no extra sites multiplier**); bundle contract = max of line contracts (100% match). |
| A14 | Segments | Business type -> segment is read from leads (every business_type maps to exactly one segment). Multi-site = 3-12 sites in data, so `MULTI_SITE_MIN_LOCATIONS=3`. Manufacturers (12-150 staff) and `locations > 10` are `assisted`. A chain business type with <3 locations is treated as professional (>6 staff) or micro. Unknown business type: sized by team (<=6 micro else professional) + assumption note. |
| A15 | Bundle templates | `api/config/bundles.yaml` maps needs -> catalogue SKUs per segment. Choice of core vs optional follows what activated leads buy (e.g. 100% of professionals buy cloud email P16 and most buy endpoint security P20 -> required; failover/CCTV/backup optional). Quantities: staff-ratio rules (e.g. SIMs ~0.33 x staff for offices, email/security = staff). These are judgement calls informed by data, not catalogue facts. |
| A16 | Tier choice | Smallest eligible tier whose `fits_up_to` covers team size; if the preferred tier is ineligible (e.g. 1G in tier-2), next-best eligible tier is used and the exclusion is reported. Fixed wireless (P04) is a fallback used only when no fibre/leased line is eligible or fibre is unavailable. |
| A17 | Dependencies in quotes | Core lines and pre-selected add-ons get dependency closure at recommendation time (cheapest eligible provider, else dependent dropped with `DEPENDENCY_INELIGIBLE`). Other add-ons resolve at toggle time: ON pulls in the cheapest eligible provider; OFF removes dependents. Fibre SKUs are blocked as providers when `fibre_available=false`. |
| A18 | GSTIN eligibility | `requires_gstin` products need `gstin_status == active`. "Applied", "inactive" (Cancelled/Suspended) and none all block them with distinct messages. |
| A19 | Mock latency | 300-600 ms random delay on `/mock/*` (config `MOCK_LATENCY_MS_*`, 0 in tests). |
