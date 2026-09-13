# Newzz — Structured Importance & Multi-Dimensional News Platform

A verification-forward, local-relevant, and explainable news platform. News Reels clusters multi-source coverage, verifies facts, and ranks real-world events using an objective 5-dimension scoring engine that answers:

> **“What news event is most important for this user to know right now?”**

---

## 1. Core Design Principle

The ranking system strictly separates these three fundamental concepts:

1. **Importance (0–100)**: How much does this real-world event matter to society? (Evaluated across 8 objective dimensions).
2. **Verification / Trust (0–100)**: How confident are we that the reported information is reliable? (Evaluated from source authority and multi-outlet corroboration).
3. **Personal Relevance (0–100)**: How relevant is this event to this particular user? (Evaluated from geographic proximity and category preferences).

These concepts are never conflated into a single ambiguous number. A major earthquake reported by a single source retains high importance while being honestly presented with a developing verification state.

---

## 2. Product Scope & Coverage

* **Platform Scope**: **Web-Only**. High-performance, responsive editorial web application designed for modern desktop, tablet, and mobile browsers.
* **Language Scope**: **English-Only**. Ingestion, analysis, summarization, and feeds operate strictly in English.
* **Onboarding Flow**: Clean, zero-friction 4-step configuration:
  $$\text{Welcome} \longrightarrow \text{State Selection} \longrightarrow \text{Category Interests} \longrightarrow \text{Priority Ranking} \longrightarrow \text{Live Reels Feed}$$
* **No Geolocation / GPS Requirement**: Fast, privacy-respecting user state selection without requiring browser GPS permissions, reverse-geocoding latency, or district ambiguity.
* **10 Primary Categories** (>= 40 distinct reels each; 948 reels total):
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
* **All 28 Indian States Supported**:
  * Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chhattisgarh, Goa, Gujarat, Haryana, Himachal Pradesh, Jharkhand, Karnataka, Kerala, Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Mizoram, Nagaland, Odisha, Punjab, Rajasthan, Sikkim, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand, West Bengal.
  * User state selection dynamically adjusts the **Personal Relevance (0–100)** score while leaving objective societal importance and trust verification invariant.

---

## 3. End-to-End Architecture

```text
NEWS SCRAPING & INGESTION (RSS Feeds & Wire APIs)
                     ↓
         NORMALIZATION & CLEANING
                     ↓
        STORY CLUSTERING & DEDUPLICATION (TF-IDF Cosine Similarity)
                     ↓
        STRUCTURED EVENT ANALYSIS (8 Societal Impact Dimensions)
                     ↓
  ┌──────────────────────────────────────────────────────────┐
  │              5 INDEPENDENT SCORING ENGINES               │
  ├──────────────────────────┬───────────────────────────────┤
  │ 1. Objective Importance  │ Human, Safety, Infra, Cyber.. │
  │ 2. Situational Urgency   │ Active Emergency / Alert      │
  │ 3. Time Freshness        │ Non-Linear Age Decay Curve    │
  │ 4. Verification / Trust  │ Tier-1 vs Tier-2 Corroboration│
  │ 5. Personal Relevance    │ Geographic Proximity + Topics │
  └──────────────────────────┴───────────────────────────────┘
                     ↓
      DETERMINISTIC FINAL SCORE & EXPLAINABLE REASON
                     ↓
     FASTAPI BACKEND & RESPONSIVE WEB APPLICATION
```

### Repository Structure

```text
d:\News\
├── apps/
│   ├── api/                    # FastAPI backend & Web Application
│   │   ├── app/                # Routers (feed, admin, location), models, schemas
│   │   ├── app/static/         # Web frontend (index.html, style.css, app.js)
│   │   ├── alembic/            # Database schema migrations
│   │   └── tests/              # API & integration test suite
│   └── worker/                 # Background worker pipeline & validation gates
├── packages/
│   └── ranking_engine/         # Centralized Multi-Dimensional Ranking Package
│       ├── config.py           # Configurable weights, bounds, decay curve
│       ├── models.py           # Pydantic schema models
│       ├── importance_engine.py# 8-dimension objective impact evaluator
│       ├── urgency_engine.py   # Temporal situational urgency evaluator
│       ├── freshness_engine.py # Timestamp decay engine
│       ├── verification_engine.py # Corroboration & credibility engine
│       ├── relevance_engine.py # Location and topic relevance engine
│       ├── feed_ranking_engine.py # Master formula & explainability generator
│       └── tests/              # 10 benchmark scenarios & property invariants
├── website_scraping/           # Automated RSS scraper & multi-source clustering bot
├── docs/                       # Specifications and handoff documentation
├── .env.example                # Environment variables template
└── docker-compose.yml
```

---

## 4. The Ranking Engine

### A. Objective Importance Score (0–100)

Evaluates real-world societal impact across 8 distinct dimensions with conservative scoring when evidence is missing:

| Dimension | Max Score | Evaluation Focus |
| :--- | :---: | :--- |
| **Human Impact** | 20 | Casualties, injuries, displaced populations, large-scale disruption. Contextual rules ensure celebrity deaths are never conflated with mass disasters. |
| **Public Safety / Life** | 20 | Active physical threats (cyclones, earthquakes, floods, fires, epidemics, active security threats) requiring public vigilance or evacuation. |
| **Geographic Scale** | 15 | District (3), multi-district (6), state (9), multi-state (12), national/global (15). |
| **Economic Impact** | 10 | Systemic financial disruption, banking crisis, major industrial damage, macro policy shifts. |
| **Government / Policy** | 10 | Statutes, high-court rulings, constitutional amendments, treaties, major elections. |
| **Infrastructure Impact** | 10 | Disruption to power grids, water supply, transportation/rail, telecommunications, hospitals, airports. |
| **Security / Cyber Impact** | 10 | Ransomware attacks on critical infrastructure, state-level cyber threats, data breaches, armed conflict. |
| **Long-Term Consequence** | 5 | Generational, multi-year structural changes. |
| **TOTAL** | **100** | Bounded $[0, 100]$. Clamped to 30.0 max for pure lifestyle/celebrity gossip. |

### B. Situational Urgency Score (0–100)

Distinguishes real-time situational urgency from static importance:
* **Active Emergency (90–100)**: Active evacuation orders, flash floods, imminent cyclone landfall, active threat.
* **Developing Crisis (75–89)**: Breaking rescue operations, live court verdict, emergency cabinet meeting.
* **Breaking News (50–74)**: Confirmed major event within last 60 minutes.
* **Moderate / Follow-up (30–49)**: Scheduled proceedings, ongoing investigation.
* **Routine / Commentary (0–29)**: Retrospectives, opinion columns, general analysis.

### C. Time Freshness Score (0–100)

Uses best-available timestamp precedence:
$$\text{event\_time} \longrightarrow \text{published\_at} \longrightarrow \text{scraped\_at}$$

Calculated via a non-linear decay curve (configurable in `RankingConfig`):
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

### D. Verification / Trust Score (0–100)

Strictly separated from importance so unverified major events are not hidden, but flagged:
* **Multiple Tier-1 sources corroborated**: **95–100** (`corroborated`)
* **Single Tier-1 wire service / official agency**: **85–94** (`verified`)
* **Multiple Tier-2 reputable sources**: **80–89** (`corroborated`)
* **Single reputable local source**: **60–79** (`single_source`)
* **Conflicting / weak / unconfirmed report**: **30–59** (`conflicting` or `unverified`)

### E. Personal Relevance Score (0–100)

Combines user-configured State preference and prioritized category interests:
$$\text{Personal Relevance} = \text{State / Geographic Component (0–50)} + \text{Category Priority Component (0–50)}$$

* **State / Geographic Component**:
  * Exact State match (e.g. Telangana story for a Telangana reader): **40**
  * National news: **25**
  * Global news / other states: **15**
  *(Internal sub-state/district matching up to 50 is supported at the engine layer when district metadata exists on the card, but user onboarding is strictly state-level)*.
* **Category Priority Component**:
  * Derived from the user's ordered personal priority ranking:
    * Rank 1 category: **50**
    * Rank 2 category: **45**
    * Rank 3 category: **40**
    * Rank 4 category: **35**
    * Rank 5 category: **30**
    * Rank 6–10 categories: **20–25**

### F. Final Feed Score Formula

$$\mathbf{FINAL\_FEED\_SCORE} = (Imp \times 0.40) + (Urg \times 0.20) + (Fresh \times 0.15) + (Rel \times 0.15) + (Trust \times 0.10)$$

* **Emergency Floor**: If situational urgency $\ge 90.0$ (active civic emergency), effective importance is elevated to $\max(imp, 75.0)$ *before* calculating the final feed score. This ensures critical emergencies immediately surface without manual intervention.
* **Priority Neutrality**: Legacy `priority_score` remains purely informative metadata and never modifies objective importance, urgency, or the final ranking.
* **36-Hour Clustering Window**: Story clustering groups articles sharing semantic similarity only if published within a 36-hour sliding window, preventing historical events from conflating with new occurrences.
* All 5 components are normalized to $[0, 100]$.
* The final feed score is strictly bounded $[0, 100]$.
* Every card provides a human-readable `priority_reason` generated strictly from underlying evidence.

---

## 5. Quick Start & Setup

### Prerequisites
* Python 3.11+ (Windows, Linux, or macOS)
* SQLite (default) or PostgreSQL

### 1. Configure Environment
```bash
cp .env.example .env
```
*(No paid API keys are required to run the core application, database, and ranking engine)*

### 2. Install Dependencies
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r apps/api/requirements.txt
pip install -r apps/worker/requirements.txt
pip install -r website_scraping/requirements.txt
```

### 3. Run Database Migrations
```bash
cd apps/api
alembic upgrade head
cd ../..
```

### 4. Start the Application
```bash
# Start FastAPI backend & Web Application (serves Web UI at http://localhost:8000/)
uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000/`** in any web browser.

### 5. (Optional) Run Scraper & News Processor
```bash
# Ingest live RSS feeds from feeds.yaml
python website_scraping/auto_news_crawler.py

# Deduplicate, summarize, rank, and sync to News Reels database
python website_scraping/process_news.py --limit 15
```

---

## 6. API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Responsive Web Application (Single-Page App) |
| `GET` | `/feed` | Ranked feed with multi-dimensional scores and explainability |
| `GET` | `/health` | API health status probe |
| `GET` | `/ready` | Database and service readiness probe |
| `GET` | `/health/ingestion` | Background ingestion monitoring probe |
| `GET` | `/admin/review` | Admin review queue for unverified items |
| `GET` | `/reverse-geocode` | *(Legacy/Utility)* Coordinates → State/District reverse geocoding |

### Feed Query Parameters
* `category` / `categories` — Filter by primary category (`technology`, `politics`, `business`, `national`, `world`, `science`, `health`, `sports`, `entertainment`, `environment`, `state`)
* `state` — User state for dynamic personal relevance scoring (e.g. `Telangana`, `Karnataka`, `Bihar`)
* `device_id` — User device identifier to apply personal category priority rankings
* `limit` — Maximum items to return per page (default: 30)
* `offset` — Pagination offset for continuous infinite scroll
* `district` — *(Internal/Legacy)* Optional district-level granularity parameter where available

---

## 7. Running Tests & Audits

### Core Test Suites
```bash
# 1. Ranking Engine Test Suite (Scenario benchmarks & invariants):
pytest packages/ranking_engine/tests/test_ranking_cases.py -v

# 2. Controlled Ranking Discrimination (Casualty context vs active emergency):
python scratch/test_ranking_discrimination.py

# 3. Capacity & Distribution Verification (948 cards, 10 categories >= 40, 28 states):
python scratch/b15_6_verify_capacity.py

# 4. Comprehensive Browser User Acceptance Test (B17 UAT - Onboarding, Feeds, Infinite Scroll):
python scratch/run_b17_uat.py
```

### Specialized Engine Audits
* `python scratch/b5_feed_ranking_audit.py` — Monotonicity & ranking integrity audit
* `python scratch/b6_freshness_audit.py` — Recency & non-linear time decay audit
* `python scratch/b7_verification_audit.py` — Tier-1/Tier-2 trust & corroboration audit
* `python scratch/b8_importance_audit.py` — 8 societal impact dimensions audit
* `python scratch/b9_urgency_audit.py` — Situational urgency & emergency floor audit
* `python scratch/b10_relevance_audit.py` — State relevance & priority order audit

---

## 8. Known Limitations & Operating Notes

1. **RSS Snippet Evidence vs Full Article**: The automated crawler collects headlines and summaries from reputable wire feeds and publisher RSS sources. The Importance Engine conservatively scores missing factual data (e.g., exact unconfirmed financial damages) at baseline rather than hallucinating estimates.
2. **Current Release Focus**: The current production release of News Reels is **Web-Only** (optimized for modern mobile, tablet, and desktop browsers). Native mobile prototypes in `apps/mobile/` are maintained separately for historical reference.
