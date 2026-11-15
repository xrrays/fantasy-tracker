"""Rebuildable, private local cache. Never stores credentials or raw Yahoo responses."""
import json
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path


class DashboardCache:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS dashboard (
                league TEXT PRIMARY KEY, payload TEXT NOT NULL, saved_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS player_days (
                league TEXT NOT NULL, day TEXT NOT NULL, player TEXT NOT NULL, points REAL,
                PRIMARY KEY (league, day, player));
            CREATE TABLE IF NOT EXISTS request_usage (
                day TEXT PRIMARY KEY, count INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS player_day_stats (
                league TEXT NOT NULL, day TEXT NOT NULL, player TEXT NOT NULL, stats TEXT NOT NULL,
                PRIMARY KEY (league, day, player));
            CREATE TABLE IF NOT EXISTS daily_lineups (
                league TEXT NOT NULL, day TEXT NOT NULL, team TEXT NOT NULL, players TEXT NOT NULL,
                PRIMARY KEY (league, day, team));
        ''')
        return connection

    def load(self, league):
        if not self.path.exists():
            return None
        with self.lock, closing(self._connect()) as db:
            row = db.execute('SELECT payload FROM dashboard WHERE league = ?', (league,)).fetchone()
            if row is None:
                return None
            value = json.loads(row[0])
            if value.get('data', {}).get('league', {}).get('key') != league:
                return None
            daily = {}
            for day, player, points in db.execute('SELECT day, player, points FROM player_days WHERE league = ? AND points IS NOT NULL', (league,)):
                daily.setdefault(day, {})[player] = points
            value['player_daily'] = daily
            daily_stats = {}
            for day, player, stats in db.execute('SELECT day, player, stats FROM player_day_stats WHERE league = ?', (league,)):
                daily_stats.setdefault(day, {})[player] = json.loads(stats)
            value['player_daily_stats'] = daily_stats
            lineups = {}
            for day, team, players in db.execute('SELECT day, team, players FROM daily_lineups WHERE league = ?', (league,)):
                lineups.setdefault(day, {})[team] = json.loads(players)
            value['daily_lineups'] = lineups
            return value

    def save(self, data, transaction_head):
        if not data:
            return
        # Only the normalized, whitelisted UI model and transaction IDs enter this table.
        payload = json.dumps({'data': data, 'transaction_head': transaction_head}, ensure_ascii=False)
        with self.lock, closing(self._connect()) as db, db:
            db.execute('INSERT OR REPLACE INTO dashboard VALUES (?, ?, ?)',
                       (data['league']['key'], payload, time.time()))

    def save_player_day(self, league, day, values):
        with self.lock, closing(self._connect()) as db, db:
            db.executemany('INSERT OR REPLACE INTO player_days VALUES (?, ?, ?, ?)',
                           [(league, day, player, points) for player, points in values.items()])

    def usage(self, day):
        if not self.path.exists():
            return 0
        with self.lock, closing(self._connect()) as db:
            row = db.execute('SELECT count FROM request_usage WHERE day = ?', (day,)).fetchone()
            return row[0] if row else 0

    def save_player_day_stats(self, league, day, values):
        with self.lock, closing(self._connect()) as db, db:
            db.executemany('INSERT OR REPLACE INTO player_day_stats VALUES (?, ?, ?, ?)',
                           [(league, day, player, json.dumps(stats)) for player, stats in values.items()])

    def save_lineups(self, league, day, teams):
        with self.lock, closing(self._connect()) as db, db:
            db.executemany('INSERT OR REPLACE INTO daily_lineups VALUES (?, ?, ?, ?)',
                           [(league, day, team, json.dumps(players)) for team,players in teams.items()])

    def save_usage(self, day, count):
        with self.lock, closing(self._connect()) as db, db:
            db.execute('INSERT OR REPLACE INTO request_usage VALUES (?, ?)', (day, count))
            # Counts are operational bookkeeping, not an archive of user activity.
            db.execute('DELETE FROM request_usage WHERE day < date(?, \'-7 days\')', (day,))
