# Software Requirements Specification (SRS) for News Reels

## 1. Introduction

### 1.1 Purpose
This document specifies the software requirements for the **News Reels** web application. It describes the purpose, architecture, features, user flows, ranking algorithms, verification standards, and quality gates implemented in the project. This document serves as the single source of truth for developers, reviewers, and stakeholders.

### 1.2 Scope
News Reels is a modern, state-aware news reels web application designed for India. It delivers rich, swipeable news reels that combine verified reporting from multiple reputable news outlets into objective, easy-to-read stories.

Key capabilities of the system:
* **In-Depth Meaningful Summaries:** Every news reel contains a thorough summary strictly between **200 and 250 words** written in simple, clear English.
* **Truthful Source Verification:** Clearly tags each story with transparent verification badges: Single Source, Multi-Source (Cross-Verified), Official Government Source, or Conflicting Reports.
* **Transparent Source Attribution:** Displays direct clickable publisher links (e.g., The Hindu, Times of India, BBC, PIB, Indian Express) and photographer credits.
* **Manual State Onboarding:** Clean 3-step onboarding allowing users to choose their Indian State or Union Territory without invasive GPS permissions.
* **Smart Editorial Ranking:** Ranks news using objective importance, priority scores, civic urgency boosts (+30 for disasters, elections, public health), and user category preferences.
* **Semantic Story Clustering:** Automatically identifies and merges related reports covering the same news event to eliminate repetitive feed clutter.

### 1.3 Definitions and Acronyms
* **Reel / Card:** A full-screen or vertical card containing a headline, image, category, 200–250 word summary, verification badge, and publisher source links.
* **Story Cluster:** A collection of ingested articles from different publishers describing the same real-world incident.
* **Cross-Verified:** A story confirmed by two or more independent news sources.
* **Official Source:** A story confirmed by a recognized government body or public news agency (e.g., PIB, DD News, News On AIR, .gov).
* **Single Source:** A story reported by only one news outlet, clearly labeled as not independently corroborated.
* **Reading Grade Level:** Flesch-Kincaid score measuring text readability (targeted between Grade 5.0 and 10.0 for simple everyday English).

### 1.4 References
* News Reels Technical Documentation (`docs/AI_PROJECT_HANDOFF.md`, `README.md`)
* FastAPI Framework Documentation: https://fastapi.tiangolo.com/
* React Native Web & Expo Documentation: https://docs.expo.dev/

---

## 2. Overall Description

### 2.1 Product Architecture
The system consists of three coordinated subsystems:
1. **Web Client (`apps/mobile`):** Built with React Native Web and Expo. Runs on `http://localhost:8081` with vertical snap scrolling, category chips, save/bookmark capabilities, and responsive mobile-first layouts.
2. **REST API Server (`apps/api`):** Built with Python and FastAPI running on `http://localhost:8000`. Serves personalized and category-filtered news feeds, user preference ranking, source lookups, and administrative review queues.
3. **News Ingestion & Verification Worker (`apps/worker`):** Background pipeline that ingests news feeds (RSS, NewsData.io, Currents), deduplicates stories, clusters related articles using cosine similarity embeddings, produces 200–250 word summaries via LLM providers (Gemini, Groq, OpenRouter), and applies automated verification rules.

```
+-------------------------------------------------------------------------+
|                          Real News Providers                            |
|             (National Dailies, Vernacular Press, PIB, RSS)              |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                       Ingestion & Worker Pipeline                       |
|   1. Ingest & Deduplicate URLs                                          |
|   2. Semantic Cosine Clustering (Group same-story articles)             |
|   3. Multi-Provider LLM Summarizer (200-250 Words, Simple English)      |
|   4. Automated Quality Gate (Word count, Grade level, Banned words)     |
|   5. Verification Engine (Single Source vs Multi vs Official)           |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  Database (PostgreSQL / SQLite Storage)                 |
|             Cards, Clusters, Sources, User Preferences, Runs            |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        FastAPI Backend (Port 8000)                      |
|       /feed | /card/{id}/sources | /user/{device_id}/preferences        |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                      Expo Web Client (Port 8081)                        |
|       Vertical Reel Pager, State Filter, Category Tabs, Bookmarks       |
+-------------------------------------------------------------------------+
```

### 2.2 User Characteristics
* **Target Audience:** General news readers, students, working professionals, and civic-minded citizens in India.
* **Reading Preference:** Fast, concise, yet fully detailed information that explains the background, main event, and consequences in 200–250 words without requiring reading a 1,500-word article.
* **Language Requirement:** Simple, accessible English free of unnecessarily dense academic jargon.

### 2.3 General Constraints
* **Summary Word Length:** Every published card summary must strictly remain within **200 to 250 words** (quality validation gate permits 180 to 260 words buffer).
* **Clarity & Readability:** Text must score between **5.0 and 10.0** on the Flesch-Kincaid reading grade level.
* **No Sensationalism:** Banned opinion terms ("shocking", "unbelievable", "mind-blowing", "miracle", "explosive", "bombshell") are strictly rejected by the automated validation filter.
* **Privacy by Default:** Zero GPS or precise device geolocation required. Users pick their State manually.

---

## 3. Specific Requirements

### 3.1 Functional Requirements

#### FR-1: Onboarding & User State Configuration
* **FR-1.1 (State Selection):** The web app provides a 3-step onboarding flow. Step 1 presents a clean grid of all 28 Indian States and Union Territories with no pre-selected state forcing.
* **FR-1.2 (Interest Selection):** Step 2 allows users to select their favorite news categories.
* **FR-1.3 (Category Priority Ordering):** Step 3 allows users to drag or rearrange category priority. The order is stored locally and synced to the backend via `/user/{device_id}/preferences`.
* **FR-1.4 (Reset Capability):** Users can reset their preferences at any time from the feed header button (`⚙️`) or the Caught Up screen.

#### FR-2: Meaningful 200–250 Word Summaries
* **FR-2.1 (Word Count Bounds):** Every reel summary must contain between 200 and 250 words.
* **FR-2.2 (Structure & Content Depth):** Each summary must explain:
  1. **The Core Event:** What happened, who was involved, and where it took place.
  2. **The Context & Background:** Why this event occurred or historical background.
  3. **The Immediate Impact & Next Steps:** Official statements, government actions, economic/social effects, and what to expect next.
* **FR-2.3 (Simple English Tone):** Sentences must be concise (12 to 18 words on average). Language must remain neutral, factual, and informative.
* **FR-2.4 (Sentence Range):** Summaries must contain between 7 and 20 well-formed sentences.

#### FR-3: Verification & Truth Badges
* **FR-3.1 (Single Source):** When a card is supported by only 1 publisher source, the UI displays `📰 Single Source — [Publisher Name]` or `📰 Single Source — Not Independently Corroborated`.
* **FR-3.2 (Cross-Verified Multi-Source):** When two or more independent sources confirm the event, the UI displays `📰 Multi-Source ([Count] sources)`.
* **FR-3.3 (Official Source):** When verified by recognized government departments or wire services (PIB, DD News, News On AIR, .gov), the badge displays `🏛️ Official Source`.
* **FR-3.4 (Conflicting Reports):** If key numbers or facts differ by >20% across news outlets, the badge displays `⚠️ Conflicting Reports`.

#### FR-4: Smart Feed & Ranking Engine
* **FR-4.1 (Urgency Civic Boost):** Stories with urgent civic impact (e.g. elections, natural disasters, floods, health emergencies, accidents, rescues) receive a **+30.0 score boost** to appear at the top.
* **FR-4.2 (Location Relevance Boost):** Stories matching the user's selected state receive a **+5.0 boost**; district matches receive **+10.0 boost**.
* **FR-4.3 (Editorial Priority):** Cards carry priority scores (1 to 10) assigned based on real-world impact.
* **FR-4.4 (Objective Quality Score):** Calculated from source trust tier, impact keywords count, and exponential recency decay (24-hour half-life).
* **FR-4.5 (Cluster Deduplication):** Only the single best-ranked card from each story cluster is displayed to prevent duplicate reels.

#### FR-5: User Interaction & Reading Features
* **FR-5.1 (Vertical Snap Paging):** The web app supports vertical snap scrolling for an immersive reels experience.
* **FR-5.2 (Category Navigation):** A horizontal header bar allows filtering by: For You (`✨`), State (`🗺️`), National (`🇮🇳`), World (`🌍`), Politics (`🏛️`), Business (`💼`), Health (`⚕️`), Sports (`🏅`), Education (`📚`), Tech (`⚡`), and Science (`🔬`).
* **FR-5.3 (Save / Bookmark):** Users can click the Save button (`🔖`) to save stories locally for offline or later reading.
* **FR-5.4 (Share Story):** Users can click the Share button (`🔗`) to copy the headline and summary directly.
* **FR-5.5 (Direct Source Links):** Every card displays clickable source links (`Source: [Name] ↗`) that open the original news publisher's article in a new browser tab.
* **FR-5.6 (Caught Up State):** When all reels in a category have been viewed, a friendly Caught Up screen is displayed with options to refresh or reset onboarding.

---

### 3.2 Quality & Ingestion Pipeline Requirements

#### QR-1: Automated Quality Validation Gate (`validate.py`)
Before any generated summary card is approved for publishing, it must pass all 4 checks:
1. **Word Count Check:** Must be between 180 and 260 words.
2. **Sentence Count Check:** Must be between 7 and 20 sentences.
3. **Reading Grade Check:** Flesch-Kincaid score must be between Grade 5.0 and 10.0.
4. **Banned Words Check:** Zero hits on sensationalist opinion vocabulary.
5. **Hallucination Consistency Check:** If fact-checking judge LLM detects unsupported claims, the card is sent to the human editorial review queue.

#### QR-2: Multi-Provider LLM Resilience
* The ingestion pipeline supports multi-provider fallback:
  * Primary: Google Gemini (`gemini-2.5-flash`)
  * Secondary Fallback: Groq (`llama-3.3-70b-versatile`)
  * Tertiary Fallback: OpenRouter Free tier (`deepseek/deepseek-r1:free` or `google/gemini-2.0-flash-lite-preview-02-05:free`)
* All pipeline runs and provider outcomes are logged in the `worker_runs` database table.

---

### 3.3 Non-Functional Requirements

#### NFR-1: Usability & Aesthetics
* **Theme:** Sleek dark-mode aesthetic (`#0A0A0D` background, `#EB7D00` warm accent, `#EBE3A7` soft gold secondary text).
* **Responsive Layout:** Optimized for mobile browser viewports (max-width 540px centered on desktop monitors).
* **Accessibility:** Accessible touch targets (minimum 48x48px), clear semantic labels, and high contrast ratios.

#### NFR-2: Performance & Latency
* **Feed API Response Time:** Under 150ms for standard paginated feed requests.
* **Client Smoothness:** 60 FPS smooth momentum scrolling on mobile and desktop web browsers.

#### NFR-3: Security & Privacy
* **Secret Protection:** API keys and credentials reside exclusively in `.env` and are strictly excluded from git tracking.
* **CORS Protection:** Configurable `CORS_ORIGINS` via application configuration.
* **Zero Location Tracking:** No tracking cookies, no GPS tracking, and no external advertising scripts.

---

## 4. Verification & Testing

### 4.1 Automated Test Suite
The project includes automated test suites covering:
* `apps/api/tests/`: Feed sorting, category filtering, admin moderation, health checks, location mapping, and priority ranking.
* `apps/worker/tests/`: Clustering, credit budgets, ingest deduplication, LLM fallback resilience, scoring recency decay, summary schema parsing, quality validation rules, source verification logic, and visual SVG rendering.

### 4.2 Test Execution Commands
* **Run Worker Tests:**
  ```powershell
  d:\News\.venv\Scripts\python.exe -m pytest apps/worker/tests/ -v
  ```
* **Run API Tests:**
  ```powershell
  d:\News\.venv\Scripts\python.exe -m pytest apps/api/tests/ -v
  ```

---

## 5. Summary Standards Checklist

To verify that any card's summary meets the News Reels standard:
- [x] **Word Count:** Exactly 200 to 250 words.
- [x] **Meaningful Content:** Answers What, Who, Where, When, and Why with context and implications.
- [x] **Simple English:** Flesch-Kincaid Grade level between 5.0 and 10.0; clear, simple sentences.
- [x] **Factually Grounded:** 100% faithful to the source articles; no hallucinated claims.
- [x] **Zero Clickbait:** Completely objective; no banned sensational words.
- [x] **Direct Publisher Links:** At least one live link to the original report.
