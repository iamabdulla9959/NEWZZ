# NEWZZ — Authoritative Product & System Specification

**Product Name:** NEWZZ  
**Classification:** Editorial News Intelligence Platform (Web-Only)  
**Version:** 1.0 (Production Authoritative)  
**Status:** Canonical Source of Truth  

---

## 1. Product Definition

**NEWZZ** is an editorial news intelligence web application that aggregates, verifies, clusters, and objectively ranks real-world news across India and the globe. It delivers clear, substantive, multi-dimensionally ranked news briefings through a responsive broadsheet interface with complete algorithmic transparency.

---

## 2. What NEWZZ Is & What NEWZZ Is NOT

### What NEWZZ Is:
* An **editorial news intelligence web application** designed for modern desktop, tablet, and mobile browsers.
* A **verification-forward** platform requiring multi-source corroboration or official source verification before publication.
* A **multi-dimensional ranking engine** that objectively separates societal importance, situational urgency, freshness, credibility, and personal relevance.
* A **broadsheet presentation** featuring lead editorial stories, state desks, and specialized category feeds.
* A **state-customized experience** supporting readers across all 36 Indian jurisdictions (28 states + 8 union territories).
* **English only** in its active production content.

### What NEWZZ Is NOT:
* **NOT a Reels application:** It does not use vertical snap-scrolling, TikTok-style card flips, or infinite mindless doomscrolling.
* **NOT a Flutter application:** Flutter is neither installed, required, nor used.
* **NOT a React Native / Native Mobile application:** No Android APKs, iOS bundles, or mobile app stores.
* **NOT a GPS-dependent tool:** It does not track user location, query device GPS hardware, or require district geofences.
* **NOT a generic clickbait aggregator:** Articles are clustered across sources, stripped of sensationalist fluff, and summarized into substantive 150–225 word factual briefings.

---

## 3. Current Architecture

```text
               RSS Wire Feeds & State Desks (36 Jurisdictions)
                                     ↓
                    [website_scraping/auto_news_crawler.py]
                                     ↓
                Raw News Storage (news.json / SQLite news.db)
                                     ↓
                     [website_scraping/process_news.py]
                   ├── Story Clustering (TF-IDF Cosine Similarity)
                   ├── LLM Factual Summarization (OpenRouter 150-225w)
                   └── Scoring via packages/ranking_engine
                                     ↓
                         Application Store & Cache
                   ├── newsreels.db (SQLite / SQLAlchemy Models)
                   └── feed.json (Static Precomputed JSON Payload)
                                     ↓
              FastAPI Backend API               Netlify CDN
          (https://newzz-5e19.onrender.com)   (Global Edge Cache)
                      ↓                              ↓
            Proxy `/api/*` Routes            Direct Broadsheet Web UI
                      └──────────────┬───────────────┘
                                     ↓
                             Client Browser
             (index.html · app.js · style.css · state/topic/priority)
```

---

## 4. Frontend Architecture & Source of Truth

The frontend is a lightweight, zero-build Broadsheet Web Application:
* **Frontend Files:**
  * `index.html`: Main editorial newsroom feed with Lead Story, Category Bar, Top News Grid, and State Focus Desk.
  * `state-selection.html`: Regional state desk selector (36 Indian jurisdictions).
  * `topic-selection.html`: Category interest selector for 10 primary categories.
  * `priority-ranking.html`: Drag-and-drop category prioritization interface.
  * `app.js`: Client UX engine managing feed fetching, tab filtering, modal popups, and localStorage preferences.
  * `style.css`: Editorial broadsheet design system with responsive grid layouts and typography scales.
* **Dual Serving Topology (Current Implementation):**
  1. **Root Files (`/`):** The authoritative files deployed to the **Netlify CDN** (`publish = "."`), configured with `Cache-Control: no-cache` headers on `feed.json` and `app.js`.
  2. **FastAPI Static Mirror (`apps/api/app/static/`):** A synchronized mirror mounted at `/` by FastAPI for local execution (`http://localhost:8000/`) and Render web service container runs.
  * *Status:* Neither location is eliminated in this checkpoint; both are maintained in sync until future deployment consolidation.

---

## 5. Backend Architecture

* **Framework:** FastAPI running with Uvicorn on Python 3.11 (`apps/api/app/`).
* **Hosting:** Render Web Service (`https://newzz-5e19.onrender.com`).
* **Local Development:** FastAPI + SQLite (`newsreels.db`).
* **Routers:**
  * `feed.py`: Dynamic feed serving, category filtering, on-the-fly multi-dimensional scoring, and deduplication.
  * `admin.py`: Editorial moderation, review queue for unverified items, and manual curation.
  * `location.py`: Legacy reverse-geocoding endpoints (retained for backward compatibility; unused by primary web flow).
* **Health & Probes:**
  * `GET /health`: Database connection check (`SELECT 1`).
  * `GET /ready`: Readiness probe reporting geocoder provider and database status.
  * `GET /health/ingestion`: Ingestion staleness and worker health monitor.
  * `GET /crawl/trigger`: Asynchronous background crawl cycle trigger.

---

## 6. Ingestion Pipelines (Dual Pipeline Reality)

The codebase currently contains two ingestion systems that operate in parallel:
1. **Primary Active Ingestion (`website_scraping/`):**
   * `auto_news_crawler.py`: Continuously parses RSS wire feeds configured in `feeds.yaml` across all 36 Indian jurisdictions and categories on a 10-minute cadence.
   * `process_news.py`: Deduplicates articles, extracts entities, requests LLM factual summaries (150–225w), applies the ranking engine, and updates `feed.json` and local SQLite databases.
   * `sync_existing_data.py`: Batch sync and scoring utility for persisted stories.
2. **Legacy / Parallel Ingestion Worker (`apps/worker/`):**
   * Multi-provider worker pipeline (`ingest.py`, `pipeline.py`, `cluster.py`, `verify.py`, `validate.py`) supporting Currents, NewsData, NewsAPI, and RSS.
   * Accompanied by a 52-test automated verification suite (`apps/worker/tests/`).
   * *Status:* The systems have **NOT** been merged yet; unification is reserved for a future architectural milestone.

---

## 7. Database & Data Models

* **Engine:** SQLite (`newsreels.db` in repository root).
* **ORM:** SQLAlchemy 2.0 (`apps/api/app/models.py`).
* **Key Entities:**
  * `Card`: Published editorial stories with headline, summary, category, state, 5 ranking component scores, and `final_feed_score`.
  * `Source`: Publisher registry with assigned `trust_tier` ("1", "2", "official_local").
  * `CardSource`: Junction linking published cards to source articles.
  * `StoryCluster`: Clustering record binding related articles covering the same real-world event.
  * `UserPreferences`: Device-linked preference state storing personalized category ordering.
  * `WorkerRun`: Operational audit log tracking ingestion cycles, credit usage, and run durations.
* **Capacity & Distribution Design:**
  * The production system is designed to support the required category and state coverage across all 10 primary categories and all 28 Indian states.
  * *Audit Verification Snapshot:* Verified at audit time with 1,066 cards in local SQLite and 2,168 fresh dispatches in `feed.json`.

---

## 8. Event Clustering & Deduplication

Implemented in `website_scraping/process_news.py` and `packages/ranking_engine`:
* **Method:** TF-IDF vectorization and pairwise cosine similarity over title and snippet tokens.
* **Sliding Window:** 36-hour temporal cutoff prevents historical stories from conflating with new breaking developments.
* **Cluster Leader:** Highest-scoring article or primary wire report becomes the cluster representative.

---

## 9. Verification & Trust System

* **Principle:** Trust is evaluated independently from importance.
* **Verification Scoring:**
  * **Corroborated (95–100):** 2+ independent Tier-1 sources (e.g., The Hindu + Indian Express + Reuters).
  * **Single Wire / Agency (85–94):** 1 reputable wire service (e.g., PTI, ANI, PIB) or official government portal.
  * **Reputable Regional (80–89):** 2+ independent Tier-2 sources.
  * **Single Local Source (60–79):** 1 local report (`single_source` tag).
  * **Unverified / Conflicting (30–59):** Conflicting accounts or unconfirmed rumors (`unverified` tag).

---

## 10. LLM Processing & Summarization

* **Provider:** OpenRouter / Google Gemini via `website_scraping/process_news.py`.
* **Prompt Mandate:**
  * Strict length calibration: **150–225 words**.
  * Neutral, objective journalistic tone.
  * Plain English readable at standard comprehension level.
  * Elimination of sensationalism, clickbait, and redundant source self-references.
  * Clear entity extraction and structured factual reporting.

---

## 11. Objective Importance Engine (0–100)

Evaluates real-world societal consequence across 8 independent dimensions (`packages/ranking_engine/importance_engine.py`):
1. **Human Impact (0–20):** Casualties, injuries, displaced populations.
2. **Public Safety (0–20):** Active environmental, fire, seismic, or biological hazards.
3. **Geographic Scale (0–15):** District (3), state (9), national/global (15).
4. **Economic Consequence (0–10):** Systemic market shifts, major financial disruption.
5. **Government & Policy (0–10):** Legislation, high-court rulings, constitutional actions.
6. **Infrastructure Disruption (0–10):** Power grid, transit, water, health facilities.
7. **Security / Cyber Impact (0–10):** Critical infrastructure attacks, state security.
8. **Long-Term Consequence (0–5):** Multi-year structural outcomes.
* *Cap Rule:* Pure lifestyle, celebrity, or entertainment stories are clamped to a maximum score of 30.0.

---

## 12. Situational Urgency Engine (0–100)

Evaluates real-time criticality (`packages/ranking_engine/urgency_engine.py`):
* **Active Emergency (90–100):** Evacuation warnings, active disasters, severe flood alerts.
* **Developing Crisis (75–89):** Live ongoing rescue operations, immediate high-level meetings.
* **Breaking News (50–74):** Major events verified within the last 60 minutes.
* **Moderate / Follow-up (30–49):** Scheduled administrative or court proceedings.
* **Routine / Commentary (0–29):** Features, analyses, retrospectives.

---

## 13. Time Freshness Engine (0–100)

Evaluates recency using a non-linear decay curve (`packages/ranking_engine/freshness_engine.py`):
* 0–15 min: **100**
* 15–30 min: **95**
* 30–60 min: **90**
* 1–2 hours: **80**
* 2–4 hours: **70**
* 4–8 hours: **55**
* 8–12 hours: **40**
* 12–24 hours: **25**
* 24–48 hours: **10**
* 48+ hours: **0–5**

---

## 14. Personal Relevance Engine (0–100)

Combines geographic proximity and prioritized topic preferences (`packages/ranking_engine/relevance_engine.py`):
$$\text{Personal Relevance} = \text{Geographic Proximity (0–50)} + \text{Topic Priority (0–50)}$$
* **Geographic Component:** Exact State match = 40, National news = 25, Other states / World = 15.
* **Topic Priority Component:** Rank 1 = 50, Rank 2 = 45, Rank 3 = 40, Rank 4 = 35, Rank 5 = 30, Ranks 6–10 = 20–25.

---

## 15. Final Ranking Formula

Master formula evaluated in `packages/ranking_engine/feed_ranking_engine.py`:
$$\mathbf{FINAL\_FEED\_SCORE} = (Imp \times 0.40) + (Urg \times 0.20) + (Fresh \times 0.15) + (Rel \times 0.15) + (Trust \times 0.10)$$

* All 5 components are normalized to $[0, 100]$.
* The final feed score is strictly bounded $[0, 100]$.
* Every card includes a deterministic `priority_reason` explaining the score.

---

## 16. Emergency Handling

* **Emergency Floor:** If Situational Urgency $\ge 90.0$ (e.g. active cyclone warning or evacuation), effective importance is elevated to $\max(imp, 75.0)$ prior to feed calculation.
* This ensures critical civic and life-safety notices immediately surface to the top of the feed without editorial delays.

---

## 17. User Personalization Flow

* **Default Landing:** Direct entrance to the Home Newsroom Feed (`index.html`) with zero mandatory gates or forced redirects.
* **Voluntary Personalization Flow:** Users can customize their experience from the header at any time:
  $$\text{State Selection} \longrightarrow \text{Topic Selection} \longrightarrow \text{Priority Ranking} \longrightarrow \text{Editorial Feed}$$
  1. `state-selection.html`: Select home state desk.
  2. `topic-selection.html`: Select preferred categories.
  3. `priority-ranking.html`: Order categories by personal priority.
  4. Returns user to customized broadsheet feed.

---

## 18. Geographic Coverage Terminology

* **Core Requirement:** All **28 Indian States** are fully supported:
  * Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chhattisgarh, Goa, Gujarat, Haryana, Himachal Pradesh, Jharkhand, Karnataka, Kerala, Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Mizoram, Nagaland, Odisha, Punjab, Rajasthan, Sikkim, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand, West Bengal.
* **Extended Jurisdiction Scope:** All **36 Indian Jurisdictions** (28 States + 8 Union Territories) are recognized and crawled:
  * Union Territories: Andaman and Nicobar Islands, Chandigarh, Dadra and Nagar Haveli and Daman and Diu, Delhi, Jammu and Kashmir, Ladakh, Lakshadweep, Puducherry.

---

## 19. Category Definitions & Desks

### 10 Canonical Primary Categories:
1. `Technology`
2. `Politics`
3. `Business`
4. `National`
5. `World`
6. `Science`
7. `Health`
8. `Sports`
9. `Entertainment`
10. `Environment`

### Regional State Desks:
* **State** is a regional desk / geographic context, **not** one of the 10 primary subject categories.
* Selecting a State Desk filters or prioritizes local news from that jurisdiction while preserving access to national and global developments.

---

## 20. API Contract

| Method | Path | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/` | — | Serves Web Application (Broadsheet UI) |
| `GET` | `/feed` | `category`, `categories`, `state`, `device_id`, `offset`, `limit` | Returns ranked feed with multi-dimensional scores and explainability |
| `GET` | `/user/{device_id}/preferences` | — | Retrieves stored category preferences for a device |
| `PUT` | `/user/{device_id}/preferences` | — | Updates stored category preferences for a device |
| `GET` | `/card/{card_id}/sources` | — | Returns full source details and trust tiers for a card |
| `GET` | `/health` | — | Database connection health probe |
| `GET` | `/ready` | — | System readiness probe |
| `GET` | `/health/ingestion` | — | Background ingestion staleness monitor |
| `GET` | `/crawl/trigger` | — | Asynchronous crawler invocation |

---

## 21. Deployment Architecture

* **Frontend:** Hosted on **Netlify CDN** (`publish = "."` in `netlify.toml`). Reverse proxies `/api/*` to the Render backend.
* **Backend:** Hosted on **Render Web Service** (`render.yaml`) executing FastAPI via `start.sh`.
* **Local Development:** FastAPI backend (`uvicorn app.main:app`) backed by SQLite (`newsreels.db`).
* **GitHub Pages Note:** GitHub Pages is **NOT** an active production deployment; `.nojekyll` has been permanently removed.

---

## 22. Known Operating Notes & Limitations

1. **RSS Snippet Ingestion:** Feeds rely on wire headlines and RSS descriptions. Missing metrics are conservatively scored at baseline.
2. **Cold Start Latency:** Free-tier Render backend instances spin down after inactivity; initial dynamic API calls may take 15–30 seconds to wake up (mitigated by instant static loading from `feed.json`).

---

## 23. Future Strategic Consolidation Roadmap

1. **Worker Unification:** Strategic convergence of legacy `apps/worker/` and active `website_scraping/` into a single, unified ingestion runner.
2. **Frontend Build Pipeline:** Directing Netlify build publish to `apps/api/app/static/` once packaging pipelines are consolidated.
