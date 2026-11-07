# Data privacy & security note — Project Udyam Digital

*Prototype with synthetic data. Principles follow the Digital Personal Data Protection Act, 2023; the DPDP Rules timelines are a production step.*

**Purposes and retention** — each purpose is a separate, unticked-by-default choice.

| Purpose (consent id) | Data used | Required | Kept |
|---|---|---|---|
| Verify business and signatory (`kyc_verification`) | extracted document fields, GSTIN / Udyam, masked ID | yes | extracted fields 12 months; photos **not stored** |
| Install, activate, bill, support (`service_delivery`) | contact, address, order | yes | life of the service |
| Offers by WhatsApp / SMS (`marketing`) | phone | no, **off by default** | until withdrawn |
| Share contact with local installer (`partner_sharing`) | name, phone, address | no, partner flow only, off | until withdrawn |

**Consent design.** Shown in the owner's language (hi / en / mr) before any document is touched: who we are, what, why, how long, rights, grievance contact, in under 120 words, with the full notice one tap away. Grants and withdrawals are an append-only ledger (notice version, language, timestamp, channel, salted-hash principal). Withdrawing is as easy as giving; withdrawing KYC consent blocks the KYC endpoints.

**Data minimisation.** Registry lookup first (GSTIN / Udyam prefill), then only the documents that path needs. Photos are read in memory and discarded; only a manual-review case stores images, in a bucket that **deletes them after 1 day**. Aadhaar, if uploaded, is masked to the last 4 digits immediately. The order keeps the phone's last 4 digits and a salted hash, not the number. Back-office shows phones masked. Lead scoring logs only behaviour counts (messages, quote views, add-on toggles), never message text, and uses them for service-delivery prioritisation. The tracker needs the last 4 digits of the phone.

**Localisation.** Storage (Firestore), review bucket, Cloud Run and the Gemini model all run in GCP Mumbai (`asia-south1`).

**Security.** TLS; encryption at rest (Google-managed); least-privilege service account; upload limits (5 MB, content sniffed, JPG / PNG / PDF only); rate limits per client; CORS allow-list; security headers; back-office Basic auth and admin token (the server refuses to start in production with default secrets); audit log for KYC decisions and back-office actions; **logs redact** phones, GSTIN, PAN, 12-digit ids and emails; secrets are not in the repo.

**AI governance.** The LLM extracts facts and phrases replies; it **never** sets price, eligibility or a KYC outcome. Prices, eligibility and decisions are deterministic code with tests. Replies that contain a price, percentage or product not in the facts are discarded. Prompt-injection and discount requests leave the price unchanged. Edge cases (a certificate that differs from the registry) go to a person; a rejected GSTIN is explained, not silently dropped.

**Rights and grievance.** Access, correction, erasure and withdrawal are available on request through the grievance officer (grievance@accel-business.example, fictional); self-service endpoints are the next build step.

**Production next steps.** DigiLocker + e-sign instead of photo upload, a registered consent manager, a data-protection impact assessment, breach-response runbook, vendor contracts for the LLM provider, and compliance with the DPDP Rules phase-in dates.
