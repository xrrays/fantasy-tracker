"""Shared normalized dashboard, with optional private SQLite persistence."""
import copy
import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .analytics import enrich_teams, records, biggest_comeback, pickup_spells, score_pickups
from .normalize import find, first, matchups, number, player, team
from .yahoo_client import YahooClient, YahooError
from .player_periods import aggregate_stats, zero_point_day, display_stats
from .editorial import load_editions, load_jordog
from .roster_analysis import roster_profiles
from .trade_analysis import trade_production, trade_windows
from .credited import credited_profiles, weighted_points, ACTIVE, INACTIVE


class DashboardService:
    def __init__(self, client=None, store=None, league_key=None):
        self.client = client or YahooClient()
        self.lock = threading.RLock()
        self.data = None
        self.running = False
        self.message = 'Ready to fetch Yahoo data.'
        self.error = None
        self.last_start = 0
        self.player_daily = {}
        self.player_daily_stats = {}
        self.daily_lineups = {}
        self.credited = {'profiles':{},'coverage':{},'reconciliation':{'checked':0,'matched':0}}
        self.transaction_head = None
        self.store = store
        if store and league_key:
            saved = store.load(league_key)
            if saved:
                self.data = saved['data']
                self.player_daily = saved.get('player_daily', {})
                self.player_daily_stats = saved.get('player_daily_stats', {})
                self.daily_lineups = saved.get('daily_lineups', {})
                self.transaction_head = tuple(saved['transaction_head']) if saved.get('transaction_head') else None
                self.message = 'Saved league data loaded. Missing work resumes in the background.'
                # Rebuild derived windows from retained daily facts after calculation changes.
                # This is local-only and never issues Yahoo requests during startup.
                if self.data.get('recent') and self.data.get('players'):
                    self._publish_recent_windows(max(int(n) for n in self.data['recent']),
                        [p['key'] for p in self.data['players']])
                self._publish_credited()

    def save(self):
        if self.store:
            with self.lock:
                self.store.save(self.data, self.transaction_head)

    def snapshot(self):
        with self.lock:
            updated = self.data.get('updated_at') if self.data else None
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(updated)).total_seconds() if updated else float('inf')
            incomplete = self.data and (not self.data.get('transactions_complete') or not self.data.get('pickups_loaded') or not self.data.get('players_loaded'))
            data = copy.deepcopy(self.data)
            if data:
                for p in data.get('players', []):
                    p['stats'] = display_stats(p.get('stats', {}), p.get('points'), data.get('stat_labels', {}))
                data['roster_profiles'] = {period:roster_profiles(data,period) for period in ('season','7','14','30')}
                data['trade_production'] = trade_production(data.get('transactions',[]),self.player_daily,self.today()-timedelta(days=1))
                data['credited'] = copy.deepcopy(self.credited)
            if data and self.store:
                data['drake_editions'] = load_editions(data)
                data['jordog_editions'] = load_jordog(data)
            if data:
                data['favorite_team_key'] = getattr(self, 'favorite_team_key', None)
            return {'data': data, 'running': self.running, 'message': self.message,
                    'error': self.error, 'requests': self.client.count, 'budget': self.client.budget,
                    'refresh_due': bool(self.data and (age > 300 or incomplete) and self.client.remaining > 40)}

    def start(self, days=None):
        with self.lock:
            if self.running:
                return False
            if days is None and time.monotonic() - self.last_start < 60:
                return False
            if days and not self.data:
                return False
            recent = self.data.get('recent', {}).get(str(days), {}) if days else {}
            if days and recent.get('end') == (self.today() - timedelta(days=1)).isoformat() and recent.get('complete', True) and 'stats' in recent and all(p['key'] in recent['stats'] for p in self.data.get('players', [])):
                return False
            self.running, self.error = True, None
            if days is None:
                self.last_start = time.monotonic()
            threading.Thread(target=self._run, args=(days,), daemon=True).start()
            return True

    def _run(self, days):
        try:
            if days == 'credited':
                from .keys import LEAGUE_ID
                self._credited(f'league/{LEAGUE_ID}')
            elif days == 'trades':
                from .keys import LEAGUE_ID
                self._trade_points(f'league/{LEAGUE_ID}')
                self.progress('Post-trade production is cached.')
            elif days:
                self._recent(days)
            else:
                self._refresh()
        except Exception as exc:
            with self.lock:
                self.error = str(exc) if isinstance(exc, YahooError) else 'Data could not be normalized; cached results were kept.'
        finally:
            with self.lock:
                self.running = False
            self.save()

    def progress(self, message):
        with self.lock:
            self.message = message

    @staticmethod
    def today():
        return datetime.now(ZoneInfo('America/Los_Angeles')).date()

    def _refresh(self):
        from .keys import LEAGUE_ID
        get = self.client.get
        prefix = f'league/{LEAGUE_ID}'
        self.progress('Fetching league settings and standings…')
        settings = get(prefix + '/settings', ttl=86400)
        raw = get(prefix + '/standings', ttl=300)
        teams = [team(t) for t in find(raw, 'team')]
        league = {'name': first(settings, 'name'), 'season': str(first(settings, 'season')),
                  'week': int(first(raw, 'current_week', first(settings, 'current_week', 1))), 'key': LEAGUE_ID}
        history = []
        previous_weeks = {}
        if self.data and self.data['league']['key'] == league['key']:
            for m in self.data['matchups']:
                previous_weeks.setdefault(m['week'], []).append(m)
        for week in range(int(first(settings, 'start_week', 1)), league['week'] + 1):
            self.progress(f'Fetching Week {week} matchups…')
            saved = previous_weeks.get(week, [])
            if week < league['week'] - 1 and len(saved) * 2 == len(teams) and all(m['status'] == 'postevent' and all(t['points'] is not None for t in m['teams']) for m in saved):
                history += saved
            else:
                history += matchups(get(prefix + f'/scoreboard;week={week}', ttl=300 if week >= league['week'] - 1 else 86400))
        enriched = enrich_teams(teams, history)
        stats = {}
        for s in find(get(f'game/{LEAGUE_ID.split(".")[0]}/stat_categories', ttl=86400), 'stat'):
            if 'stat_id' in s and 'display_name' in s:
                stats[str(s['stat_id'])] = s['display_name']
        fresh = {'league': league, 'teams': enriched, 'matchups': history, 'records': records(history),
                 'scoring_weights': {str(s['stat_id']):number(s['value']) for s in find(first(settings,'stat_modifiers',{}),'stat')},
                 'daily': [], 'daily_by_week': {}, 'pickups': [], 'pickups_loaded': False,
                 'players': [], 'draft': [], 'transactions': [], 'transactions_complete': False, 'recent': {},
                 'roster_owners': {}, 'rosters_loaded': False,
                 'stat_labels': stats, 'updated_at': datetime.now(timezone.utc).isoformat(),
                 'players_loaded': False, 'managers_loaded': False,
                 'coverage': ['Daily trend is checked against the official weekly score.',
                              'Manager acquisition value is not yet calculated from started-roster history.']}
        with self.lock:
            # Preserve separately fetched player data while refreshing the core view.
            if self.data and self.data['league']['key'] == league['key']:
                for k in ('players', 'draft', 'transactions', 'transactions_complete', 'players_loaded', 'managers_loaded', 'recent_pool', 'daily_by_week', 'pickups', 'pickups_loaded', 'roster_owners', 'rosters_loaded'):
                    if k in self.data:
                        fresh[k] = self.data[k]
                fresh['recent'] = self.data['recent']  # Retain requested windows so paused imports resume after restart.
                fresh['daily'] = fresh['daily_by_week'].get(str(league['week']), [])
                comeback = biggest_comeback(history, fresh['daily_by_week'])
                fresh['records'].update(comeback=comeback['record'], comeback_covered=comeback['covered_matchups'])
            self.data = fresh
        self.save()
        # Closed days are stable enough to chart. Today's moving totals stay in the live scoreboard.
        self._daily_weeks(prefix, [m for m in history if m['week'] == league['week']])
        self._players_and_managers(prefix)
        self._rosters(prefix)
        self._trade_points(prefix)
        # The default recent period now fills automatically in the background.
        for window in sorted({7} | {int(k) for k in self.data.get('recent', {})}, reverse=True):
            self._recent(window)
        self._daily_weeks(prefix, history)
        self._pickups(prefix)
        self._full_player_stats(prefix)
        if self.daily_lineups:
            self._credited(prefix)
        if self.data['transactions_complete'] and self.data['pickups_loaded']:
            self.progress('Up to date. Tabs and filters use shared cached data.')
        elif self.client.remaining <= 30:
            self.progress('Season import paused at the local request budget. Loaded results are retained; refresh after the budget resets to continue.')
        else:
            self.progress('Loaded results are up to date; some daily pickup points remain unavailable.')

    def _daily_weeks(self, prefix, history):
        weeks = {m['week']: m for m in history if m.get('start') and not m.get('playoffs') and not m.get('consolation')}
        for week, matchup in sorted(weeks.items(), reverse=True):
            start = date.fromisoformat(matchup['start'])
            end = min(date.fromisoformat(matchup['end']), self.today() - timedelta(days=1))
            by_date = {d['date']: d for d in self.data['daily_by_week'].get(str(week), []) if d['date'] <= end.isoformat()}
            team_keys = {t['key'] for t in self.data['teams']}
            for offset in range((end - start).days + 1):
                day = (start + timedelta(days=offset)).isoformat()
                saved = by_date.get(day)
                if day < (self.today() - timedelta(days=3)).isoformat() and saved and all(saved['scores'].get(key) is not None for key in team_keys):
                    continue
                # Reserve room for user-requested player periods and acquisition data.
                if self.client.remaining <= 40:
                    self.progress('Daily-history import paused at the local request budget; loaded weeks remain available.')
                    self.save()
                    return
                self.progress(f'Loading Week {week} daily points: {day}…')
                response = self.client.get(prefix + f'/teams/stats;type=date;date={day}', ttl=86400)
                by_date[day] = {'date': day, 'scores': {first(t, 'team_key'): number(first(t, 'team_points', {}).get('total')) for t in find(response, 'team')}}
                with self.lock:
                    self.data['daily_by_week'][str(week)] = [by_date[d] for d in sorted(by_date)]
                    if week == self.data['league']['week']:
                        self.data['daily'] = self.data['daily_by_week'][str(week)]
            with self.lock:
                comeback = biggest_comeback(self.data['matchups'], self.data['daily_by_week'])
                self.data['records']['comeback'] = comeback['record']
                self.data['records']['comeback_covered'] = comeback['covered_matchups']
            self.save()

    def _daily_player_points(self, prefix, day, keys, require_stats=False):
        cache = self.player_daily.setdefault(day, {})
        stats_cache = self.player_daily_stats.setdefault(day, {})
        missing = sorted({key for key in keys if key not in cache or (require_stats and key not in stats_cache)})
        for i in range(0, len(missing), 25):
            batch_keys = missing[i:i+25]
            response = self.client.get(prefix + '/players;player_keys=' + ','.join(batch_keys) + f'/stats;type=date;date={day}', ttl=86400)
            values = {p['key']: p for p in (player(r) for r in find(response, 'player'))}
            cache.update({key: values.get(key, {}).get('points') for key in batch_keys})
            stats_cache.update({key: values[key]['stats'] for key in batch_keys if key in values})
            if self.store:
                self.store.save_player_day(prefix.removeprefix('league/'), day, {key: cache[key] for key in batch_keys})
                self.store.save_player_day_stats(prefix.removeprefix('league/'), day, {key: stats_cache[key] for key in batch_keys if key in stats_cache})
        return {key: cache.get(key) for key in keys}

    def _pickups(self, prefix):
        spells = pickup_spells(self.data['transactions'], self.today() - timedelta(days=1))
        with self.lock:
            self.data['pickups_loaded'] = False
            self.data['pickups'] = score_pickups(spells, self.player_daily)
        needed = {}
        for spell in spells:
            start = date.fromisoformat(spell['start'])
            for offset in range(spell['days']):
                day = (start + timedelta(days=offset)).isoformat()
                needed.setdefault(day, set()).add(spell['player'])
        for day, keys in sorted(needed.items()):
            # Completed player-days are retained across refreshes for this process.
            # Only missing pairs cost requests; stop gracefully instead of discarding progress.
            missing = set(keys) - set(self.player_daily.get(day, {}))
            if missing and (len(missing) + 24) // 25 > self.client.remaining - 20:
                return
            self.progress(f'Calculating points since pickup: {day}…')
            if missing:
                self._daily_player_points(prefix, day, keys)
            with self.lock:
                self.data['pickups'] = score_pickups(spells, self.player_daily)
            self.save()
        with self.lock:
            self.data['pickups'] = score_pickups(spells, self.player_daily)
            self.data['pickups_loaded'] = all(p['points_complete'] for p in self.data['pickups'])

    def _rosters(self, prefix):
        self.progress('Loading current fantasy rosters…')
        raw = self.client.get(prefix + '/teams/roster', ttl=300)
        entries = list(find(raw, 'team'))
        expected = {t['key'] for t in self.data['teams']}
        actual = {first(t, 'team_key') for t in entries}
        if not expected or actual != expected:
            raise YahooError('Current roster coverage is incomplete; previous ownership was kept.')
        owners = {first(p, 'player_key'): first(t, 'team_key') for t in entries for p in find(t, 'player')}
        known = {p['key'] for p in self.data.get('players', [])}
        missing = sorted(set(owners) - known - {None})
        for i in range(0,len(missing),25):
            response = self.client.get(prefix+'/players;player_keys='+','.join(missing[i:i+25])+'/stats;type=season',ttl=3600)
            with self.lock:
                self.data.setdefault('players', []).extend(player(p) for p in find(response,'player'))
        with self.lock:
            self.data.update(roster_owners=owners, rosters_loaded=True)
        self.save()

    def _trade_points(self, prefix):
        needed={}
        for tx,start,keys,days in trade_windows(self.data.get('transactions',[]),self.today()-timedelta(days=1)):
            for i in range(days):
                needed.setdefault((start+timedelta(days=i)).isoformat(),set()).update(keys)
        for day,keys in sorted(needed.items(),reverse=True):
            missing=set(keys)-set(self.player_daily.get(day,{}))
            if missing and (len(missing)+24)//25 > self.client.remaining-20:
                return
            if missing:
                self.progress(f'Loading production since trades: {day}…')
                self._daily_player_points(prefix,day,keys)

    def _publish_credited(self):
        if self.data:
            result=credited_profiles(self.data,self.daily_lineups,self.player_daily,self.player_daily_stats,self.today()-timedelta(days=1))
            with self.lock:
                self.credited=result

    def _credited(self, prefix):
        """Backfill once, then only missing closed dates/player-days. No Yahoo writes."""
        start=date.fromisoformat(min(m['start'] for m in self.data['matchups'] if m.get('start')))
        through=self.today()-timedelta(days=1)
        expected={t['key'] for t in self.data['teams']}
        weights=self.data.get('scoring_weights')
        if not weights:
            settings=self.client.get(prefix+'/settings',ttl=86400)
            weights={str(s['stat_id']):number(s['value']) for s in find(first(settings,'stat_modifiers',{}),'stat')}
            self.data['scoring_weights']=weights
        if not weights or any(v is None for v in weights.values()):
            raise YahooError('League scoring weights are unavailable; credited import paused.')
        game=prefix.split('/')[1].split('.')[0]
        for offset in range((through-start).days+1):
            day=(through-timedelta(days=offset)).isoformat()
            changed=False
            self.progress(f'Loading credited starting-lineup production: {day}…')
            if set(self.daily_lineups.get(day,{}))!=expected:
                if self.client.remaining<=40: break
                response=self.client.get(prefix+f'/teams/roster;date={day}',ttl=86400)
                teams=list(find(response,'team'))
                if {first(t,'team_key') for t in teams}!=expected:
                    raise YahooError('Historical lineup coverage is incomplete; previous data was kept.')
                rows={}; known={p['key'] for p in self.data['players']}
                for t in teams:
                    roster=first(t,'roster',{})
                    if first(roster,'date')!=day:
                        raise YahooError('Yahoo returned a different lineup date; import paused.')
                    entries=[]
                    for raw in find(roster,'player'):
                        p=player(raw);slot=first(first(raw,'selected_position',{}),'position')
                        if slot not in ACTIVE|INACTIVE:
                            raise YahooError('Historical lineup slot is unknown; import paused.')
                        entries.append({'player':p['key'],'slot':slot})
                        if p['key'] not in known:
                            with self.lock: self.data['players'].append(p)
                            known.add(p['key'])
                    rows[first(t,'team_key')]=entries
                self.daily_lineups[day]=rows
                changed=True
                if self.store: self.store.save_lineups(prefix.removeprefix('league/'),day,rows)
            keys=sorted({p['player'] for rows in self.daily_lineups[day].values() for p in rows if p['slot'] in ACTIVE})
            cache=self.player_daily_stats.setdefault(day,{})
            missing=[k for k in keys if '0' not in cache.get(k,{}) or self.player_daily.get(day,{}).get(k) is None]
            for i in range(0,len(missing),25):
                if self.client.remaining<=40:
                    self._publish_credited();self.save()
                    return
                batch=missing[i:i+25]
                changed=True
                response=self.client.get(f'game/{game}/players;player_keys='+','.join(batch)+f'/stats;type=date;date={day}',ttl=86400)
                fetched=[player(r) for r in find(response,'player')]
                values={p['key']:p['stats'] for p in fetched}
                groups={p['key']:p['group'] for p in fetched}
                for key,stats in values.items():
                    calculated=weighted_points(stats,weights,groups[key])
                    official=self.player_daily.get(day,{}).get(key)
                    if official is not None and calculated is not None and abs(official-calculated)>.011:
                        raise YahooError('Daily player scoring does not reconcile; credited import paused.')
                    cache[key]=stats
                    self.player_daily.setdefault(day,{})[key]=official if official is not None else calculated
                if self.store:
                    self.store.save_player_day_stats(prefix.removeprefix('league/'),day,values)
                    self.store.save_player_day(prefix.removeprefix('league/'),day,{k:self.player_daily[day].get(k) for k in batch})
            if changed:
                self._publish_credited();self.save()
        self._publish_credited()
        self.progress('Credited lineup production is saved.' if self.credited['coverage'].get('season',{}).get('complete') else 'Credited import paused at the local request budget; saved progress is retained.')

    def _full_player_stats(self, prefix):
        """Game context includes GP and non-scoring categories omitted by league stats.

        Keep league fantasy points unchanged; upgrade retained stats gradually.
        A marker distinguishes an inspected blank no-game day from old league data.
        """
        game = prefix.split('/')[1].split('.')[0]
        players = self.data.get('players', [])
        keys = [p['key'] for p in players]
        by_key = {p['key']:p for p in players}
        missing = [p['key'] for p in players if '0' not in p.get('stats', {})]
        for offset in range(0,len(missing),25):
            if self.client.remaining <= 40: return
            batch = missing[offset:offset+25]
            raw = self.client.get(f'game/{game}/players;player_keys='+','.join(batch)+'/stats;type=season', ttl=3600)
            with self.lock:
                for p in (player(r) for r in find(raw,'player')):
                    if p['key'] in by_key:
                        by_key[p['key']]['stats'].update(p['stats'])
            self.save()
        for offset in range(30):
            day=(self.today()-timedelta(days=offset+1)).isoformat()
            cache=self.player_daily_stats.setdefault(day,{})
            missing=[k for k in keys if '0' not in cache.get(k,{})]
            for i in range(0,len(missing),25):
                if self.client.remaining <= 40:
                    self._publish_recent_windows(30,keys)
                    return
                batch=missing[i:i+25]
                raw=self.client.get(f'game/{game}/players;player_keys='+','.join(batch)+f'/stats;type=date;date={day}',ttl=86400)
                for p in (player(r) for r in find(raw,'player')):
                    # GP=blank is retained as unavailable, never inferred from points.
                    cache[p['key']]={**cache.get(p['key'],{}),**p['stats']}
                    cache[p['key']].setdefault('0',None)
                if self.store:
                    self.store.save_player_day_stats(prefix.removeprefix('league/'),day,{k:cache[k] for k in batch if k in cache})
            self._publish_recent_windows(30,keys)

    def _transactions(self, prefix):
        """Page the season once, then refresh the newest pages until the known frontier.

        Incomplete backfills rewalk cached pages on the next explicit refresh. An
        end page (or a known frontier from a completed import) proves coverage.
        Normalized checkpoints persist when a store is configured; raw API pages do not.
        """
        previous = {tx['id']: tx for tx in self.data.get('transactions', [])}
        known = set(previous)
        was_complete = self.data.get('transactions_complete', False)
        seen = set()
        start = 0
        with self.lock:
            self.data['transactions_complete'] = False
        while True:
            if self.client.remaining <= 30:
                return
            self.progress(f'Loading season transactions: {len(previous)} moves collected…')
            path = prefix + f'/transactions;types=add,drop,trade;start={start};count=25'
            response = self.client.get(path, ttl=300 if start == 0 else 1800)
            entries = list(find(response, 'transaction'))
            ids = {first(tx, 'transaction_key') for tx in entries}
            if start == 0:
                head = tuple(first(tx, 'transaction_key') for tx in entries)
                if self.transaction_head != head:
                    # Inserts shift every page offset. Never combine a new head
                    # with stale cached offsets, which could silently skip moves.
                    self.client.invalidate(prefix + '/transactions;', except_path=path)
                self.transaction_head = head
            if entries and (None in ids or not ids - seen):
                raise YahooError('Transaction pagination did not advance; partial history was retained.')
            seen.update(ids)
            for tx in entries:
                identifier = first(tx, 'transaction_key')
                if first(tx, 'status') != 'successful':
                    continue
                changes = []
                for raw in find(tx, 'player'):
                    details = first(raw, 'transaction_data', {})
                    changes.append({'player': first(raw, 'player_key'), 'name': first(first(raw, 'name', {}), 'full'),
                                    'action': first(details, 'type'), 'source_type': first(details, 'source_type'),
                                    'source': first(details, 'source_team_key'), 'destination': first(details, 'destination_team_key')})
                previous[identifier] = {'id': identifier, 'type': first(tx, 'type'),
                                        'timestamp': first(tx, 'timestamp'), 'players': changes}
            complete = len(entries) < 25 or (was_complete and bool(ids & known))
            with self.lock:
                self.data['transactions'] = sorted(previous.values(), key=lambda tx: (int(tx['timestamp']), tx['id']), reverse=True)
                self.data['transactions_complete'] = complete
            self.save()
            if complete:
                return
            start += 25

    def _players_and_managers(self, prefix):
        get = self.client.get
        pool = {}
        for position in ('', 'D', 'G'):
            for start in ((0, 25) if not position else (0,)):
                self.progress('Fetching season player leaders…')
                path = prefix + f'/players;sort=PTS;sort_type=season;start={start};count=25'
                if position:
                    path += f';position={position}'
                for raw in find(get(path + '/stats;type=season', ttl=3600), 'player'):
                    p = player(raw)
                    pool[p['key']] = p
        draft = []
        for d in find(get(prefix + '/draftresults', ttl=86400), 'draft_result'):
            draft.append({'player': d.get('player_key'), 'team': d.get('team_key'),
                          'pick': number(d.get('pick')), 'round': number(d.get('round'))})
        self._transactions(prefix)
        transactions = self.data['transactions']
        keys = sorted(({d['player'] for d in draft} | {p['player'] for t in transactions for p in t['players']}) - set(pool) - {None})
        for i in range(0, len(keys), 25):
            self.progress(f'Fetching drafted and recently moved players ({i + 1}/{len(keys)})…')
            for raw in find(get(prefix + '/players;player_keys=' + ','.join(keys[i:i + 25]) + '/stats;type=season', ttl=3600), 'player'):
                p = player(raw)
                pool[p['key']] = p
        with self.lock:
            self.data.update(players=list(pool.values()), draft=draft, transactions=transactions,
                             recent_pool=list(pool), players_loaded=True, managers_loaded=True)
        self.save()

    def _recent(self, days):
        """Points and all daily stats over the same completed-calendar-day window."""
        from .keys import LEAGUE_ID
        with self.lock:
            keys = [p['key'] for p in self.data.get('players', [])] or list(self.data.get('recent_pool', []))
        end = self.today() - timedelta(days=1)
        totals = {key: 0.0 for key in keys}
        valid = {key: True for key in keys}
        if not keys:
            raise YahooError('Wait for the season player pool to load.')
        completed = True
        for offset in range(days):
            day = (end - timedelta(days=offset)).isoformat()
            for i in range(0, len(keys), 25):
                self.progress(f'Loading {days}-day points: {day}, batch {i // 25 + 1}…')
                batch_keys = keys[i:i + 25]
                missing = {key for key in batch_keys if key not in self.player_daily.get(day, {}) or key not in self.player_daily_stats.get(day, {})}
                if missing and self.client.remaining <= 20:
                    completed = False
                    batch = {k: self.player_daily.get(day, {}).get(k) for k in batch_keys}
                else:
                    batch = self._daily_player_points(f'league/{LEAGUE_ID}', day, batch_keys, require_stats=True)
                for key in keys[i:i + 25]:
                    value = batch.get(key)
                    if value is None:
                        valid[key] = False
                    else:
                        totals[key] += value
            self._publish_recent_windows(days, keys)
        self._publish_recent_windows(days, keys)
        self.progress(f'{days}-day import paused at the local request limit; progress is saved.' if not completed else f'{days}-day player import finished.')

    def _publish_recent_windows(self, requested, keys):
        end = self.today() - timedelta(days=1)
        players = {p['key']:p for p in self.data.get('players', [])}
        for days in sorted({7, requested} | {n for n in (14,30) if n <= requested}):
            dates = [(end-timedelta(days=offset)).isoformat() for offset in range(days)]
            points = {}
            stats = {}
            complete = True
            for key in keys:
                values = [self.player_daily.get(day, {}).get(key) for day in dates]
                points[key] = round(sum(values),2) if all(v is not None for v in values) else None
                daily = [zero_point_day(self.player_daily_stats.get(day, {}).get(key),
                    self.player_daily.get(day, {}).get(key), self.data.get('stat_labels',{})) for day in dates]
                stats[key] = aggregate_stats(daily, self.data.get('stat_labels',{}), players.get(key,{}).get('stats',{}))
                complete = complete and points[key] is not None and all(day is not None for day in daily)
            with self.lock:
                self.data['recent'][str(days)] = dict(points=points,stats=stats,start=(end-timedelta(days=days-1)).isoformat(),
                    end=end.isoformat(),pool_size=len(keys),complete=complete,paused=not complete and self.client.remaining<=20,
                    fetched_at=datetime.now(timezone.utc).isoformat())
        self.save()
