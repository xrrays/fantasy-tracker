# Fantasy Hockey Dashboard — agent context and project state

Last maintained: November 8, 2026. Applies to this entire project. Read before working and update the state/next-step sections after substantial changes. Keep current decisions rather than appending a session diary. Never record credential values here.

## Current project state and working conventions

- The dashboard has a minimal frontend shell; league content, visuals, analytics, and backend server remain unimplemented. Keep proposed features below distinct from shipped behavior.
- `backend/main.py` is the moved legacy CLI/settings script. It supports `python -m backend.main` and direct execution. `backend/__init__.py` has no network side effects, but `backend/main.py` still does; do not import the latter into a server or a test.
- `backend/keys.py` contains the configured league key. `backend/oauth2.json` stores the approved Yahoo credentials and mutable OAuth state. Both remain ignored; resolve credentials from the backend directory, not the launch directory.
- `test/test.py` is the moved manual league-discovery diagnostic, not an automated test. Future backend tests belong under `test/` and must use mocked Yahoo calls/sanitized fixtures by default. Live diagnostics require an intentional invocation.
- `frontend/` now contains a React + TypeScript + Vite app with five hash-linked pages: Home, Teams, Players, History, Columns. Each page contains only its heading and a neutral placeholder. Navigation is client-side, supports direct hash links and browser history, and includes a responsive header and keyboard focus styles. Per the owner, do not add league content, charts, main visuals, or nonfunctional selectors/Refresh controls at this stage. Dependencies are pinned in package.json/package-lock.json; no router/query/chart library is installed. The formerly referenced `frontend/mockups/PROMPTS.txt` is absent; do not assume it still exists. The selected mockup is `concept/02-flat-precision.png`. Previous rounds and generation notes are preserved locally under ignored `archive/round-1/`, `archive/round-2/`, and `archive/round-3/`; do not assume those archived files are available in a fresh clone. Mockups are raster images, not a working web application.
- File ownership: `README.md` is owner-edited; do not change it unless explicitly asked. `AGENTS.md` is agent-maintained. `TODO.md` is shared: maintain a shallow broad roadmap, and leave the Requirements section for the owner to write; do not populate or rewrite that section unless explicitly asked. Keep implementation details in this file rather than expanding TODO into a task backlog. `TODO.md` replaces the former `TODO.txt` roadmap (the latter was already absent when TODO.md was created).
- The owner is considering a private hosted dashboard for roughly 16 league members and prefers free hosting. Hosting is being evaluated, not selected or authorized for deployment. Local development remains the starting point; a Windows launcher is a prior proposal whose priority should be revisited with the owner-written requirements.
- Confirmed visual direction: lifted black/charcoal, white/gray text, and SPARSE orange accents only. Use solid fills, no gradients, sharp professional typography, proper Title Case headings, and minimal modular cards. No slogans, quirky marketing copy, large orange number walls, accent-filled ribbons, or unnecessary widgets. The owner selected Round 3/02 Flat Precision as the visual direction, now at `concept/02-flat-precision.png`. Use it as the implementation reference. Exact font and mobile treatment remain open.
- Branding/header: supplied orange logo beside large `THO-RAY`, smaller `Fantasy Hockey League` underneath; top navigation exactly Home / Teams / Players / History / Columns, followed by a team selector and Refresh. Team selection changes Home. Knies Your Beak Fam is the initial favorite, not the only selectable team. Retain season/week controls; no separate Charts or Rankings top-level tab is currently requested.
- Home priorities: four main groups, arranged as Round 2/01: wide current matchup at left, season profile beside it, season record book below those two, and Around the League on the right with seven other matchups. Keep one Mon–Sun cumulative scoring graph. Replace the duplicate daily two-team points table with a compact signed lead/deficit strip (positive = selected team ahead, negative = behind); this is the current design interpretation of the owner's feedback. No extra League Pulse/standings/column cards in Round 3; reduce clutter and leave depth to other tabs. Daily team-credited data and Biggest Comeback require separate validation; current weekly totals do not reconstruct earlier daily leads.
- The owner completed `TODO.md` Requirements/Features. Priority group 1: snappy menus, live week scores and daily trends, sortable standings/basic team metrics, adjustable charts, Jordog Power Rankings, total six-year history, and mobile support. Group 2: deeper history, AI column, player/VORP and roster analysis, trade/value tools and polls, draft/manager data, and scoring what-if tools. Group 3: MCP and Discord integration. Preserve the owner's wording and priority groups; availability and scope of these features are not yet validated.
- Six-year history is requested. The owner will supply historical league keys later. Design season-aware models with manager mapping and scoring comparability; actual historical coverage is not yet validated.
- Selected concept: `concept/02-flat-precision.png` (Round 3/02, Flat Precision), 1774 × 887 (2:1). All other round images and design notes were moved into project-root `archive/`, which is ignored by Git. `concept/reference/thoray-logo.png` remains an active branding asset. Target responsive production layouts with desktop checks at 1440 × 900 and 1920 × 1080 plus mobile, rather than hardcoding image dimensions. Faint shading in the generated image is not an approved gradient style; use solid fills in implementation. All mockup data is illustrative.
- Snappy interaction is a first-release requirement: reuse loaded season data for navigation and common filters, retain browser query state/cache across views, and refresh Yahoo data separately in the background. Shared backend caching and coordinated refresh must avoid a Yahoo fetch per page/filter change or per viewer. Timing targets still need agreement and device testing.
- There is no Python dashboard backend server, launcher, or local fantasy database yet. The frontend dev/preview server binds to 127.0.0.1:5174 with strict port selection. Future runtime data should be ignored under `data/`.
- The old `DASHBOARD_PLAN.md` was consolidated into this file. `DISCORD_AGENT_HANDOFF.md` was deleted at the owner's request after delivery. The other agent owns the sibling Discord project; avoid edits there without coordination.
- Preserve existing local/user changes. Do not delete credentials, cache data, or unrelated files. All Yahoo league actions in this dashboard are read-only.
- Keep Yahoo fetching, response normalization, pure analytics, storage, and HTTP/UI rendering separate. Share calculations with Discord through a small coordinated module later; do not make the bot depend on this laptop running.

### Current commands and verification

From the fantasy project root:

```powershell
python test/test.py       # intentional live Yahoo league lookup
python -m backend.main   # intentional live Yahoo settings inspection
```

Frontend commands (run from `frontend/`):

```powershell
npm ci             # install pinned dependencies on a fresh checkout
npm run dev        # http://127.0.0.1:5174/
npm run build      # TypeScript check and production build
npm run preview    # serve built frontend locally, dev server must be stopped first
```

Frontend validation: TypeScript check and Vite production build passed, and Vite reported ready on the selected port. Local HTTP verification was blocked by socket access permissions and the companion browser timed out, so visual and interactive browser verification remains outstanding. No Yahoo requests are made by this shell.

Required existing Python dependencies: `yahoo-oauth`, `yahoo-fantasy-api`, `tabulate`. Use a project virtual environment when building the server. Do not add an automatic live Yahoo call to test discovery.

Organization was checked with Python AST parsing and mocked script execution from multiple working directories, including module/direct backend invocation and the manual diagnostic. Credentials were moved without content changes and ignore rules checked. Live API calls are not needed to verify file organization.

## Technical direction — proposal, not implementation

- **Languages:** Python for data access, normalization, analytics, and backend; TypeScript for the React frontend; SQL for a small local cache.
- **Backend:** FastAPI + Pydantic + Uvicorn. Use synchronous handlers or a worker thread for the existing synchronous Yahoo wrapper, with explicit timeouts and one serialized credential-refresh owner.
- **Frontend:** React + Vite + TypeScript; plain CSS with shared tokens and responsive layouts. Recharts is the recommended chart library for score trends, PF/PA scatterplots, and comparisons. Add router/query libraries only if real navigation and refresh complexity justify them.
- **External API:** approved Yahoo Fantasy Sports REST API through `yahoo_oauth` and `yahoo_fantasy_api`, supplemented by small GET-only adapters for missing fields. No additional hockey API is required for the league-first release.
- **Internal API:** versioned JSON endpoints such as `GET /api/v1/league`, `/standings`, `/matchups?week=...`, `/analytics?through_week=...`, `/teams/{team_key}`, and `/records`; `POST /api/v1/refresh` refreshes the local cache only, never mutates the Yahoo league. Model responses with Pydantic and expose data freshness/coverage.
- **Persistence:** SQLite through Python's standard `sqlite3` module initially, with a few explicit tables and schema migrations. It is a rebuildable cache of Yahoo data, not the authority for league results. Retention policy must be established before permanent snapshots/exports.
- **Delivery:** local Windows browser app first. During development, Vite and FastAPI run separately using dedicated ports (proposed 5174/8001 to avoid Mailroom). Later serve the built frontend from FastAPI for a single local origin and simpler launcher. Bind locally until a deliberate hosting decision.
- **Testing:** Python `unittest` for metrics/parsing/cache/auth behavior; frontend Vitest + React Testing Library when implemented; a small browser smoke test once a real dashboard exists. Pin actual dependencies after compatibility validation rather than choosing speculative version numbers now.
- **Scale:** a single backend process and local SQLite are sufficient for one 16-team league. Do not introduce Redis, Celery, microservices, containers, an ORM, or a separate Node backend without a demonstrated need.

Official technology references: [FastAPI](https://fastapi.tiangolo.com/), [Vite](https://vite.dev/guide/), [Recharts](https://recharts.github.io/en-US/), [SQLite usage guidance](https://www.sqlite.org/whentouse.html).

### Next intended work

The requested placeholder shell is complete. On the next content request, use the selected Flat Precision mockup at `concept/02-flat-precision.png` to derive the implementation design and mobile layout; keep placeholders until content is authorized. Use the completed Requirements/Features section in TODO.md as the owner's priorities; settle metric definitions, daily-score availability, six-year keys/coverage, editorial ownership, and hosted delivery before treating them as verified contracts. Before durable storage or sharing with league members, review the signed Yahoo agreement's applicable permissions. Then extract a Yahoo client with durable refresh state, collect sanitized response fixtures, normalize season-aware league data, and implement pure analytics. Scaffold FastAPI and React around verified contracts with navigation/filtering separated from Yahoo refresh. Production screens must use verified data.

The remaining sections preserve discovery, product vision, metrics, and scope notes from the original dashboard plan. Where those older proposals differ from the current state above or owner-written TODO.md requirements (navigation, history priority, local launcher, palette), the current decisions and owner requirements take precedence.

## Direction

Build a browser application for understanding **the whole league**, with **Knies Your Beak Fam** as the owner's initial selected team and all teams selectable. The emphasis is on explaining performance: who is scoring well, who is benefiting from their schedule, and which matchups and records stand out. Player and roster analysis belong in the eventual product, but should follow a reliable league dashboard.

Use Mailroom's launch-and-view model: a Windows launcher opens a React interface backed by a local Python server. Treat hosting as a later deployment option, rather than an initial dependency.

## Confirmed starting point

- Yahoo confirmed API access was live in its September 14 email. The user subsequently ran successful league discovery and settings requests on October 4.
- Active league: `477.l.5599`; numeric league ID: `5599`; game: NHL; Yahoo season: `2026` (2026–27 hockey).
- League name: **Land On My Pont**. The supplied settings identify 16 teams, H2H Points, daily rosters, four divisions, eight playoff teams, playoff start week 24, and season end week 26. These are initial observations, not constants to hardcode.
- `backend/keys.py` contains the correct full league key.
- `backend/main.py` authenticates through `yahoo_oauth`, creates `yfa.Game(sc, 'nhl')`, and selects the league with `gm.to_league(LEAGUE_ID)`.
- The interactive menu exists but is commented out. The currently executed code prints league settings.
- No fantasy SQLite/database file or persistence layer was found in the fantasy project. Yahoo is the upstream data source; a local dashboard cache would be new. The Discord bot's PostgreSQL references are for blackjack, not evidence of an existing fantasy database.
- `backend/oauth2.json` and `backend/keys.py` are ignored by Git. Never include credential values in this file, the frontend, fixtures, or agent messages.

### What the existing code already computes

Current scoreboard; points-for and points-against leaderboards; deviations from the league's average cumulative PF/PA; average net matchup margin; official rank versus PF rank; lowest weekly score; largest blowout; closest non-tied matchup; highest losing score.

These are a useful analytics starting point, but the functions print terminal text and fetch their own data. They need conversion into calculations returning structured values, separate from Yahoo fetching and UI rendering.

### Evidence boundary

On November 8, 2026, an intentional authenticated check through the existing Python OAuth flow successfully fetched settings, all 16 standings entries, and all eight current-week matchups for Land On My Pont. Yahoo reported week 6 with matchups in progress. Current access is verified as of that check; this does not validate restart durability or every field/endpoint. Win/loss/tie values were not present at the top-level keys requested by the diagnostic; inspect the actual nested response before modeling records, rather than treating absent fields as zero. No fixtures were saved.

Additional capabilities below are documented or present in installed library code, not yet verified for every field in this NHL league. Earlier GET probes returned HTTP 401 when bypassing refresh; the successful authenticated check supersedes that as the latest connectivity evidence. Fresh authenticated endpoint sampling remains an implementation gate for the other resources.

## Yahoo data inventory

Yahoo's current [API reference](https://sports.yahoo.com/developer/docs/) documents these read resources:

- **Game:** season metadata, calendar, fantasy-week dates, available stat categories, and positions.
- **League:** settings, scoring weights, standings, current or selected-week scoreboard, teams, eligible players, draft results, and completed transactions.
- **Team:** metadata, division, managers, stats/points, standings, dated roster selections, draft picks, and H2H matchups.
- **Player:** identity, NHL team, images, positions, stats, league ownership, global ownership percentage, and draft analysis.
- **User:** the authenticated account's games, leagues, and teams.

Representative paths under `https://fantasysports.yahooapis.com/fantasy/v2`:

- `league/477.l.5599/standings`
- `league/477.l.5599/scoreboard;week=1`
- `league/477.l.5599/settings`
- `league/477.l.5599/teams`
- `team/{team_key}/roster;date=2026-10-04`
- `league/477.l.5599/draftresults`
- `league/477.l.5599/transactions`
- `game/477/stat_categories`

Use league context for league-specific player points. Return fields depend on sport, scoring system, coverage period, and permissions. A roster's player production is distinct from points actually credited to its fantasy team.

### What our Python wrapper makes convenient

The [wrapper documentation](https://yahoo-fantasy-api.readthedocs.io/en/latest/yahoo_fantasy_api.html) provides `settings()`, `standings()`, `matchups(week)`, `teams()`, `stat_categories()`, `positions()`, `team_key()`, `to_team(key).roster(day=...)`, `player_details()`, `player_stats()`, `ownership()`, `percent_owned()`, `free_agents()`, `waivers()`, `draft_results()`, and `transactions()`.

Inspect the installed code when documentation and behavior differ. Its NHL player-stat week parameter is documented as NFL-only: plan on daily data and Yahoo week boundaries for NHL aggregates. The local wrapper batches player-stat requests in groups of at most 25. Its `settings()` parser intentionally removes roster positions and stat categories, so the short settings dump does not represent everything Yahoo supplies. Fetch categories/positions separately or use a small GET-only adapter for fields the wrapper omits.

The installed `league.py`, `team.py`, and `yhandler.py` were inspected for these details. Upstream references: [league implementation](https://github.com/spilchen/yahoo_fantasy_api/blob/master/yahoo_fantasy_api/league.py), [team implementation](https://github.com/spilchen/yahoo_fantasy_api/blob/master/yahoo_fantasy_api/team.py).

### Hockey statistics to expose

The installed wrapper's NHL mappings include skater games played, goals, assists, NHL points, plus/minus, penalty minutes, power-play goals/assists/points, game-winning goals, shots on goal, and shooting percentage. Goalie mappings include starts, wins/losses, goals against, GAA, shots against, saves, save percentage, shutouts, and minutes.

These are available mapping definitions, not a promise that every field arrives for every request. Hits, blocks, other league-specific categories, and their exact labels should be resolved from the game's live categories and the league's modifiers. Some advanced-stat names exist in the old static mapping, but their existence in code is not evidence of current API delivery.

For this points league, the useful display is both the raw stat and its fantasy contribution: for example, goals, goal weight, and points earned from goals. The supplied settings already contain 13 weighted stat IDs. Resolve all 13 against live categories rather than copying generic hockey scoring rules. Separate NHL points (goals plus assists) from league fantasy points in every chart and column.

### Scope and data limits

Yahoo's [current access page](https://sports.yahoo.com/developer/access/) says Fantasy Sports API access currently provides reads only. Older reference examples describe write operations; those examples do not establish write permission for this application.

Do not promise NHL play-by-play, a complete NHL game schedule, shift-level data, starting-goalie confirmation, injury news articles, chat history, private waiver bids, premium projections, or real-time push updates from these endpoints. Some extra player fields may exist, but projections, detailed news, and advanced hockey metrics need specific validation before they become product requirements. A future schedule/streaming tool may need a separately researched NHL data source.

Historical league keys are discoverable, but access, completeness, scoring comparability, and manager identity across seasons must be checked. Previous season `465.l.16818` is a strong first candidate: the current settings' renewal field points to it. Do not assume every returned key is NHL; the supplied league lookup list contains mixed game keys.

## Proposed dashboard

### 1. Overview — first screen

Show the league name, season and week selector, data freshness, and one clear Refresh action. Keep the league scoreboard prominent: all eight matchups, scores, margins, and live/final status. Highlight Knies Your Beak Fam with an understated accent and a quick link to its team detail.

Below it, show sortable standings with record, division, PF, PA, differential, and PF rank. Include concise insights such as highest score this week, closest matchup, and strongest completed-week scoring trend. Each insight should link to the underlying teams/week and say whether it is provisional.

Default to the selected current week for the scoreboard and completed regular-season weeks for comparative analysis. Let the user deliberately include the current week or playoffs.

### 2. Performance and luck — primary differentiator

Show PF versus PA as a scatterplot, with team names on hover and the user's team marked. Plot weekly scoring against the league mean. Provide standings-rank versus scoring-rank comparison, all-play standings, and actual results versus expected matchup wins.

Useful questions: Is a high-ranked team actually strong? Is a low-ranked team repeatedly facing excellent opponents? Which teams are improving? How much of a record is explained by the schedule?

Do not treat all rank differences as proof of luck: division/seeding rules and ties also influence official rankings. Use all-play as the clearer descriptive schedule comparison.

### 3. Teams and comparisons

Every team gets a detail view: record, points, weekly trend, opponent history, matchup margins, roster, and scoring contribution breakdown when validated. The user's team is the default favorite, but every team remains selectable.

A two-team comparison should line up scores, all-play results, consistency, head-to-head history, and roster production. Prefer stable team keys for identity; team names can change.

### 4. Records and history

Adapt the current records code and add highest weekly score, highest combined matchup score, winning/losing streaks, and repeated bad beats. Every record includes the week, both relevant teams, values, and a link back to its matchup.

Design for current and historical seasons from the start. Validate/import historical league keys when the owner supplies them; retain the previous renewed season as a first candidate, not the complete history. Provide an explicit season selector. Cross-season comparisons should show scoring rules and format changes; do not combine incompatible raw scores into one leaderboard.

### 5. Players, rosters, and activity — next phase

Build a player explorer with position/team/owner filters, season and recent production, league-weighted points where validated, and free-agent/waiver status. Add draft results and a completed add/drop/trade timeline.

For roster contribution, distinguish all production by a player from production credited while started on a particular fantasy team. Bench-point and acquisition-value analysis require dated rosters plus daily stats, not just today's roster and season totals. Display injury/status codes as returned without implying they are detailed medical reports or news coverage.

Draft-value analysis can compare picks with observed production, clearly labeled retrospective. Keep future projections and playoff simulations out of the first release.

## Metric definitions and correctness

These are proposed calculations from Yahoo data, not statistics Yahoo directly returns:

- **Point differential:** PF minus PA for the selected coverage period.
- **Deviation from league mean:** a team's PF/PA minus the league mean for the same period. The existing code's 'average points' is this deviation, not points per week; rename it accordingly.
- **Average weekly points:** points over completed selected weeks divided by those weeks. Never divide by `current_week` when it includes an unfinished week.
- **Average net margin:** sum of finalized matchup margins divided by finalized matchups. Separately compute average winning margin and losing margin when those groups exist.
- **All-play record:** compare each team's finalized score with every other comparable team that week. With 16 teams, each gets 15 hypothetical W/L/T results per complete league week. Equal scores count as ties.
- **Expected matchup wins:** for each completed week, `(teams beaten + 0.5 × teams tied) / other teams compared`; sum over weeks. This is a historical schedule baseline, not a prediction.
- **Schedule-luck difference:** actual wins plus half actual ties, minus expected matchup wins. Positive means more standings results than the all-play baseline. If future league rules add a median game, adapt the definition rather than mixing the two records.
- **Consistency:** standard deviation of finalized weekly scores; pair with the mean and number of weeks. Suppress unsupported conclusions when the sample is small.
- **League-weighted player points:** use stat ID definitions and actual scoring modifiers, or Yahoo's returned league-context totals after verification. Map numeric stat IDs through categories; do not guess labels from the current settings dump.

Use matchup status and Yahoo's week date boundaries to identify completion. The current `current_week - 1` shortcut misses the final week once the season ends. Preserve current-week provisional values separately; recheck recent finalized results because stat corrections can change records. Separate regular-season, playoff, and consolation comparisons where necessary, and explicitly handle unequal participation.

Missing data is unavailable, not zero. Represent ties correctly in ranks and outcomes. Do not average save percentages or GAA by simply summing/averaging ratios; use their underlying totals if these metrics are added.

## Proposed implementation shape

Use React + TypeScript + Vite for the UI, Python + FastAPI for a local backend, and SQLite for a rebuildable cache and approved retained history. This matches familiar Mailroom tools; use separate ports and a separate data location so both applications can run together. The fantasy UI should have its own restrained hockey identity, not Mailroom's university branding.

One path through the app: browser → local backend → normalized league data and calculations → Yahoo adapter/cache. Only the backend handles credentials. Refactor calculation logic into importable Python functions so the Discord agent can later reuse the same definitions without scraping the website or importing the current network-active `main.py`.

Prefer a small shared module over a separate hosted service initially. The bot should not require the user's laptop to be running. If both applications run in different deployments, each needs its own writable token state or an explicitly selected common credential owner; avoid two processes competing to rewrite the same OAuth file.

Suggested local data groups: league/season configuration, teams, finalized matchups, daily rosters/player totals when needed, transactions/draft picks, and fetch timestamps. Keep secrets outside SQLite. Store only fields the product needs; omit manager emails, invitation links, chat identifiers, and private pending claims from UI payloads.

Treat caching/retention as a policy to settle against the signed Personal Use agreement before implementing permanent snapshots or exports. This planning pass has not reviewed that agreement's storage or redistribution clauses.

### Refresh and operational behavior

Start with fetch-on-open plus manual refresh, reuse one fetch for all consumers, and show the last successful fetch time. A configurable few-minute refresh while the page is open is a later option, not a promised Yahoo update interval. Avoid constant background work when the local app is closed.

Batch supported collection requests, honor pagination, use request timeouts, deduplicate simultaneous refreshes, and back off on throttling. No current numeric quota was verified, so do not encode an assumed requests-per-hour allowance. On outage, show cached data with a visible stale status. Distinguish expired authentication (401), authorization/permission failure (403), rate limiting (429), and unavailable data.

Manage token refresh centrally and persist refreshed fields atomically. Library initialization persists refreshed credentials, but the inspected request-time refresh helper updates the session without persisting the returned fields itself; a long-running backend needs to address that difference.

### Eventual hosting

Hosting evaluation as of November 8, 2026: Vercel supports FastAPI as well as frontend hosting, but its function filesystem is unsuitable for durable local SQLite or a mutable OAuth JSON file. A free hosted design would need external durable storage and refresh coordination across concurrent requests. Render Free can run the Python server, but sleeps after 15 idle minutes and loses local file changes on restart/redeploy/spin-down; persistent disks require paid compute. Supabase Free is a possible external Postgres/auth option, subject to quotas and low-activity pausing. These are researched candidates, not adopted dependencies; recheck official plan details when selecting a host. References: https://vercel.com/docs/frameworks/backend/fastapi , https://vercel.com/docs/functions/runtimes , https://render.com/docs/free , https://supabase.com/pricing .

The frontend could eventually use free static hosting, but authenticated Yahoo fetching still needs a backend. A private hosted deployment also needs secret storage, durable refresh state/cache, HTTPS, and access control for this private league. Do not commit to a provider/free tier until deployment is in scope and current costs/limits are researched.

The approval was for personal use. Confirm what the signed agreement permits before public hosting or distributing league data to other people through Discord. Private league membership and API authorization are separate from redistribution permission. Keep the current local dashboard scope while that is clarified.

## Build sequence and success checks

1. **Data validation and extraction:** sample refreshed GET responses for standings, scoreboard, teams, categories, roster, draft and transactions. Identify the favorite by team key; verify its name is Knies Your Beak Fam. Save sanitized minimal fixtures. Confirm historical NHL keys and correct week boundaries. Define storage/retention before creating a durable cache.
2. **Useful first release:** selected-team Home; sortable standings; live week scores and validated daily trends; performance/luck charts; season records; team details; editorial power rankings; validated six-year history and mobile support as requested in TODO.md group 1. Set delivery/access with the owner. Success means scores and standings agree with Yahoo, finalized metrics exclude partial weeks, token refresh survives a restart, and navigation/filter changes reuse loaded data.
3. **Roster and player depth:** daily roster-aware contribution; player explorer; free agents; draft and completed activity. Require evidence for missing fields and hockey-specific date support before shipping each analysis.
4. **History expansion and release:** expand deeper historical analysis after validating group 1 coverage, preserve compatible comparisons, and release through the selected private hosting approach. Windows launcher remains optional pending delivery choice.

Prioritize useful league analysis over replacing every screen Yahoo already has. At week 1, charts and records must acknowledge limited completed data rather than invent trends.

## Choices still open

- Flat Precision (Round 3/02) is selected; final font and mobile treatment remain open. Use solid charcoal surfaces and sparse orange, with no purple or gradients.
- Historical league keys will be supplied later; historical seasons are part of the intended product and data model from the start.
- Whether refresh is manual initially or automatic while open.
- Retention/redistribution scope in the signed agreement; private hosting for roughly 16 members, durable token/cache storage, member access, and acceptable free-tier delays. No provider has been selected. Bot deployment remains separate.

The main preference is settled: league-wide analysis first, slight emphasis on Knies Your Beak Fam, with roster/player analysis included in the eventual vision.
