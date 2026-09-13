# News Reels: Continuation Context

## Resume Objective

Continue the production-readiness acceptance loop from the current session. The required loop is:

1. Kill stale Python and Node processes that hold application ports.
2. Start the FastAPI API cleanly on port 8000.
3. Start the Expo web app cleanly on port 8081.
4. Run one fresh-user browser pass from onboarding through feed.
5. Reproduce and fix the first blocker found.
6. Rerun the same focused check and repeat the user journey until it is green.

Do not stop at unit-test success. Do not claim the journey works without executing it.

## Current Product State

- The reverse-geocoder root cause was an invalid/rejected LocationIQ credential.
- The implementation now defaults to free OpenStreetMap Nominatim.
- LocationIQ is optional only when a configured key is present.
- Reverse-geocode responses have a six-hour in-memory cache.
- `/health` checks database connectivity.
- `/ready` reports database and selected geocoder provider status.
- `/health/ingestion` reports the latest worker run.
- The mobile app has GPS permission handling and manual state/district fallback.
- Explicit feed category filters now remain truthful: selecting Local/District returns only district stories and no longer silently substitutes national stories when local coverage is empty.

## Verified Before This Context Was Written

- A live Delhi Nominatim reverse-geocode request returned HTTP 200 with real address data.
- API tests were reported green: 15/15 in the earlier focused run.
- Worker tests were reported green: 51/51 in the earlier run.
- The remaining unproven area is a clean browser onboarding and persistence pass with the API and Expo app continuously available.

## Runtime Status

The stale API listener was replaced during the latest verification pass. The current API process is running from `apps/api` on port 8000 and has been verified with `/health` and `/ready`; `/ready` reports `geocoder_provider: nominatim`. The Expo web app is running on port 8081 and the persisted feed loads successfully.

Windows shell/process management remains a maintenance concern: use a clean noninteractive shell and inspect the owning process before starting another server. A shared browser page exists at `http://localhost:8081/`; use `?reset=1` for a genuine fresh-user pass.

## Immediate Next Actions

1. Inspect port owners for 8000 and 8081 using a noninteractive command. Do not answer stray `Y`/`N` prompts as PowerShell commands.
2. Terminate only stale Python/Node/Expo/Uvicorn processes associated with this local project; preserve unrelated user processes where possible.
3. Start the API in a fresh terminal and verify with `GET /health` and `GET /ready`.
4. Start Expo web and verify the page loads at `http://localhost:8081/?reset=1`.
5. Use browser interaction to complete manual onboarding first, because it is deterministic in a browser. Then test GPS/error fallback if the platform exposes it.
6. Reload without reset and verify persisted onboarding state.
7. Record any failure with the exact screen, request, status, and root cause before editing.

## Relevant Files

- `apps/api/app/main.py`
- `apps/api/app/routers/location.py`
- `apps/api/app/routers/feed.py`
- `apps/api/tests/test_health.py`
- `apps/api/tests/test_location.py`
- `apps/mobile/App.tsx`
- `apps/mobile/src/api.ts`
- `apps/mobile/src/screens/LocationScreen.tsx`
- `apps/mobile/src/screens/InterestsScreen.tsx`
- `apps/mobile/src/screens/CategoryOrderScreen.tsx`
- `apps/mobile/src/screens/FeedScreen.tsx`
- `docs/PRD.md`
- `docs/PROGRESS.md`

## Safety and Cost Constraints

- Do not expose or copy secrets from `.env` into this file, chat, commits, screenshots, or logs.
- Do not introduce paid APIs, paid AI providers, paid maps, paid infrastructure, or paid services.
- Keep Nominatim plus manual location selection as the free fallback path.
- Do not modify tests merely to make a failing implementation pass.

## Resume Prompt

> Read `docs/AI_PROJECT_HANDOFF.md` and this file. Continue the News Reels production-readiness loop. First stabilize ports and start the API and Expo web app in clean noninteractive shells. Then execute a fresh-user browser journey at `http://localhost:8081/?reset=1`. Fix the first reproducible blocker at its root cause, run focused validation, and repeat until onboarding, feed loading, and persistence are verified. Never expose `.env` secrets and never claim success without executing the journey.
