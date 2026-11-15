"""Single-process, paced, GET-only Yahoo access. No network on import."""
import contextlib
import io
import json
import logging
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class YahooError(Exception):
    pass


class YahooClient:
    def __init__(self, interval=2.0, budget=900, store=None):
        self.interval, self.budget = interval, budget
        self.lock = threading.RLock()
        self.session = None
        self.last = 0.0
        self.blocked_until = 0.0
        self.count = 0
        self.cache = {}
        self.day = time.strftime('%Y-%m-%d')
        self.store = store
        if self.store:
            self.count = self.store.usage(self.day)

    @property
    def remaining(self):
        with self.lock:
            if time.strftime('%Y-%m-%d') != self.day:
                self.day, self.count = time.strftime('%Y-%m-%d'), 0
            return max(0, self.budget - self.count)

    def invalidate(self, prefix, except_path=None):
        with self.lock:
            for path in list(self.cache):
                if path.startswith(prefix) and path != except_path:
                    del self.cache[path]

    def connect(self):
        from yahoo_oauth import OAuth2

        class DurableOAuth(OAuth2):
            def refresh_access_token(inner):
                values = super().refresh_access_token()
                path = ROOT / 'oauth2.json'
                original = json.loads(path.read_text())
                original.update(values)
                temporary = path.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(original), encoding='utf-8')
                os.replace(temporary, path)
                return values

        for name in ('yahoo_oauth', 'oauthlib', 'requests_oauthlib'):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.session = DurableOAuth(None, None, from_file=str(ROOT / 'oauth2.json'))

    def get(self, path, ttl=1800):
        with self.lock:
            now = time.monotonic()
            if path in self.cache and now - self.cache[path][0] < ttl:
                return self.cache[path][1]
            if time.strftime('%Y-%m-%d') != self.day:
                self.day, self.count = time.strftime('%Y-%m-%d'), 0
            if self.count >= self.budget:
                raise YahooError('Local daily request budget reached; try tomorrow.')
            if now < self.blocked_until:
                raise YahooError('Yahoo requests are paused after throttling. Cached data remains available.')
            if self.session is None:
                self.connect()
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.count += 1
            if self.store:
                self.store.save_usage(self.day, self.count)
            try:
                response = self.session.session.get(
                    f'https://fantasysports.yahooapis.com/fantasy/v2/{path}',
                    params={'format': 'json'}, timeout=25,
                )
                self.last = time.monotonic()
                if response.status_code == 401:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        values = self.session.refresh_access_token()
                    self.session.access_token = values['access_token']
                    self.session.refresh_token = values.get('refresh_token', self.session.refresh_token)
                    self.session.session = self.session.oauth.get_session(token=values['access_token'])
                    self.cache.pop(path, None)
                    # One retry; it is paced and counted like any other request.
                    return self._retry(path, ttl)
                return self._accept(path, response)
            except YahooError:
                raise
            except Exception:
                raise YahooError('Yahoo could not be reached. Check your connection or authentication.') from None

    def _retry(self, path, ttl):
        if self.count >= self.budget:
            raise YahooError('Local request budget reached.')
        time.sleep(self.interval)
        self.count += 1
        if self.store:
            self.store.save_usage(self.day, self.count)
        response = self.session.session.get(
            f'https://fantasysports.yahooapis.com/fantasy/v2/{path}',
            params={'format': 'json'}, timeout=25,
        )
        self.last = time.monotonic()
        return self._accept(path, response)

    def _accept(self, path, response):
        if response.status_code in (429, 999):
            retry = response.headers.get('Retry-After', '')
            delay = max(900, int(retry)) if retry.isdigit() else 900
            self.blocked_until = time.monotonic() + delay
            raise YahooError('Yahoo throttled this connection; requests paused for at least 15 minutes.')
        if response.status_code == 401:
            raise YahooError('Yahoo login needs attention. Reauthorize locally.')
        if response.status_code == 403:
            raise YahooError('Yahoo denied permission for this resource.')
        if response.status_code != 200:
            raise YahooError(f'Yahoo returned HTTP {response.status_code}.')
        data = response.json()
        self.cache[path] = (time.monotonic(), data)
        return data
