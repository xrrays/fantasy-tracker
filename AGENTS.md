# Agent Context - Fantasy Hockey Dashboard

Maintained November 15, 2026. Applies to the whole repository. Keep this concise and current; never record credentials, real league/team identifiers, manager names or raw API responses here.

## Ownership and scope
- README.md belongs to the owner: do not edit without an explicit request.
- AGENTS.md is agent maintained. TODO.md is shared; preserve the owner's Requirements/Features wording. Keep its roadmap shallow.
- Preserve unrelated working changes, credentials and the ignored runtime cache. Never reset/delete the database to fix an import.
- Yahoo access is read-only. Do not send league mutations or contact other people.
- Owner-reported Yahoo support guidance permits this private, noncommercial, single-league friends dashboard and its cache. This is reported guidance, not a verified contract amendment. Do not reopen the same blanket permission objection. Revisit public/paid/mass distribution or contrary guidance.
- Hosting remains undecided and is not authorized. Keep both servers on loopback; the local guards are not hosted authentication.

## Structure and commands
- backend/: FastAPI HTTP layer, paced Yahoo adapter, normalization, pure analytics, SQLite cache, player periods, current/credited roster analysis, trade production, editorial publishing.
- frontend/src/: React/TypeScript views and shared components/production columns; plain CSS. Seven tabs: Home, Standings, Rosters, Transactions, Players, History, Editorial. Hash aliases preserve old links.
- scripts/discover_leagues.py: intentionally invoked live diagnostic; never run during tests or import into the server. Its output includes private identifiers; do not publish it.
- test/: offline unittest suite and explicitly synthetic preview server. No live Yahoo in test discovery.
- concept/: selected Flat Precision reference and branding. archive/: ignored prior designs, legacy CLI and unused artwork. These are local reference material, not required application code.
- docs/: current operations, architecture/privacy notes and review report. README remains owner controlled.
- data/: ignored SQLite cache, private manual/AI editions and diagnostics. Secrets remain separately in backend/keys.py and backend/oauth2.json, both ignored. Configure from backend/keys.example.py; OAuth provisioning is a separate owner step.
- From frontend: npm ci; npm run dev (API + UI on 127.0.0.1:8001 / 5174); npm run build; npm run preview (built UI only, API separately).
- Python setup: python -m venv .venv; .venv/Scripts/python.exe -m pip install -r backend/requirements.txt.
- Offline checks: .venv/Scripts/python.exe -m unittest discover -s test -p "test_*.py".

## Current shipped behavior
- Home: current scoreboard, Mon-Sun cumulative trends through yesterday, signed lead strip, season profile, record book and seven other matchups. Daily scores do not reconstruct live intraday history. Current-week live totals are a separate source.
- Standings: official record/PF/PA plus completed-regular-season averages and all-play xWins. Missing values stay unknown. xWins sums weekly (opponents beaten + half ties)/opponents compared; it is descriptive, not a forecast. Schedule strength = average PA over the same complete weeks.
- Players: shared FAN PTS/FP-per-game/draft/production columns with individual Rosters, roster/NHL/position/availability filters and name search. SH% uses goals/shots times 100; GP aliases deduplicate; HIT/BLK follow SOG; TOI/GP is minutes:seconds. Excluded categories follow owner UI choices. Coverage is the loaded player pool, not the entire NHL universe.
- Rosters CURRENT: current players' entire selected-period production, including before acquisition and bench/IR. TOTALS rank uses total FP; AVERAGES uses FP per player. Four equal-height leader cards match the table and show total/average leaders.
- Rosters CREDITED: historical dated starting lineups, excluding bench/IR and pre-acquisition days while retaining former contributors. Averages use unique players who actually appeared. Top 100 and average positional ranks refer to team-player contributions. Individual team detail remains CURRENT mode and expands vertically.
- Credited import covers 47 closed dates and all 16 teams. All 752 team-day checks agree with Yahoo daily totals within 0.15; only 61/96 completed team-weeks agree with weekly scorecards. Six refreshed weekly scorecards were unchanged. The 35 weekly differences are unresolved, not assumed to be corrections or goalie minimums. Preserve the visible validation status; do not call this fully verified official weekly scoring.
- Transactions: full completed history with manager filters and independent 15-item pages. Best Pickups includes active spells (*), stops at ownership exits, and shows partial known sums with a dagger. Pickup/trade production is not starting-lineup credit; trade totals continue after subsequent moves. Trade receiving cards show each player's own signed production beside their name in a fixed right-aligned, tabular-number column, plus the large receiving-side total. Per-player sums reuse saved daily FP and share the same processed-date/yesterday window and partial-data markers. At narrower widths the player list spans the card below the heading/total to preserve readable names. Best Draft Picks compares pick to drafted-pool season production, with draft/current owners.
- Waiver Claims shows completed awards only. Sampled feed does not expose losing offers or historical priorities; do not invent these from current team priorities.
- History: current standings real; other seasons and brackets explicitly demo. Historical league keys have not been supplied/imported.
- Editorial: private monthly Jordog editions load from data/editorial/jordog/{league}/editions.json; validate full team coverage. They are not in frontend source or localStorage. DRAKE reads the newest two private, frozen weekly editions; publishing CLI never contacts Yahoo. Previously configured weekly Codex publishing is external to this repo and must be verified separately before relying on scheduling.
- Branding is RAY, solid charcoal with restrained orange. Editorial has an approved Vice City/Transformers theme exception. Preserve active layered assets, OVO chain, and no text obstruction; no em dashes in website text.

## Engineering and privacy boundaries
- Frontend never handles Yahoo credentials. Ordinary navigation/filter/sort reads reuse loaded data. Initial stale open/manual refresh can start one shared background job; no automatic upstream polling.
- One backend process owns OAuth refresh. Serialized GETs, two-second minimum spacing, 25-second timeout, paced 401 retry, 15-minute minimum pause on 429/999, 60-second refresh cooldown. Normal application budget is 900/day, not a verified Yahoo quota. Prior explicitly authorized bounded imports exceeded it; retain usage and resume ordinary fetching after reset, never silently reset counters or raise the normal ceiling.
- Cache survives restarts: normalized snapshot/checkpoints, daily player FP/stats, selected lineup slots, request usage. No raw responses or OAuth secrets in SQLite. It is rebuildable but expensive to recreate; back up private state deliberately before hosting/migrations. Seven-day request bookkeeping retention; other runtime data retained until owner clears it.
- Game-context stats fill GP/non-scoring categories; league FP remains authoritative when present. Older missing credited FP uses verified scoring modifiers; missing applicable categories remain unknown. NHL stat 33 is seconds and converts to minutes for aggregate TOI/GP.
- Explicit zero FP plus an entirely blank returned stat line normalizes counting stats to zero. Missing rows, partial lines, nonzero/unknown FP and undefined rates are not zero-filled. Keep this boundary tested.
- Local Host/Origin/header guards and no-store responses reduce browser-origin abuse; they do not authenticate league members. Do not expose Vite or the API to the internet.
- IDs are not passwords, but real configuration, monthly rankings and user data belong only in ignored runtime files. The local API must expose some IDs/data for this authorized UI; protect it with authentication before hosting. Do not claim old Git history or owner README was redacted.
- Keep fetch orchestration separate from pure metrics, persistence, HTTP and rendering. Avoid importing legacy archived code. No Redis/Celery/ORM/microservices needed at this size.

## Next work
1. Resolve credited weekly differences and daily/weekly trend discrepancies; confirm older stat-correction refresh policy and acquisition coverage before stronger accuracy claims.
2. Add CI, reproducible clean-environment checks, frontend interaction tests, response-contract validation and focused service/CSS refactoring.
3. Import validated historical keys and season/manager mappings; then add adjustable comparisons, rank history/VORP and deeper trade/scoring tools per owner priorities.
4. Select private hosting, member authentication, durable OAuth/cache ownership, backup/restore and background refresh before deployment. Current app is a useful local prototype, not production ready.
