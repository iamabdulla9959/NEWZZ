# News Reels — Progress Log

Work top to bottom. Status: `[ ]` not started · `[~]` in progress · `[x]` done

## Backlog

- [x] **TASK 1 — Repo scaffold**
- [x] **TASK 2 — Data models**
- [x] **TASK 3 — Ingestion worker**
- [x] **TASK 4 — Clustering / dedup** (re-verified with geographic sharding & keyword pre-filter)
- [x] **TASK 5 — Verification logic** (updated with official_local rule & verification_type)
- [x] **TASK 6 — Summarization pipeline** (re-verified with abstractive rewrite & typographic visual generator)
- [x] **TASK 7 — Validation pipeline** (re-verified checking against original_text)
- [x] **TASK 8 — Review queue + minimal admin**
- [x] **TASK 9 — Feed API**
- [x] **TASK 10 — Mobile: onboarding**
- [x] **TASK 11 — Mobile: main feed**
- [x] **TASK 12 — Mobile: caught-up state**
- [x] **TASK 13 — End-to-end smoke test**

## Notes

### Risk Review & Schema Updates Applied (Steps 1–6)
1. **Verification Rules (Patch FR3/FR4)**:
   - Added `trust_tier: "official_local"` to `Source` and `CardSource` models (migrated `trust_tier` from `Integer` to `String(32)`).
   - District/local scope cards are eligible to publish with either 2+ independent sources or exactly 1 `official_local` source. A single non-official source cannot publish.
   - Added `verification_type` field ("cross_verified" | "official_source" | "flagged_conflict") to `Card` model, API schemas, and mobile app.
   - Mobile displays distinct `"🏛️ Official Source"` badge for official local stories.
2. **Regional Ingestion + Translation Layer**:
   - Added `original_language`, `original_text`, `translated_text`, `translation_confidence` to `Article` model. `original_text` is permanently retained.
   - Integrated `langdetect` in ingestion worker. If language != "en", invokes strict LLM translation prompt.
   - Seeded verified vernacular sub-feeds (Amar Ujala Delhi for Hindi district news, OneIndia Tamil for Tamil regional news) and official local source.
   - Verified live ingestion against Amar Ujala Delhi: populated both `original_text` (Hindi) and `translated_text` (English).
3. **Geographic Sharding for Clustering (Task 4 Re-verification)**:
   - Re-written clustering: articles are strictly queried within matching `(category, state, district)` tags and published within the last 24 hours.
   - Cheap keyword pre-filter checks `>= 3` shared significant keywords before vector evaluation. Dropped candidates logged to `filtered_out` audit table.
   - Benchmark script `apps/worker/scripts/benchmark_clustering.py` verified 96.0% candidate query reduction vs full table.
4. **Abstractive Rewrite & No-Hotlink Media (Task 6 Re-verification)**:
   - Updated summarization prompt to explicitly enforce extracting core entities and writing an entirely new plain 6th-grade narrative without mirroring source phrasing.
   - Built `card_visual` generator with Figma category color palettes: orange (local), teal (state), blue (national), purple (international), green (tech), pink (science).
   - Eliminated any source image URL fetching; card visual renders pure typographic gradient headline cards.
5. **Multi-Provider LLM Resilience & Health Logging**:
   - Built `MultiProviderClient` wrapper: tries Gemini first, falls back to Groq, then to OpenRouter free tier. Logs serving provider.
   - Added `worker_runs` table logging timestamp, sources polled, articles ingested, errors, and duration after every run.
   - Exposed `GET /health/ingestion` with uptime monitor documentation in code comments.
6. **Privacy-by-Design Audit**:
   - Confirmed zero PII (no name, email, phone, or GPS permissions). State and district selection is dropdown-only and persisted exclusively in local `AsyncStorage`.
7. **Task 7 Re-verification**:
   - Fact-consistency judge in `pipeline.py` updated to verify against `original_text` when available, avoiding lossy intermediate translation errors.
8. **Test Verification**:
   - All 36 automated unit tests passing (`pytest apps/api/tests apps/worker/tests`).
   - End-to-end smoke test `apps/worker/scripts/e2e_smoke.py` passes.
