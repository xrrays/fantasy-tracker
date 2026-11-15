# Local Operations

The owner maintains README.md; this is the implementation-maintained setup guide.

## Fresh checkout
1. Create a Python virtual environment: `python -m venv .venv`.
2. Install `backend/requirements.txt` using that environment's Python.
3. Copy `backend/keys.example.py` to ignored `backend/keys.py` and enter your league key and optional favorite team key.
4. Place the owner's approved Yahoo OAuth configuration in ignored `backend/oauth2.json`. Never put it in frontend/public or commit it. A fresh clone does not provision Yahoo approval or account authorization.
5. Run `npm ci` from frontend, then `npm run dev`. UI binds to 127.0.0.1:5174 and API to 127.0.0.1:8001. An existing API is reused; stopping this launcher only stops a backend it started.

`npm run dev:ui` starts UI only. `npm run build` checks TypeScript/builds production files. `npm run preview` previews that build and requires the API separately. These commands run from frontend.

Run offline checks from root: `.venv/Scripts/python.exe -m unittest discover -s test -p "test_*.py"`. On Unix use `.venv/bin/python`. The synthetic preview is `python test/preview_dashboard.py --port 8002`; Vite must be explicitly configured to proxy that port. Never substitute demo data for real results.

## Private state
The SQLite cache and manual/AI editorial editions live under ignored data/. They survive restarts and are not in a clean checkout. Copy these only through an owner-approved private backup. Stop the API before copying the database, or use SQLite backup facilities for a live copy. Credentials require a separate protected backup; do not store their values in logs or database exports.

Monthly Jordog editions are JSON month-to-team-key arrays at data/editorial/jordog/{league}/editions.json; every edition must rank each team exactly once. DRAKE context/publish commands are `python -m backend.editorial context` and `python -m backend.editorial publish path/to/draft.json`; they read the cache only. Publishing does not itself schedule anything.

The request budget is an application safeguard, not Yahoo's documented quota. Paused imports resume from retained facts. Do not clear the database or counters to restart an import. The API is read-only upstream; local POST refresh endpoints coordinate cache work.

## Privacy and deployment
The browser receives authorized league data from the local API, including identifiers needed for interaction. Loopback binding and browser-origin guards are not member authentication. Do not publish the development servers. Hosting needs authenticated access, HTTPS, protected/durable OAuth ownership, persistent cache and operational backup/restore.

## Source map
backend/server.py: local HTTP and guards; service.py: orchestration; yahoo_client.py: pacing/auth/backoff; normalize.py: whitelisted responses; cache.py: persistence; analytics/player_periods/roster_analysis/credited/trade_analysis: metrics; editorial.py: local publishing. frontend/src contains views, shared table/column helpers, types and CSS. scripts contains intentional live diagnostics; test contains offline checks and synthetic preview; concept contains active design references; ignored archive preserves superseded work.
