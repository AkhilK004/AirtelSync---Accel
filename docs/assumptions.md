# Assumptions & deviations from PLAN.md

| # | Item | Decision |
|---|---|---|
| A1 | Data location | Dataset copied to `data/raw/` (original `YTL_TrackA_Udyam_Digital_Data/` left untouched). |
| A2 | City tiers | Data has tiers 1 and 2 only (plan assumed 3). Tier-3 handling in advisor = treat unknown city as the least-served tier (2) with an assumption note. |
| A3 | Price range meaning | README does not say what `[min, max]` means. Phase 2 will pick a deterministic point in range and document it (config `PRICE_POINT_RULE`). Validate against `monthly_bundle_value_inr` of activated leads. |
| A4 | Dependencies | `requires_one_of` is OR semantics (at least one SKU). Plan's "closure" is adapted accordingly. |
| A5 | Size limits | Catalogue has only `min_employees`/`min_sites` (no max). Plan's `SIZE_TOO_LARGE` code is unused. |
| A6 | Languages | Data has 10 languages; UI ships en, hi, mr per plan. Others fall back to English/Hindi. |
| A7 | Whether prices include GST | Not stated. Assume **exclusive**; GST added at `GST_RATE` 18% (config). Confirm in Phase 2. |
| A8 | Tooling | `uv` not installed system-wide; installed via `pip install uv`, invoked as `python -m uv`. Python 3.12 managed by uv. |
| A9 | shadcn toast | shadcn deprecated `toast`; `sonner` used instead. |
| A10 | GSTIN checksum | 100% of registry passes -> enforced as FAIL (PLAN rule 4). |
| A11 | "Today" | 2026-07-15 (`settings.TODAY`) for bill recency / expiry checks. |
| A12 | Git | `web/` was created with its own `.git` by create-next-app; handled in phase commit (see README of phase report). |
