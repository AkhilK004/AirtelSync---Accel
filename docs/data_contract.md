# Data contract (Phase 0)

Source: `data/raw/` (copy of `YTL_TrackA_Udyam_Digital_Data/`, read-only). Only `api/app/data/loaders.py` reads these files. All data is synthetic. "Today" = **2026-07-15** (dataset README).

## product_catalogue.csv (25 rows) -> `Product`
| Raw column | Internal field | Notes |
|---|---|---|
| product_id | sku | P01..P25 |
| category | category | Connectivity, Communication, Cloud & Productivity, Security, IoT & Physical |
| product_name / description | name / description | English only; hi/mr names must be added in `catalogue_i18n.json` (derived, not hardcoded in logic) |
| unit | unit | per site, per line, per user, per IP, per channel, per number, per pack, per account, per counter, per device, per camera, per vehicle. Quantity unit is NOT always "site" -> pricing needs a qty rule per unit |
| price_min/max_inr_per_month | monthly_price_min/max_paise | INR -> int paise. Meaning of the range is **not defined** in the README (see assumptions A3) |
| one_time_setup_inr | setup_fee_paise | |
| min_contract_months | contract_months | 1, 3, 6, 12, 24 |
| available_city_tiers | eligible_city_tiers | `1;2` style. **Only tiers 1 and 2 exist** (plan assumed tier 3) |
| min_employees, min_sites | same | product offered only at/above these sizes. There is **no maximum** |
| requires_gstin | requires_gstin | Y/N -> bool |
| requires_one_of | requires_one_of | `|`-separated SKUs; bundle needs **at least one** (OR-dependency, not AND) |
| typical_install_days | install_days | for tracker ETA |
| target_segments | target_segments | micro, prof, multi, mfg (maps to lead segments) |

## smb_leads.csv (5,000 rows) -> DataFrame via `load_leads()`
- Dates parsed (`created_date`..`activated_date`); `has_gstin`/`has_udyam` -> bool; `churned_within_6_months` Y/N -> bool; added `activated` bool.
- Period 2026-04-01..2026-06-30.
- Segments (4): Micro retail & services 2709, Professional offices 1247, Small multi-site businesses 755, Small manufacturers 289.
- `city_tier` in {1,2}; 10 preferred languages (Hindi 2137, English 1168, Marathi 505, Kannada, Gujarati, Telugu, Tamil, Bengali, Punjabi, Malayalam).
- `num_sites`: 1 (4001), 2 (244), then 3..12 (multi-site and some manufacturers); employees 1..150 (median 6).
- `current_internet`: Mobile hotspot, Business broadband, Home broadband, Mixed per site, Leased line (124 null). Null together with `current_provider`.
- `products_of_interest`: `;`-separated valid SKUs. `bundle_products`: `P01x1;P07x2` (activated only).
- `stage_reached` + `outcome`: Activated 368; Dropped 4632 (Lead 1594, Contacted 1432, Needs assessed 1113, Quote accepted 273, KYC complete 220). 21 distinct drop reasons.
- Post-activation fields (value, setup, contract, churn, NPS, days, bundle) are null for non-activated.
- Prices of bundles: median `monthly_bundle_value_inr` 6,900 overall; micro 2,470; prof 6,575; mfg 15,910; multi 28,080.

## mock_gstin_registry.csv (3,534) -> `GstinRecord`
`gstin, legal_name, trade_name, constitution, principal_place_of_business->address, state, registration_date, status`.
Status: Active 3266, Cancelled 167, Suspended 101. Constitution: Proprietorship 2443, Private Limited 631, LLP 460. Proprietor legal names look like `Sneha Rao (Prop. Saffron Bakers)`. Address ends with `- <6-digit pincode>`.

## mock_udyam_registry.csv (2,723) -> `UdyamRecord`
`udyam_number, enterprise_name, enterprise_type (Micro 1833/Small 737/Medium 153), major_activity, nic_description, state, city, date_of_registration`. No PAN, GSTIN or owner field: cross-matching by name only.

## kyc_documents/ (47 PNG, 12 applicants K01-K12)
Pattern `K{nn}_{doc_type}.png`, doc_type in `gst_certificate | udyam_certificate | signatory_id | address_proof`. 4 docs per applicant except K05 (no Udyam certificate) -> 47. Applicants are **not** linked to a lead id or registry key in the CSVs; GSTIN comes from the image itself.

## Referential integrity (verified)
- All lead GSTINs (3,534) exist in the GSTIN registry; all lead Udyam numbers (2,723) exist in the Udyam registry; `has_gstin = Y` always has a `gstin`.
- Registry status among leads: 268 leads hold Cancelled/Suspended GSTINs -> products with `requires_gstin` must check **status**, not only presence.
- All `products_of_interest` SKUs exist in the catalogue. No duplicate lead ids / GSTINs / Udyam numbers.
- Stage dates are in order; every activated lead has `kyc_complete_date`; `days_lead_to_activation == activated_date - created_date` for all 368.

## Headline reproduction (sanity)
Funnel 5000/3406/1974/861/588/368 matches README counts (stage_reached cumulative). Mean lead->activation 17.62 days. Mean follow-up calls (activated) 3.01. CAC = total acquisition cost / 368 = Rs 15,053. Activation GSTIN Y 9.56% vs N 2.05%.

## Validator calibration (PLAN rule 4)
- GSTIN format regex: 100% of registry. GSTIN mod-36 checksum: **100%** -> enforce as FAIL.
- PAN-embedded 4th char (GSTIN position 6) is always `X` -> validator must accept `X` (README).
- Udyam regex `^UDYAM-[A-Z]{2}-\d{2}-\d{7}$`: 100% (district code always `00`).
