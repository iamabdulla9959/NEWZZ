# Product Requirements Document — News Reels

**Version:** 1.0 (MVP) | **Owner:** You (PM) | **Status:** Draft for review

---

## 1. Overview

**Product name (working):** News Reels
**One-line description:** A mobile app that delivers verified, plain-English news summaries in a swipeable, Reels-style feed — organized from hyperlocal to global — so users can stay informed in minutes and actually remember what they read.

**Problem statement:**
People want to stay informed across multiple scopes (district → state → national → international → tech → science) but face three competing failures in existing products: (1) short-news apps like Inshorts optimize for speed but don't visibly verify accuracy, (2) full-article aggregators like Google News are trustworthy but too slow/dense for daily habit-forming use, and (3) both are designed for infinite engagement rather than actually helping users retain what they read.

**Vision:** Become the news app people trust *because* it shows its work — verification as the core product experience, not backend hygiene.

---

## 2. Goals & Success Metrics

| Goal | Metric | MVP Target |
|---|---|---|
| Prove the core loop works | D1 retention | ≥25% |
| Prove content is trustworthy | % cards with 2+ verified sources | 100% (or explicitly flagged) |
| Prove "remember it" value prop | Post-session recall (via user testing, not in-app) | Qualitative pass in soft launch |
| Validate habit formation | Avg. sessions/day per active user | ≥1.5 |
| Keep it cheap | Monthly infra + API spend during MVP | $0–150 |

**Non-goals for v1:** monetization, personalization/recommendation algorithm, multi-language support, push notifications beyond one daily recap, native fact-checking ML model (we use rules + LLM-judge instead).

---

## 3. Target Users & Personas

- **Primary: "Busy Daily Reader"** — 20–40 yo, checks news 1–3x/day between tasks, wants to feel informed without doomscrolling or being misled. India-based initially (district/state relevance).
- **Secondary: "Skeptical Switcher"** — currently uses Inshorts/Google News but is fatigued by ads or unsure what's verified vs. rumor; actively looking for a trust-first alternative.

---

## 4. Scope — MVP Feature List (Prioritized)

### P0 — Must have for launch

| Feature | Description |
|---|---|
| Onboarding: location | User selects state + district (2 screens max) |
| Onboarding: interests | Topic chips; District/State/National/International/Tech pre-selected |
| Main feed | Full-screen vertical swipe cards, one story per screen |
| Card content | Headline (≤10 words), 3–5 sentence summary, category tag, timestamp |
| Verification badge | Visible "✅ Verified by [Source A], [Source B]" on every card |
| Source cross-check pipeline | No card publishes without 2+ independent sources (or 1 Tier-1 wire service) |
| Summarization pipeline | LLM summarization under strict prompt rules (see §5.2) |
| Post-generation validation | Word count, reading-level, banned-opinion-word, and fact-consistency checks before publish |
| Human review queue | Lightweight admin view for flagged/sensitive stories |
| Save & Share | Bookmark and native share sheet on each card |
| Full Story link | Tap-through to original source article |
| "You're caught up" screen | End-of-feed state, no infinite scroll illusion |

### P1 — Fast-follow (within 4–6 weeks of launch)

| Feature | Description |
|---|---|
| Quick Recap card | Every 5–6 stories, a 3-bullet recap card |
| Daily Recap push | Single fixed-time notification with the day's top verified stories |
| Additional categories | Science, Business, Sports toggles |
| "How We Verify" page | Public static page explaining the methodology |

### P2 — Later / Phase 2+

| Feature | Description |
|---|---|
| Personalized ranking | Weight feed by save/read behavior, with forced diversity floor |
| Multi-language support | Hindi/Telugu/etc. |
| Streak/gamification | Daily streak indicator |
| Monetization | Native ads or ad-free premium tier |
| Public API | Syndicate verified/summarized feed to other apps |

---

## 5. Functional Requirements Detail

### 5.1 Ingestion & Verification

- FR1: System polls whitelisted RSS/API sources every 10–15 minutes.
- FR2: System clusters articles reporting the same event using text-similarity (embedding cosine similarity ≥0.85).
- FR3: A story is eligible to publish only if: (a) ≥2 independent Tier-2 sources agree on core facts, OR (b) ≥1 Tier-1 wire-service source reports it.
- FR4: If sources disagree on a key fact (e.g., figures differing >20%), the story is marked `flagged_conflict` and the summary must state "Reports differ on X" instead of picking a number.
- FR5: Stories uncorroborated after 45 minutes may publish with a visible single-source disclaimer rather than being held indefinitely.

### 5.2 Summarization

- FR6: Summaries generated via LLM under a fixed system prompt: 3–5 sentences, ~60–85 words, 6th–8th grade reading level, no opinion language, no unsupported claims, structured claim-conflict handling.
- FR7: Every summary passes automated validation (word count, reading level, banned-word filter, LLM-judge fact-consistency check) before publish; failures route to the review queue, never silently auto-publish.
- FR8: Every published card stores and displays its source list with tap-through URLs.

**LLM system prompt (strict):**

```
You are a news summarizer for News Reels. Output ONLY valid JSON matching this schema:
{
  "headline": "string, at most 10 words, factual, no clickbait",
  "summary": "string, 3 to 5 sentences, 60 to 85 words",
  "category": "district|state|national|international|tech|science",
  "key_facts": ["short factual bullets drawn only from sources"],
  "conflicts": ["descriptions of numeric or factual disagreements, or empty"]
}

Rules:
- Reading level: 6th–8th grade. Short sentences. Common words.
- No opinion language (do not use: allegedly without attribution, shocking, devastating, slammed, blasted, hero, disaster unless quoting a source name+claim).
- No unsupported claims. Every sentence must be backed by the provided source texts.
- If sources disagree on a number by more than 20%, do not pick a number. Write: "Reports differ on <topic>."
- Do not copy source sentences verbatim. Paraphrase facts only.
- Do not invent names, figures, dates, or quotes.
```

### 5.3 Feed / Client

- FR9: Feed renders one story per full-screen card, vertical swipe navigation, category filter tabs.
- FR10: Users can save, share, and open the full source article from any card.
- FR11: After all unread stories for selected categories are seen, show a static "caught up" end state (no auto-refill loop).

### 5.4 Moderation

- FR12: Any story matching a sensitivity keyword list (deaths, unrest, elections, health emergencies) is force-routed to human review regardless of validation pass/fail.

---

## 6. Non-Functional Requirements

- **Cost:** MVP infra + API spend must stay within free tiers (GDELT, NewsData.io free tier, Gemini/Groq free tier, Supabase/Vercel free tier) — target $0–150/month.
- **Latency:** New verified stories should appear in-feed within 45–60 minutes of first source publication.
- **Reliability:** Validator failures must fail closed (route to review, never auto-publish on error).
- **Legal:** No reproduction of source text beyond short factual attribution; all cards link back to original sources.
- **Accessibility:** Minimum 6th–8th grade reading level is itself an accessibility feature; maintain WCAG-reasonable contrast in dark mode.

---

## 7. Assumptions & Risks

| Risk | Mitigation |
|---|---|
| Free API tiers too rate-limited at scale | Combine multiple free sources (GDELT + NewsData.io + RSS); revisit paid tier once usage data justifies cost |
| LLM hallucination slips through | Two-layer validation (rules + LLM-judge); human spot-check queue |
| District-level news is thin/unreliable | Supplement with official government RSS/press-release feeds |
| Verification delay vs. breaking-news speed expectation | Explicit "we're a few minutes behind, but verified" positioning; single-source disclaimer fallback after 45 min |
| Low seat permissions blocking tooling (e.g., Figma) | Confirmed separately — not a product risk, but track as an execution blocker |

---

## 8. Open Questions

1. Launch geography: single state/district first, or national + a pilot district simultaneously?
2. Do we require login/auth for MVP, or device-ID only (faster to ship, no save-across-devices)?
3. Sensitivity keyword list — who owns/approves it before launch?
4. Who performs human review during MVP — you solo, or do we need a second reviewer for coverage?
