# LandOS Feature Tracker

> **Last updated:** 2026-03-23
> Track progress by changing status: `[ ]` → `[~]` (in progress) → `[x]` (done)

---

## Recently Completed

- [x] **AI search robustness overhaul** — Comprehensive fix to the AI explore pipeline:
  - [x] Fix KeyError 'name' crashes: bulletproof `build_flat_results` with safe index validation
  - [x] Runtime Dublin vs non-Dublin table filtering (not just prompt-based)
  - [x] Title synthesis fallback for all 17 table types when AI fails to provide titles
  - [x] Column naming guidance in hypothesis prompt (tables have different column names)
  - [x] Evaluation prompt validation of site picks (type-check indices, scores, signals)
  - [x] User-friendly error messages instead of raw Python exceptions
  - [x] Improved SQL broaden/retry prompts with common fix patterns
  - [x] Non-Dublin area geocoding (fly-to works for Cork, Galway, etc.)
  - [x] Better 0-result messaging with follow-up suggestions
  - [x] Logging throughout the pipeline for debugging

## Quick Wins (days)

- [ ] **Opportunity score per parcel** — Join zoning + size + no building + RZLT status, colour-code on map
- [ ] **Unregistered land layer** — Render parcels in neither freehold nor leasehold as hatched overlay
- [ ] **Planning timeline per parcel** — Click a parcel, see associated DCC planning apps as a timeline
- [ ] **Constraints checklist on click** — Zoned? RZLT? Planning history? Conservation? One panel summary

## Medium Effort (weeks)

- [ ] **AI site dossier** — Click high-scoring parcel → generate one-page PDF with all layers + AI narrative
- [ ] **Comparables engine** — PPR data spatially joined, show avg price/sqm within 500m over 24 months
- [ ] **Saved searches + alerts** — Define filters, save them, get notified on new matches
- [ ] **Reusable AI queries** — Save natural language searches as repeatable filters/workflows
- [ ] **Demographics on click** — Surface census stats (density, age, household size) per area
- [ ] **Topography layer** — OSi elevation data, flag slopes relevant to buildability

## Larger Lifts (when you have traction)

- [ ] **Ownership lookups** — Connect to Tailte Éireann folio system or link out to landdirect.ie
- [ ] **Bulk export + letters** — Select multiple parcels, export CSV/PDF, eventually send letters to owners
- [ ] **Data enrichment API** — Upload Eircodes/coordinates, get back scored + enriched data
- [ ] **Appraisal calculator** — Basic residual land value model (GDV minus costs = land value)
- [ ] **Collaboration** — Site sharing, team workspaces, notes per parcel
- [ ] **AI agents** — Automated weekly scans of target areas with emailed summaries
