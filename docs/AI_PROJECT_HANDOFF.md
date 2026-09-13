# News Reels: AI Project Handoff

## Mission

News Reels is a free-tier-first mobile news product for India. It presents verified, plain-English news summaries in a vertical feed, organized from district and state news through national, international, tech, and science stories.

The product must be validated as a real user would use it. Passing unit tests is necessary but not sufficient. Always run the app, follow the onboarding journey, and fix the first real blocker before claiming the flow works.

## Repository Map

- `apps/api`: FastAPI backend, SQLAlchemy models, Alembic migrations, feed/location/admin routes, API tests.
- `apps/mobile`: Expo React Native app, also runnable as a web app for browser acceptance testing.
- `apps/worker`: ingestion, clustering, verification, summarization, validation, and worker tests.
- `packages/shared`: shared TypeScript package.
- `docs/PRD.md`: product requirements and acceptance intent.
- `docs/PROGRESS.md`: implementation history and completed work.
- `docker-compose.yml`: local Postgres and Redis services.

## Product Requirements That Matter During Testing

1. A new user can choose a state and district, using GPS or manual fallback.
2. A new user can select interests and arrange category priority.
3. Completing onboarding persists preferences locally and opens the feed.
4. The feed shows verified cards, source information, category, location relevance, and fallback/empty states.
5. Users can save/share/open the original source where those controls exist.
6. The app must fail clearly and recover gracefully when GPS, the API, or a provider is unavailable.
7. No paid API, paid infrastructure, or paid provider may be introduced. Keep free providers and manual fallbacks working.

## Important Current Implementation

### API

- `apps/api/app/main.py` exposes `/health`, `/ready`, and `/health/ingestion`.
- Feed routes are in `apps/api/app/routers/feed.py`.
- Reverse geocoding is in `apps/api/app/routers/location.py`.
- OpenStreetMap Nominatim is the default reverse-geocoder.
- LocationIQ is optional and is used only when `LOCATIONIQ_API_KEY` is configured.
- Reverse-geocode results are cached in memory for six hours.

### Mobile

- `apps/mobile/App.tsx` controls boot, location, interests, priority, and feed gates.
- `apps/mobile/src/screens/LocationScreen.tsx` supports GPS and manual selection.
- `apps/mobile/src/api.ts` selects the API URL from `EXPO_PUBLIC_API_URL`, browser hostname, or `127.0.0.1`.
- The web app normally runs at `http://localhost:8081/`; the API normally runs at `http://localhost:8000/`.
- Add `?reset=1` or `?onboard=1` to the web URL to clear local onboarding state and force a fresh-user pass.

## Runtime Rules

- On Windows, stale Python/Node processes frequently hold port 8000 or 8081. Inspect listeners before starting another server.
- Use a clean, noninteractive shell where possible. Avoid commands that trigger PowerShell execution-policy confirmation prompts.
- Start the API from `apps/api` with the repository virtual environment when available:

```powershell
Set-Location 'D:\News\apps\api'
& 'D:\News\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Start the mobile web app from `apps/mobile`:

```powershell
Set-Location 'D:\News\apps\mobile'
npm run web -- --port 8081
```

- Never print, paste, commit, or place credential values in documentation. Read variable names from `.env` only when needed, and redact values in reports.

## Validation Expectations

Run focused checks after each change, then broaden only as needed:

```powershell
Set-Location 'D:\News\apps\api'
& 'D:\News\.venv\Scripts\python.exe' -m pytest tests -q

Set-Location 'D:\News\apps\worker'
& 'D:\News\.venv\Scripts\python.exe' -m pytest tests -q
```

For the real user journey, use the browser tools or a browser manually:

1. Open `http://localhost:8081/?reset=1`.
2. Confirm the location screen appears.
3. Test manual location selection and continue.
4. Select interests and continue.
5. Reorder/select priorities and finish onboarding.
6. Confirm the feed loads from the API.
7. Reload without `reset=1` and confirm onboarding does not repeat.
8. Exercise API failure or empty-feed states only after the happy path is observed.

## Working Style for the Next AI

- Start from the smallest concrete failing behavior.
- Form one local hypothesis and one cheap check before editing.
- Make the smallest root-cause fix.
- Run a focused executable validation immediately after the first edit.
- Do not weaken, delete, or rewrite tests to hide failures.
- Do not undo unrelated user changes in a dirty worktree.
- Keep the user informed about runtime blockers and distinguish code defects from local environment problems.
- Do not claim production readiness until the fresh-user browser flow has actually completed.
