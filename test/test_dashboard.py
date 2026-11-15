"""Offline tests. Never import the legacy main script or call Yahoo."""
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.analytics import enrich_teams, records, biggest_comeback, pickup_spells, score_pickups
from backend.normalize import number, player, team, player_image, stat_number
from backend.player_periods import aggregate_stats
from backend.service import DashboardService
from backend.yahoo_client import YahooClient, YahooError
from backend.cache import DashboardCache


def matchup(week, scores, status='postevent', **kwargs):
    return {'week': week, 'status': status, 'teams': [
        {'key': k, 'name': k, 'points': score} for k, score in scores], **kwargs}


class MetricsTests(unittest.TestCase):
    def test_ties_and_expected_wins(self):
        teams = [{'key': k, 'name': k} for k in 'abcd']
        matches = [matchup(1, [('a', 100), ('b', 100)]), matchup(1, [('c', 50), ('d', 0)])]
        results = {t['key']: t for t in enrich_teams(teams, matches)}
        self.assertAlmostEqual(results['a']['expected_wins'], 2.5 / 3, places=4)
        self.assertEqual(results['a']['all_ties'], 1)
        self.assertAlmostEqual(sum(t['expected_wins'] for t in results.values()), 2, places=3)
        self.assertEqual(results['a']['schedule_strength'], 100)
        self.assertEqual(results['d']['margin'], -50)

    def test_six_week_example(self):
        teams = [{'key': str(i), 'name': str(i)} for i in range(16)]
        matches = []
        for week, wins in enumerate([15, 15, 15, 10, 6, 6], 1):
            scores = [('0', wins - .5)] + [(str(i), float(i - 1)) for i in range(1, 16)]
            matches += [matchup(week, scores[i:i + 2]) for i in range(0, 16, 2)]
        result = enrich_teams(teams, matches)[0]
        self.assertEqual(result['all_wins'], 67)
        self.assertEqual(result['all_losses'], 23)
        self.assertAlmostEqual(result['expected_wins'], 4.4667)

    def test_partial_missing_playoff_and_incomplete_weeks_excluded(self):
        teams = [{'key': k, 'name': k} for k in 'ab']
        for match in [matchup(1, [('a', 10), ('b', 5)], 'midevent'),
                      matchup(1, [('a', None), ('b', 5)]),
                      matchup(1, [('a', 10), ('b', 5)], playoffs=True),
                      matchup(1, [('a', 10), ('b', 5)], consolation=True)]:
            self.assertIsNone(enrich_teams(teams, [match])[0]['expected_wins'])
        self.assertIsNone(enrich_teams(teams + [{'key': 'c', 'name': 'c'}], [matchup(1, [('a', 10), ('b', 5)])])[0]['expected_wins'])

    def test_final_week_and_records(self):
        rows = [matchup(26, [('a', 200), ('b', 199.5)]), matchup(25, [('a', 300), ('b', 300)]), matchup(27, [('a', 1000), ('b', 0)], 'midevent')]
        result = records(rows)
        self.assertEqual(result['highest']['points'], 300)
        self.assertEqual(result['closest']['week'], 26)
        self.assertEqual(result['closest']['margin'], .5)


class NormalizeTests(unittest.TestCase):
    def test_larger_headshot_source_and_safe_fallback(self):
        source = 'https://s.yimg.com/xe/i/us/sp/v/nhl_cutout/players_l/2026/1.png'
        thumbnail = 'https://s.yimg.com/iu/api/res/small/https://s.yimg.com/' + source.split('https://s.yimg.com/')[1]
        self.assertEqual(player_image(thumbnail), source)
        self.assertEqual(player_image('https://other.invalid/image.png'), 'https://other.invalid/image.png')
        self.assertEqual(player_image('javascript:alert(1)'), '')
    def test_missing_data_and_sensitive_fields(self):
        self.assertIsNone(number('-'))
        raw = [[{'team_key': 'x'}, {'name': 'Example'}, {'managers': [{'manager': {'nickname': 'Alias', 'email': 'private@example.invalid', 'guid': 'private'}}]}], {'team_standings': {'rank': '1', 'points_for': '0', 'outcome_totals': {'wins': '0', 'losses': '1', 'ties': '0'}}}]
        result = team(raw)
        self.assertEqual(result['manager'], 'Alias')
        self.assertEqual(result['pf'], 0)
        self.assertIsNone(result['pa'])
        self.assertNotIn('private', json.dumps(result))

    def test_player_context(self):
        raw = [[{'player_key': 'p1'}, {'name': {'full': 'Player'}}, {'eligible_positions': [{'position': 'G'}]}], {'player_points': {'total': '0'}, 'player_stats': {'stats': [{'stat': {'stat_id': '25', 'value': '12'}}]}}]
        result = player(raw)
        self.assertEqual(result['group'], 'G')
        self.assertEqual(result['points'], 0)
        self.assertEqual(result['stats']['25'], 12)


class ClientTests(unittest.TestCase):
    def client(self, code=200, budget=240):
        c = YahooClient(interval=0, budget=budget)
        response = Mock(status_code=code, headers={})
        response.json.return_value = {'ok': True}
        c.session = SimpleNamespace(session=SimpleNamespace(get=Mock(return_value=response)))
        return c

    def test_cached_reads_do_not_request_again(self):
        c = self.client()
        c.get('resource'); c.get('resource')
        self.assertEqual(c.count, 1)
        c.session.session.get.assert_called_once()

    def test_throttle_stops_followup_requests(self):
        for code in (429, 999):
            c = self.client(code)
            with self.assertRaises(YahooError): c.get('resource')
            with self.assertRaises(YahooError): c.get('other')
            self.assertEqual(c.count, 1)

    def test_local_budget(self):
        c = self.client(budget=1)
        c.get('resource')
        with self.assertRaises(YahooError): c.get('other')
        self.assertEqual(c.count, 1)

    def test_atomic_token_refresh_preserves_other_configuration(self):
        from yahoo_oauth import OAuth2
        parent = (Path(__file__).resolve().parents[1] / 'data' / 'test-temp').resolve()
        self.assertTrue(parent.is_relative_to(Path(__file__).resolve().parents[1]))
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(parent))
            path = Path(folder) / 'oauth2.json'
            path.write_text(json.dumps({'consumer_key': 'test-key', 'refresh_token': 'old-token'}))
            c = YahooClient()
            with patch('backend.yahoo_client.ROOT', Path(folder)), patch.object(OAuth2, '__init__', return_value=None), patch.object(OAuth2, 'refresh_access_token', return_value={'refresh_token': 'new-token', 'access_token': 'new-access'}):
                c.connect()
                c.session.refresh_access_token()
            self.assertEqual(json.loads(path.read_text())['refresh_token'], 'new-token')
            self.assertEqual(json.loads(path.read_text())['consumer_key'], 'test-key')
            self.assertFalse(path.with_suffix('.json.tmp').exists())


class ServiceTests(unittest.TestCase):
    def setUp(self):
        config = patch.dict('sys.modules', {'backend.keys': SimpleNamespace(LEAGUE_ID='example')})
        config.start()
        self.addCleanup(config.stop)

    @staticmethod
    def transaction_client(total=130, budget=240):
        c = YahooClient(interval=0, budget=budget)
        events = [{'transaction_key': f'tx{i}', 'type': 'add', 'status': 'successful',
                   'timestamp': str(1791000000 + i), 'players': []} for i in range(total, 0, -1)]
        def respond(url, **kwargs):
            start = int(url.split(';start=')[1].split(';')[0])
            response = Mock(status_code=200, headers={})
            response.json.return_value = {'transactions': [{ 'transaction': tx } for tx in events[start:start + 25]]}
            return response
        c.session = SimpleNamespace(session=SimpleNamespace(get=Mock(side_effect=respond)))
        return c, events

    def test_complete_transaction_history_beyond_one_hundred(self):
        c, events = self.transaction_client()
        service = DashboardService(c)
        service.data = {'transactions': []}
        service._transactions('league/example')
        self.assertEqual(len(service.data['transactions']), len(events))
        self.assertTrue(service.data['transactions_complete'])
        self.assertEqual(c.count, 6)

    def test_incremental_transactions_refresh_shifted_pages_without_skipping(self):
        c, events = self.transaction_client()
        service = DashboardService(c)
        service.data = {'transactions': []}
        service._transactions('league/example')
        events[:0] = [dict(events[0], transaction_key=f'new{i}', timestamp=str(1792000000 + i)) for i in range(30, 0, -1)]
        head = 'league/example/transactions;types=add,drop,trade;start=0;count=25'
        c.cache.pop(head)
        c.session.session.get.reset_mock()
        service._transactions('league/example')
        self.assertEqual(len(service.data['transactions']), 160)
        self.assertTrue(service.data['transactions_complete'])
        self.assertEqual(c.session.session.get.call_count, 2)
        self.assertEqual(service.data['transactions'][0]['id'], 'new30')
        self.assertEqual(len({t['id'] for t in service.data['transactions']}), 160)

    def test_transaction_backfill_pauses_and_resumes_with_cached_pages(self):
        c, _ = self.transaction_client(total=70, budget=32)
        service = DashboardService(c)
        service.data = {'transactions': []}
        service._transactions('league/example')
        self.assertEqual(len(service.data['transactions']), 50)
        self.assertFalse(service.data['transactions_complete'])
        c.day = '2000-01-01'
        c.session.session.get.reset_mock()
        service._transactions('league/example')
        self.assertEqual(len(service.data['transactions']), 70)
        self.assertTrue(service.data['transactions_complete'])
        self.assertEqual(c.session.session.get.call_count, 1)

    def test_repeated_transaction_page_does_not_claim_full_coverage(self):
        c, _ = self.transaction_client(total=25)
        c.session.session.get.side_effect = None
        c.session.session.get.return_value = Mock(status_code=200, headers={})
        c.session.session.get.return_value.json.return_value = {'transactions': [{'transaction': {
            'transaction_key': f'tx{i}', 'status': 'successful', 'timestamp': str(i), 'players': []}} for i in range(25)]}
        service = DashboardService(c)
        service.data = {'transactions': []}
        with self.assertRaises(YahooError):
            service._transactions('league/example')
        self.assertFalse(service.data['transactions_complete'])
        self.assertEqual(len(service.data['transactions']), 25)

    def test_pickup_refresh_only_fetches_new_completed_player_days(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        c = YahooClient(interval=0)
        c.get = Mock(return_value={'player': [[{'player_key': 'p'}], {'player_points': {'total': '2'}}]})
        service = DashboardService(c)
        timestamp = str(int(datetime(2026, 10, 1, 12, tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()))
        service.data = {'transactions': [{'id': 'tx', 'timestamp': timestamp, 'players': [{'player': 'p', 'name': 'Player', 'action': 'add', 'source_type': 'freeagents', 'source': None, 'destination': 'a'}]}]}
        with patch.object(service, 'today', return_value=date(2026, 10, 3)):
            service._pickups('league/example')
            service._pickups('league/example')
        self.assertEqual(c.get.call_count, 2)
        self.assertEqual(service.data['pickups'][0]['points'], 4)
        c.count = c.budget
        with patch.object(service, 'today', return_value=date(2026, 10, 3)):
            service._pickups('league/example')
        self.assertTrue(service.data['pickups_loaded'])
        self.assertEqual(c.get.call_count, 2)
        c.count = 0
        with patch.object(service, 'today', return_value=date(2026, 10, 4)):
            service._pickups('league/example')
        self.assertEqual(c.get.call_count, 3)
        self.assertEqual(service.data['pickups'][0]['points'], 6)
        self.assertTrue(service.data['pickups_loaded'])

    def test_daily_player_cache_reuses_overlapping_windows(self):
        c = YahooClient(interval=0)
        c.get = Mock(return_value={'player': [[{'player_key': 'a'}], {'player_points': {'total': '2'}}]})
        service = DashboardService(c)
        service._daily_player_points('league/example', '2026-10-01', ['a'])
        service._daily_player_points('league/example', '2026-10-01', ['a'])
        c.get.assert_called_once()
    def test_one_refresh_owner(self):
        service = DashboardService(YahooClient(interval=0))
        with patch('backend.service.threading.Thread') as thread:
            self.assertTrue(service.start())
            self.assertFalse(service.start())
            thread.assert_called_once()

    def test_recent_boundaries_and_missing_points(self):
        c = YahooClient(interval=0)
        c.get = Mock(return_value={'players': {'0': {'player': [[{'player_key': 'a'}, {'name': {'full': 'A'}}], {'player_points': {'total': '2'}}]}}})
        service = DashboardService(c)
        service.data = {'recent_pool': ['a', 'b'], 'recent': {}}
        service._recent(7)
        value = service.data['recent']['7']
        self.assertEqual(value['points']['a'], 14)
        self.assertIsNone(value['points']['b'])
        self.assertEqual(value['end'], (service.today() - __import__('datetime').timedelta(days=1)).isoformat())
        self.assertEqual(c.get.call_count, 7)

    def test_reading_snapshot_never_fetches(self):
        c = self.client = YahooClient()
        c.get = Mock()
        DashboardService(c).snapshot()
        c.get.assert_not_called()

    def test_current_rosters_include_every_team_and_keep_unknown_separate(self):
        c = YahooClient(interval=0)
        c.get = Mock(return_value={'teams': [
            {'team': [{'team_key': 'a'}, {'roster': {'players': [{'player': [{'player_key': 'p1'}]}, {'player': [{'player_key': 'p2'}]}]}}]},
            {'team': [{'team_key': 'b'}, {'roster': {'players': [{'player': [{'player_key': 'p3'}]}]}}]},
        ]})
        service = DashboardService(c)
        service.data = {'teams': [{'key': 'a'}, {'key': 'b'}]}
        service._rosters('league/example')
        self.assertEqual(service.data['roster_owners'], {'p1': 'a', 'p2': 'a', 'p3': 'b'})
        self.assertTrue(service.data['rosters_loaded'])
        c.get.return_value = {'team': [{'team_key': 'a'}]}
        with self.assertRaises(YahooError):
            service._rosters('league/example')
        self.assertEqual(service.data['roster_owners']['p3'], 'b')

    def test_recent_import_pauses_without_spending_the_request_reserve(self):
        c = YahooClient(interval=0, budget=20)
        c.get = Mock()
        service = DashboardService(c)
        service.data = {'recent_pool': ['p1'], 'recent': {}}
        service._recent(7)
        c.get.assert_not_called()
        self.assertFalse(service.data['recent']['7']['complete'])
        self.assertIsNone(service.data['recent']['7']['points']['p1'])

    def test_recent_includes_unrostered_players_outside_old_leader_pool(self):
        c = YahooClient(interval=0, budget=20)
        c.get = Mock()
        service = DashboardService(c)
        service.data = {'players':[{'key':'leader', 'stats':{}}, {'key':'free-agent','stats':{}}],
                        'recent_pool':['leader'], 'recent':{}}
        service._recent(14)
        self.assertEqual(set(service.data['recent']['14']['points']), {'leader','free-agent'})
        self.assertTrue(service.data['recent']['14']['paused'])
        c.get.assert_not_called()

    def test_long_backfill_publishes_complete_short_window_before_finishing(self):
        from datetime import date, timedelta
        client = YahooClient(interval=0, budget=20)
        client.get = Mock()
        service = DashboardService(client)
        service.data = {'players':[{'key':'p','stats':{'1':100}}], 'recent':{}, 'stat_labels':{'1':'G'}}
        for offset in range(7):
            day = (date(2026,11,14)-timedelta(days=offset)).isoformat()
            service.player_daily[day] = {'p':2}
            service.player_daily_stats[day] = {'p':{'1':1}}
        with patch.object(service,'today',return_value=date(2026,11,15)):
            service._recent(30)
        self.assertTrue(service.data['recent']['7']['complete'])
        self.assertEqual(service.data['recent']['7']['points']['p'],14)
        self.assertEqual(service.data['recent']['7']['stats']['p']['1'],7)
        self.assertFalse(service.data['recent']['14']['complete'])
        self.assertFalse(service.data['recent']['30']['complete'])
        client.get.assert_not_called()

    def test_api_blocks_cross_origin_post(self):
        from backend.server import local_only
        next_handler = AsyncMock(return_value=SimpleNamespace(headers={}, status_code=200))
        external = SimpleNamespace(method='POST', headers={'origin': 'https://external.invalid', 'X-Ray-Local': '1'})
        bare = SimpleNamespace(method='POST', headers={})
        valid = SimpleNamespace(method='POST', headers={'origin': 'http://127.0.0.1:5174', 'X-Ray-Local': '1'})
        self.assertEqual(asyncio.run(local_only(external, next_handler)).status_code, 403)
        self.assertEqual(asyncio.run(local_only(bare, next_handler)).status_code, 403)
        next_handler.assert_not_called()
        self.assertEqual(asyncio.run(local_only(valid, next_handler)).status_code, 200)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        parent = (root / 'data' / 'test-temp').resolve()
        self.assertTrue(parent.is_relative_to(root))
        parent.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=parent)
        self.cache = DashboardCache(Path(self.folder.name) / 'cache.sqlite3')

    def tearDown(self):
        self.folder.cleanup()

    @staticmethod
    def data():
        from datetime import datetime, timezone
        return {'league': {'key': 'example', 'season': '2026', 'week': 1}, 'players_loaded': True,
                'transactions': [], 'transactions_complete': True, 'pickups_loaded': True,
                'updated_at': datetime.now(timezone.utc).isoformat()}

    def test_saved_snapshot_opens_without_a_yahoo_request_and_is_league_scoped(self):
        self.cache.save(self.data(), ['tx1'])
        c = YahooClient(interval=0, store=self.cache)
        c.get = Mock()
        service = DashboardService(c, store=self.cache, league_key='example')
        self.assertEqual(service.snapshot()['data']['league']['key'], 'example')
        self.assertFalse(service.snapshot()['refresh_due'])
        self.assertEqual(service.transaction_head, ('tx1',))
        c.get.assert_not_called()
        self.assertIsNone(self.cache.load('other-season'))

    def test_lineups_survive_restart_and_are_league_scoped(self):
        self.cache.save(self.data(),[])
        self.cache.save_lineups('example','2026-11-01',{'a':[dict(player='p',slot='BN')]})
        other=DashboardCache(self.cache.path)
        self.assertEqual(other.load('example')['daily_lineups']['2026-11-01']['a'],[dict(player='p',slot='BN')])
        self.assertIsNone(other.load('other'))

    def test_request_budget_survives_process_restart(self):
        c = YahooClient(interval=0, budget=1, store=self.cache)
        response = Mock(status_code=200, headers={})
        response.json.return_value = {'ok': True}
        c.session = SimpleNamespace(session=SimpleNamespace(get=Mock(return_value=response)))
        c.get('example')
        restarted = YahooClient(interval=0, budget=1, store=DashboardCache(self.cache.path))
        self.assertEqual(restarted.count, 1)
        with self.assertRaises(YahooError):
            restarted.get('other')

    def test_restart_reuses_completed_player_days_and_only_fetches_missing_day(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        data = self.data()
        timestamp = str(int(datetime(2026, 10, 1, 12, tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()))
        data['transactions'] = [{'id': 'tx', 'timestamp': timestamp, 'players': [{'player': 'p', 'name': 'Player', 'action': 'add', 'source_type': 'freeagents', 'source': None, 'destination': 'a'}]}]
        self.cache.save(data, ['tx'])
        self.cache.save_player_day('example', '2026-10-01', {'p': 2})
        self.cache.save_player_day('example', '2026-10-02', {'p': 3})
        c = YahooClient(interval=0)
        c.get = Mock(return_value={'player': [[{'player_key': 'p'}], {'player_points': {'total': '5'}}]})
        service = DashboardService(c, store=self.cache, league_key='example')
        with patch.object(service, 'today', return_value=date(2026, 10, 4)):
            service._pickups('league/example')
        self.assertEqual(c.get.call_count, 1)
        self.assertIn('date=2026-10-03', c.get.call_args.args[0])
        self.assertEqual(service.data['pickups'][0]['points'], 10)
        restarted = DashboardService(YahooClient(interval=0), store=self.cache, league_key='example')
        self.assertEqual(restarted.player_daily['2026-10-03']['p'], 5)

    def test_zero_and_missing_points_remain_distinct_after_restart(self):
        self.cache.save(self.data(), None)
        self.cache.save_player_day('example', '2026-10-01', {'zero': 0, 'missing': None})
        daily = self.cache.load('example')['player_daily']
        self.assertEqual(daily['2026-10-01']['zero'], 0)
        self.assertNotIn('missing', daily['2026-10-01'])

    def test_restart_rebuilds_recent_stats_from_saved_daily_facts_without_fetching(self):
        from datetime import date,timedelta
        data = self.data()
        data.update(players=[{'key':'p','stats':{'1':99}}], stat_labels={'1':'G'}, recent={'7':{}})
        self.cache.save(data,None)
        for offset in range(7):
            day=(date(2026,11,14)-timedelta(days=offset)).isoformat()
            self.cache.save_player_day('example',day,{'p':0 if offset==0 else 2})
            self.cache.save_player_day_stats('example',day,{'p':{'1':None if offset==0 else 1}})
        client=YahooClient(interval=0)
        client.get=Mock()
        with patch.object(DashboardService,'today',return_value=date(2026,11,15)):
            restarted=DashboardService(client,store=self.cache,league_key='example')
        self.assertEqual(restarted.data['recent']['7']['stats']['p']['1'],6)
        self.assertEqual(restarted.data['recent']['7']['points']['p'],12)
        self.assertTrue(restarted.data['recent']['7']['complete'])
        client.get.assert_not_called()

    def test_daily_stat_upgrade_survives_restart_and_does_not_refetch(self):
        self.cache.save(self.data(), None)
        self.cache.save_player_day('example', '2026-10-01', {'p': 5})
        client = YahooClient(interval=0)
        client.get = Mock(return_value={'player': [[{'player_key': 'p'}],
            {'player_points': {'total': '5'}}, {'player_stats': {'stats': [
                {'stat': {'stat_id': '1', 'value': '2'}}, {'stat': {'stat_id': '2', 'value': '1'}}]}}]})
        service = DashboardService(client, store=self.cache, league_key='example')
        self.assertEqual(service._daily_player_points('league/example', '2026-10-01', ['p']), {'p':5})
        client.get.assert_not_called()
        service._daily_player_points('league/example', '2026-10-01', ['p'], require_stats=True)
        client.get.assert_called_once()
        restarted = DashboardService(YahooClient(interval=0), store=DashboardCache(self.cache.path), league_key='example')
        restarted.client.get = Mock()
        self.assertEqual(restarted.player_daily_stats['2026-10-01']['p'], {'1':2, '2':1})
        self.assertEqual(restarted._daily_player_points('league/example', '2026-10-01', ['p'], require_stats=True), {'p':5})
        restarted.client.get.assert_not_called()
        self.assertIsNone(self.cache.load('other'))

    def test_api_startup_restores_saved_dashboard_without_fetching(self):
        from backend import server
        self.cache.save(self.data(), None)
        async def read():
            async with server.lifespan(server.app):
                return server.dashboard()
        with patch.dict('sys.modules', {'backend.keys': SimpleNamespace(LEAGUE_ID='example')}), \
                patch.object(server, 'DashboardCache', return_value=self.cache), \
                patch.object(server, 'service', DashboardService()), \
                patch.object(YahooClient, 'get') as get:
            snapshot = asyncio.run(read())
        self.assertEqual(snapshot['data']['league']['key'], 'example')
        self.assertFalse(snapshot['refresh_due'])
        get.assert_not_called()

    def test_older_complete_team_days_do_not_refetch(self):
        service = DashboardService(YahooClient(interval=0))
        service.client.get = Mock()
        match = dict(matchup(1, [('a', 20), ('b', 19)]), start='2026-10-01', end='2026-10-02')
        service.data = {'league': {'week': 2}, 'teams': [{'key': 'a'}, {'key': 'b'}],
                        'matchups': [match], 'records': {}, 'daily_by_week': {'1': [
                            {'date': '2026-10-01', 'scores': {'a': 2, 'b': 15}},
                            {'date': '2026-10-02', 'scores': {'a': 18, 'b': 4}}]}}
        service._daily_weeks('league/example', [match])
        service.client.get.assert_not_called()
        self.assertEqual(service.data['records']['comeback_covered'], 1)


class DailyAnalysisTests(unittest.TestCase):
    def test_confirmed_zero_point_blank_day_counts_as_zero_without_filling_missing_data(self):
        from backend.player_periods import zero_point_day
        labels = {'g':'G','gaa':'GAA'}
        self.assertEqual(zero_point_day({'g':None,'gaa':None},0,labels), {'g':0,'gaa':None})
        self.assertIsNone(zero_point_day(None,0,labels))
        self.assertEqual(zero_point_day({'g':None},None,labels), {'g':None})
        self.assertEqual(zero_point_day({'g':None},3,labels), {'g':None})
        self.assertEqual(zero_point_day({'g':None,'gaa':1},0,labels), {'g':None,'gaa':1})

    def test_period_counts_and_rates_use_underlying_totals(self):
        labels = {'g':'G', 'sog':'SOG', 'sh':'SH%', 'sv':'SV', 'ga':'GA', 'sa':'SA', 'pct':'SV%', 'gaa':'GAA', 'toi':'TOI', 'avg':'TOI/G', 'gp':'GP'}
        days = [dict(g=1, sog=2, sh=50, sv=9, ga=1, sa=10, pct=.9, gaa=2, toi=30, avg=30, gp=1),
                dict(g=0, sog=8, sh=0, sv=90, ga=10, sa=100, pct=.9, gaa=10, toi=60, avg=60, gp=1)]
        value = aggregate_stats(days, labels)
        self.assertEqual(value['g'], 1)
        self.assertEqual(value['sog'], 10)
        self.assertEqual(value['sh'], 10)
        self.assertEqual(value['pct'], .9)
        self.assertEqual(value['gaa'], 7.3333)
        self.assertEqual(value['avg'], 45)

    def test_missing_stats_do_not_become_season_totals_or_zero(self):
        labels = {'g':'G', 'gp':'GP', 'pct':'SV%', 'unknown':'FO%'}
        self.assertIsNone(aggregate_stats([{'g':2}, None], labels, ['g'])['g'])
        self.assertIsNone(aggregate_stats([{}, {}], labels, ['g'])['g'])
        self.assertEqual(aggregate_stats([{'g':2}, {'gp':0}], labels, ['g'])['g'], 2)
        self.assertIsNone(aggregate_stats([{'g':2}, {'gp':1}], labels, ['g'])['g'])
        self.assertIsNone(aggregate_stats([{'unknown':50}], labels)['unknown'])
        self.assertEqual(aggregate_stats([{'sv':9, 'ga':1}, {'sv':90, 'ga':0}], dict(sv='SV',ga='GA',pct='SV%'), ['pct'])['pct'], .99)

    def test_game_context_ice_time_seconds_produce_minutes_per_game(self):
        value=aggregate_stats([{'33':1200,'0':1},{'33':1800,'0':1}], {'33':'TOI','0':'GP','34':'TOI/G'}, ['34'])
        self.assertEqual(value['33'],50)
        self.assertEqual(value['34'],25)

    def test_time_stats_are_normalized_to_minutes(self):
        self.assertEqual(stat_number('60:30'), 60.5)
        self.assertEqual(stat_number('120:00'), 120)
        self.assertIsNone(stat_number('12:75'))
        self.assertIsNone(stat_number('-'))

    def test_comeback_requires_final_win_and_reconciled_full_week(self):
        match = dict(matchup(1, [('a', 20), ('b', 19)]), start='2026-10-01', end='2026-10-02')
        days = {'1': [{'date': '2026-10-01', 'scores': {'a': 2, 'b': 15}}, {'date': '2026-10-02', 'scores': {'a': 18, 'b': 4}}]}
        result = biggest_comeback([match], days)
        self.assertEqual(result['record']['deficit'], 13)
        self.assertEqual(result['record']['team'], 'a')
        self.assertEqual(result['covered_matchups'], 1)
        self.assertIsNone(biggest_comeback([dict(match, status='midevent')], days)['record'])
        days['1'][1]['scores']['a'] = None
        self.assertIsNone(biggest_comeback([match], days)['record'])
        days['1'][1]['scores']['a'] = 19
        self.assertIsNone(biggest_comeback([match], days)['record'])

    def test_pickup_points_stop_before_drop_and_restart_on_reacquisition(self):
        from datetime import datetime, date
        from zoneinfo import ZoneInfo
        def tx(identifier, day, action, source, destination):
            timestamp = str(int(datetime.fromisoformat(day+'T12:00:00').replace(tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()))
            return {'id': identifier, 'timestamp': timestamp, 'players': [{'player': 'p', 'name': 'Example', 'action': action,
                'source_type': 'freeagents' if action == 'add' else 'team', 'source': source, 'destination': destination}]}
        events = [tx('1', '2026-10-01', 'add', None, 'a'), tx('2', '2026-10-03', 'drop', 'a', None), tx('3', '2026-10-05', 'add', None, 'a')]
        spells = pickup_spells(events, date(2026,10,6))
        self.assertEqual(spells[0]['end'], '2026-10-02')
        self.assertEqual(spells[1]['start'], '2026-10-05')
        self.assertFalse(spells[0]['active'])
        self.assertTrue(spells[1]['active'])
        daily = {f'2026-10-0{i}': {'p': float(i)} for i in range(1,7)}
        scored = {r['id']:r for r in score_pickups(spells, daily)}
        self.assertEqual(scored['1:p']['points'], 3)
        self.assertEqual(scored['3:p']['points'], 11)
        daily['2026-10-01']['p'] = None
        partial = {r['id']:r for r in score_pickups(spells, daily)}['1:p']
        self.assertEqual(partial['points'], 2)
        self.assertFalse(partial['points_complete'])
        self.assertEqual(partial['covered_days'], 1)

    def test_active_pickup_is_included_and_missing_days_are_not_zero(self):
        spell = {'id': 'active', 'start': '2026-10-01', 'days': 3, 'player': 'p', 'active': True}
        result = score_pickups([spell], {'2026-10-01': {'p': 12}, '2026-10-03': {'p': 10}})[0]
        self.assertEqual(result['points'], 22)
        self.assertFalse(result['points_complete'])
        self.assertTrue(result['active'])
        self.assertIsNone(score_pickups([spell], {})[0]['points'])
        self.assertFalse(score_pickups([spell], {})[0]['points_complete'])


class EditorialTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        from backend.editorial import context
        parent = Path(__file__).resolve().parents[1] / 'data' / 'test-temp'
        parent.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.folder.name)
        stamp = datetime.now(timezone.utc).isoformat()
        self.data = {'league': {'key':'editorial-test', 'season':'2026'}, 'updated_at':stamp,
                     'teams': [{'key':key, 'name':key, 'manager':key} for key in 'ab'],
                     'matchups': [matchup(week, [('a',100+week),('b',99)], playoffs=False, consolation=False) for week in (1,2,3)]}
        self.assertEqual(context(self.data, self.root)['through_week'], 3)

    def tearDown(self):
        self.folder.cleanup()

    def edition(self, week, order='ab'):
        return dict(league_key='editorial-test', season='2026', through_week=week,
                    published_at=self.data['updated_at'], source_updated_at=self.data['updated_at'],
                    entries=[dict(team_key=key, rank=i+1, name=key, blurb='A specific weekly assessment based on actual completed results.') for i,key in enumerate(order)])

    def test_editions_persist_newest_two_and_cannot_be_replaced(self):
        from backend.editorial import publish, load_editions
        for week in (1,2,3):
            publish(self.edition(week, 'ba' if week==2 else 'ab'), self.data, self.root)
        editions = load_editions(self.data, self.root)
        self.assertEqual([e['through_week'] for e in editions], [3,2])
        self.assertEqual(editions[1]['entries'][0]['team_key'], 'b')
        with self.assertRaises(ValueError):
            publish(self.edition(3), self.data, self.root)
        self.assertEqual(len(list((self.root/'editorial-test').glob('week-*.json'))), 3)

    def test_partial_week_foreign_league_and_duplicate_team_rejected(self):
        from backend.editorial import validate, folder
        for invalid in (dict(self.edition(3), league_key='other'), dict(self.edition(3), through_week=4), self.edition(3,'aa')):
            with self.assertRaises(ValueError):
                validate(invalid, self.data)
        self.data['matchups'][-1]['status'] = 'midevent'
        with self.assertRaises(ValueError):
            validate(self.edition(3), self.data)
        with self.assertRaises(ValueError):
            folder('../outside', self.root)

    def test_invalid_file_does_not_hide_previous_edition(self):
        from backend.editorial import publish, load_editions, folder
        publish(self.edition(1), self.data, self.root)
        (folder('editorial-test',self.root)/'week-02.json').write_text('{')
        self.assertEqual(load_editions(self.data,self.root)[0]['through_week'], 1)

    def test_recent_all_stats_are_period_totals_instead_of_season_fallback(self):
        from datetime import date
        client = YahooClient(interval=0)
        client.get = Mock(return_value={'player': [[{'player_key':'p'}], {'player_points':{'total':'3'}},
            {'player_stats':{'stats':[{'stat':{'stat_id':'1','value':'2'}}]}}]})
        service = DashboardService(client)
        service.data = {'recent_pool':['p'], 'players':[{'key':'p','stats':{'1':999}}], 'recent':{}, 'stat_labels':{'1':'G'}}
        with patch.dict('sys.modules', {'backend.keys':SimpleNamespace(LEAGUE_ID='example')}), patch.object(service,'today',return_value=date(2026,11,15)):
            service._recent(7)
        self.assertEqual(service.data['recent']['7']['stats']['p']['1'], 14)
        self.assertEqual(service.data['recent']['7']['points']['p'], 21)
        service.client.get.reset_mock()
        with patch.dict('sys.modules', {'backend.keys':SimpleNamespace(LEAGUE_ID='example')}), patch.object(service,'today',return_value=date(2026,11,15)):
            service._recent(7)
        service.client.get.assert_not_called()


class RosterAndTradeTests(unittest.TestCase):
    def test_trade_individual_values_sum_to_side_total_and_keep_unknown_distinct(self):
        from backend.trade_analysis import trade_production
        from datetime import date,datetime
        from zoneinfo import ZoneInfo
        tx=dict(id='trade',type='trade',timestamp=str(int(datetime(2026,11,10,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp())),
            players=[dict(player=k,action='trade',destination='a') for k in ['p','q','r']])
        daily={'2026-11-10':{'p':10,'q':-2,'r':0},'2026-11-11':{'p':5,'q':-1,'r':0}}
        side=trade_production([tx],daily,date(2026,11,11))['trade']['a']
        self.assertEqual(side['players']['p']['points'],15)
        self.assertEqual(side['players']['q']['points'],-3)
        self.assertEqual(side['players']['r']['points'],0)
        self.assertEqual(sum(p['points'] for p in side['players'].values()),side['points'])
        del daily['2026-11-11']['p'];del daily['2026-11-10']['q'];del daily['2026-11-11']['q']
        side=trade_production([tx],daily,date(2026,11,11))['trade']['a']
        self.assertEqual(side['players']['p']['points'],10)
        self.assertFalse(side['players']['p']['complete'])
        self.assertIsNone(side['players']['q']['points'])
        self.assertEqual(side['players']['r']['points'],0)

    def test_zero_season_lines_do_not_hide_roster_totals_and_missing_lines_stay_unknown(self):
        from backend.player_periods import display_stats
        from backend.roster_analysis import roster_profiles
        data=self.roster_data()
        data['stat_labels']={'0':'GP','1':'G','2':'A','14':'SOG','15':'SH%'}
        for p in data['players']: p['stats']={'0':2,'1':1,'2':3,'14':5,'15':.2}
        zero=dict(key='zero',group='F',points=0,stats={k:None for k in data['stat_labels']})
        data['players'].append(zero);data['roster_owners']['zero']='a'
        for p in data['players']: p['stats']=display_stats(p['stats'],p['points'],data['stat_labels'])
        self.assertEqual(roster_profiles(data)[0]['stats']['GP'],6)
        self.assertEqual(zero['stats']['0'],0)
        self.assertIsNone(zero['stats']['15'])
        self.assertEqual(data['players'][0]['stats']['15'],20)
        self.assertEqual(display_stats({},0,data['stat_labels']),{})
        partial=display_stats({'0':None,'1':2},0,data['stat_labels'])
        self.assertIsNone(partial['0'])
        self.assertIsNone(display_stats({'0':None},5,data['stat_labels'])['0'])

    def test_more_goalies_do_not_improve_per_player_strength_and_stats_remain_totals(self):
        from backend.roster_analysis import roster_profiles
        data=dict(teams=[dict(key=k,name=k,manager=k) for k in 'ab'],rosters_loaded=True,
            roster_owners={'g1':'a','g2':'a','g3':'b'},stat_labels={'0':'GP','1':'G','2':'A','14':'SOG','25':'SV','19':'W'},
            players=[dict(key=k,group='G',points=v,stats={'0':10,'25':200,'19':5}) for k,v in [('g1',20),('g2',40),('g3',40)]])
        a,b=roster_profiles(data)
        self.assertEqual(a['points'],60)
        self.assertEqual(a['average_points'],30)
        self.assertEqual(a['rank'],2)
        self.assertEqual(a['total_rank'],1)
        self.assertEqual(a['groups']['G']['average_pos_rank'],2)
        self.assertEqual(b['groups']['G']['rank'],1)
        self.assertEqual(a['stats'],dict(GP=20,G=0,A=0,SOG=0,SV=400,W=10))

    @staticmethod
    def roster_data():
        return dict(teams=[dict(key=k,name=k,manager=k) for k in 'ab'],rosters_loaded=True,
            roster_owners={'f1':'a','d1':'a','g1':'a','f2':'b'},recent={'7':{'points':{'f1':2,'d1':3,'g1':-1,'f2':4,'fa':10}}},
            players=[dict(key=k,group=g,points=v,status='IR' if k=='d1' else '') for k,g,v in [('f1','F',10),('f2','F',10),('fa','F',30),('d1','D',20),('g1','G',-5)]])

    def test_roster_totals_use_current_owners_and_tied_ranks_include_free_agents(self):
        from backend.roster_analysis import roster_profiles
        rows={r['key']:r for r in roster_profiles(self.roster_data())}
        self.assertEqual(rows['a']['points'],25)
        self.assertEqual(rows['a']['count'],3)
        self.assertEqual(rows['a']['status_flags'],1)
        self.assertEqual(rows['a']['groups']['F']['rank'],1)
        self.assertEqual(rows['b']['groups']['F']['rank'],1)
        self.assertEqual(rows['a']['groups']['G']['rank'],1)
        self.assertIsNone(rows['b']['groups']['G']['rank'])
        self.assertEqual(rows['a']['player_ranks']['f1'],{'rank':3,'pos_rank':2})
        self.assertEqual(rows['b']['player_ranks']['f2'],{'rank':3,'pos_rank':2})

    def test_roster_period_changes_all_strength_ranks_and_missing_data_is_not_zero(self):
        from backend.roster_analysis import roster_profiles
        data=self.roster_data()
        rows={r['key']:r for r in roster_profiles(data,'7')}
        self.assertEqual(rows['a']['points'],4)
        self.assertEqual(rows['a']['rank'],2)
        self.assertEqual(rows['b']['rank'],1)
        self.assertAlmostEqual(rows['a']['average_points'],4/3,places=3)
        data['players'][0]['points']=None
        row=roster_profiles(data)[0]
        self.assertEqual(row['count'],3)
        self.assertEqual(row['covered'],2)
        self.assertIsNone(row['points'])
        data['roster_owners']['unknown']='a'
        row=roster_profiles(data)[0]
        self.assertEqual(row['count'],4)
        self.assertTrue(all(g['points'] is None for g in row['groups'].values()))

    def test_unknown_roster_coverage_is_not_an_empty_zero_point_team(self):
        from backend.roster_analysis import roster_profiles
        data=self.roster_data();data['rosters_loaded']=False;data['roster_owners']={}
        self.assertTrue(all(r['points'] is None and r['rank'] is None for r in roster_profiles(data)))

    def test_trade_production_uses_processed_date_and_complete_days_even_after_drop(self):
        from backend.trade_analysis import trade_production
        from datetime import date,datetime
        from zoneinfo import ZoneInfo
        stamp=str(int(datetime(2026,11,10,1,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()))
        tx={'id':'t','type':'trade','timestamp':stamp,'players':[dict(player='p',action='trade',destination='a'),dict(player='q',action='trade',destination='b')]}
        result=trade_production([tx],{'2026-11-10':{'p':4,'q':-3},'2026-11-11':{'p':6,'q':1}},date(2026,11,11))['t']
        self.assertEqual(result['a']['points'],10)
        self.assertEqual(result['b']['points'],-2)
        self.assertTrue(result['a']['complete'])
        self.assertEqual(result['a']['expected'],2)
        partial=trade_production([tx],{'2026-11-10':{'p':4}},date(2026,11,11))['t']
        self.assertEqual(partial['a']['points'],4)
        self.assertFalse(partial['a']['complete'])
        self.assertIsNone(partial['b']['points'])

    def test_trade_same_day_has_zero_completed_production(self):
        from backend.trade_analysis import trade_production
        from datetime import date,datetime
        from zoneinfo import ZoneInfo
        tx=dict(id='t',type='trade',timestamp=str(int(datetime(2026,11,12,1,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp())),players=[dict(player='p',action='trade',destination='a')])
        side=trade_production([tx],{},date(2026,11,11))['t']['a']
        self.assertEqual(side['points'],0)
        self.assertTrue(side['complete'])


class ManualEditionPrivacyTests(unittest.TestCase):
    def test_private_editions_are_validated_and_missing_file_is_empty(self):
        from backend.editorial import load_jordog
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data={'league':{'key':'example'},'teams':[{'key':'a'},{'key':'b'}]}
            self.assertEqual(load_jordog(data,root),{})
            (root/'example').mkdir()
            (root/'example/editions.json').write_text(json.dumps({'2026-10':['a','b'],'2026-11':['a','a'],'bad':['b','a']}))
            self.assertEqual(load_jordog(data,root),{'2026-10':['a','b']})

class CreditedTests(unittest.TestCase):
    @staticmethod
    def fixture():
        teams=[dict(key=k,name=k,manager=k) for k in 'ab']
        data=dict(teams=teams,players=[dict(key=k,group=g,points=100,stats={}) for k,g in [('p','F'),('q','D'),('g','G')]],
            roster_owners={'p':'b','q':'a','g':'a'},stat_labels={'0':'GP','1':'G','14':'SOG'},
            matchups=[dict(week=1,start='2026-11-01',end='2026-11-02',status='postevent',teams=[dict(key='a',points=18),dict(key='b',points=24)])])
        lineups={'2026-11-01':{'a':[dict(player='p',slot='C'),dict(player='q',slot='BN'),dict(player='g',slot='IR')],'b':[dict(player='q',slot='D')]},
                 '2026-11-02':{'a':[dict(player='q',slot='D')],'b':[dict(player='p',slot='RW')]}}
        daily={'2026-11-01':{'p':10,'q':4,'g':500},'2026-11-02':{'p':20,'q':8}}
        stats={day:{k:{'0':1,'1':1,'14':5} for k in values} for day,values in daily.items()}
        return data,lineups,daily,stats

    def test_started_contributions_follow_moves_keep_former_players_and_exclude_bench_ir(self):
        from backend.credited import credited_profiles
        from datetime import date
        result=credited_profiles(*self.fixture(),date(2026,11,2))
        a,b=result['profiles']['season']
        self.assertEqual(a['points'],18)
        self.assertEqual(b['points'],24)
        self.assertEqual(a['count'],2)
        self.assertEqual(a['average_points'],9)
        self.assertEqual(a['groups']['F']['points'],10)
        self.assertEqual(a['groups']['D']['points'],8)
        self.assertEqual(a['groups']['G']['points'],0)
        self.assertEqual(a['stats']['GP'],2)
        self.assertTrue(result['coverage']['season']['complete'])
        self.assertEqual(result['reconciliation']['matched'],2)

    def test_missing_lineup_or_player_day_is_not_zero_and_disables_incomplete_ranks(self):
        from backend.credited import credited_profiles
        from datetime import date
        data,lineups,daily,stats=self.fixture()
        del lineups['2026-11-02']['a']
        result=credited_profiles(data,lineups,daily,stats,date(2026,11,2))
        self.assertFalse(result['coverage']['season']['complete'])
        self.assertIsNone(result['profiles']['season'][0]['points'])
        self.assertTrue(all(r['rank'] is None for r in result['profiles']['season']))
        data,lineups,daily,stats=self.fixture();del daily['2026-11-02']['q']
        result=credited_profiles(data,lineups,daily,stats,date(2026,11,2))
        self.assertIsNone(result['profiles']['season'][0]['points'])

    def test_zero_game_slots_do_not_inflate_contributor_average(self):
        from backend.credited import credited_profiles
        from datetime import date
        data,lineups,daily,stats=self.fixture()
        lineups['2026-11-02']['a'].append(dict(player='g',slot='G'))
        daily['2026-11-02']['g']=0;stats['2026-11-02']['g']={'0':0}
        result=credited_profiles(data,lineups,daily,stats,date(2026,11,2))
        self.assertEqual(result['profiles']['season'][0]['count'],2)
        self.assertEqual(result['profiles']['season'][0]['average_points'],9)

    def test_weighted_points_handle_no_stat_days_and_preserve_missing_values(self):
        from backend.credited import weighted_points
        self.assertEqual(weighted_points({'0':1,'g':2,'ga':3},{'g':6,'ga':-3}),3)
        self.assertEqual(weighted_points({'0':None,'g':None},{'g':6}),0)
        self.assertEqual(weighted_points({'0':0,'g':None},{'g':6}),0)
        self.assertIsNone(weighted_points({}, {'g':6}))
        self.assertIsNone(weighted_points({'0':1,'g':None},{'g':6}))
        self.assertIsNone(weighted_points({'0':1,'1':2},{'1':6,'14':.7},'F'))
        self.assertEqual(weighted_points({'0':1,'19':1},{'1':6,'19':5},'G'),5)

    def test_lineup_import_reuses_saved_dates_and_never_fetches_on_cached_repeat(self):
        from datetime import date
        data,lineups,daily,stats=self.fixture()
        data['scoring_weights']={'1':6}
        client=YahooClient(interval=0);client.get=Mock()
        service=DashboardService(client);service.data=data
        service.daily_lineups=lineups;service.player_daily=daily;service.player_daily_stats=stats
        with patch.object(service,'today',return_value=date(2026,11,3)):
            service._credited('league/477.l.example')
        client.get.assert_not_called()
        self.assertTrue(service.credited['coverage']['season']['complete'])

    def test_wrong_historical_date_is_rejected_without_caching(self):
        from datetime import date
        data,_,_,_=self.fixture();data['scoring_weights']={'1':6}
        client=YahooClient(interval=0)
        client.get=Mock(return_value={'teams':[{'team':{'team_key':k,'roster':{'date':'wrong'}}} for k in 'ab']})
        service=DashboardService(client);service.data=data
        with patch.object(service,'today',return_value=date(2026,11,3)), self.assertRaises(YahooError):
            service._credited('league/477.l.example')
        self.assertEqual(service.daily_lineups,{})

    def test_daily_verification_is_separate_from_weekly_corrections(self):
        from backend.credited import credited_profiles
        from datetime import date
        data,lineups,daily,stats=self.fixture()
        data['daily_by_week']={'1':[dict(date='2026-11-01',scores={'a':10,'b':4}),dict(date='2026-11-02',scores={'a':8,'b':20})]}
        data['matchups'][0]['teams'][0]['points']=99
        result=credited_profiles(data,lineups,daily,stats,date(2026,11,2))
        self.assertEqual(result['reconciliation']['daily_checked'],4)
        self.assertEqual(result['reconciliation']['daily_matched'],4)
        self.assertEqual(result['reconciliation']['matched'],1)

    def test_mismatching_week_is_visible_in_reconciliation(self):
        from backend.credited import credited_profiles
        from datetime import date
        data,lineups,daily,stats=self.fixture()
        data['matchups'][0]['teams'][0]['points']=99
        result=credited_profiles(data,lineups,daily,stats,date(2026,11,2))
        self.assertEqual(result['reconciliation']['checked'],2)
        self.assertEqual(result['reconciliation']['matched'],1)
        self.assertEqual(result['reconciliation']['differences'][0]['calculated'],18)


if __name__ == '__main__':
    unittest.main()
