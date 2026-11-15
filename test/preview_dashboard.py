"""Explicit offline layout preview. All scores/players are synthetic; never contacts Yahoo.

Run separately from the production backend: python test/preview_dashboard.py
Then run npm run dev:ui in frontend. Do not use this as a league data source.
"""
import json
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.roster_analysis import roster_profiles
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from random import Random


def preview_data():
    rng = Random(16)
    managers = [f'Manager {i:02}' for i in range(1,17)]
    teams = [dict(key=f'preview.t.{i}', name=f'Preview Team {i:02}', manager=manager,
                  rank=i, division='', wins=7-i//3, losses=i//3, ties=0,
                  win_pct=(7-i//3)/7, pf=2100-i*39.6, pa=1850+i*9.5,
                  moves=20+i, trades=i%4, all_wins=90-i*4, all_losses=i*4,
                  all_ties=0, expected_wins=5.8-i*.22, completed_weeks=6,
                  average=350-i*6.6, schedule_strength=310+i*1.6,
                  margin=40-i*8.2, consistency=15+i) for i, manager in enumerate(managers, 1)]
    labels = {str(i): label for i, label in enumerate(['GP', 'G', 'A', 'PTS', '+/-', 'PIM', 'PPP', 'SOG', 'HIT', 'BLK', 'W', 'SV', 'GA', 'GAA', 'SV%', 'SO'])}
    players = []
    owners = {}
    for i in range(1, 349):
        group = 'G' if i%7 == 0 else 'D' if i%3 == 0 else 'F'
        stats = {str(j): rng.randint(0, 50) for j in ([0, 10, 11, 12, 13, 14, 15] if group == 'G' else range(10))}
        if group == 'G': stats.update({'13': 2.57, '14': .917})
        players.append(dict(key=f'p{i}', name=f'Preview {"Goalie" if group == "G" else "Skater"} {i:03}',
                            nhl_team=['EDM', 'CGY', 'TOR', 'MTL', 'WPG', 'VAN', 'OTT'][i%7],
                            group=group, positions=['G'] if group == 'G' else ['D'] if group == 'D' else ['C', 'LW'],
                            image='', status='Injured Reserve' if i%31 == 0 else 'Not Active' if i%29 == 0 else '', points=round(365-i*.83, 2),
                            stats=stats, rank=i))
        if i <= 288: owners[f'p{i}'] = teams[(i+2)%16]['key']
    matchups = []
    daily = []
    for i in range(0, 16, 2):
        matchups.append(dict(week=7, status='midevent', start='2026-11-09', end='2026-11-15',
                             playoffs=False, consolation=False, teams=[
                                 dict(key=teams[j]['key'], name=teams[j]['name'], points=300+j*4.75)
                                 for j in (i, i+1)]))
    for d in range(5):
        daily.append(dict(date=f'2026-11-{9+d:02}', scores={t['key']: 25+d*4+i*1.5 for i,t in enumerate(teams)}))
    moves = []
    for i in range(140):
        trade = i%5 == 0
        a, b = teams[i%16], teams[(i+1)%16]
        p = players[i]
        moved = [dict(player=p['key'], name=p['name'], action='trade' if trade else 'add',
                      source_type='team' if trade else 'waivers' if i%4==0 else 'freeagents', source=a['key'] if trade else None, destination=b['key'])]
        if trade:
            q = players[i+1]
            moved.append(dict(player=q['key'], name=q['name'], action='trade', source_type='team', source=b['key'], destination=a['key']))
        else:
            q = players[i+1]
            moved.append(dict(player=q['key'], name=q['name'], action='drop', source_type='team', source=b['key'], destination=None))
        moves.append(dict(id=f'tx{i}', type='trade' if trade else 'add', timestamp=str(1794700000-i*7200), players=moved))
    pickups = [dict(id=f'pickup{i}', player=p['key'], name=p['name'], team=teams[i%16]['key'],
                    source='waivers' if i%4 == 0 else 'freeagents', start='2026-11-01', end='2026-11-13',
                    days=13, covered_days=9 if i%7 == 0 else 13, points=round(90-i*.61, 2),
                    active=i%3 == 0, points_complete=i%7 != 0) for i,p in enumerate(players[:100])]
    return dict(preview=True, league=dict(key='preview', season='2026', week=7, name='Offline Layout Preview'),
                teams=teams, players=players, matchups=matchups, daily=daily, daily_by_week={'7':daily},
                draft=[dict(player=p['key'], team=teams[i%16]['key'], pick=i+1, round=i//16+1) for i,p in enumerate(players[:272])],
                transactions=moves, transactions_complete=True, pickups=pickups, pickups_loaded=False,
                roster_owners=owners, rosters_loaded=True, recent_pool=[p['key'] for p in players[:87]],
                recent={'7':dict(points={p['key']:round(40-i*.3, 2) for i,p in enumerate(players[:87])},
                                 stats={p['key']:{k:round(v/5, 3) if labels[k] not in ('GAA', 'SV%') else v for k,v in p['stats'].items()} for p in players[:87]},
                                 start='2026-11-07', end='2026-11-13', pool_size=87, complete=True, fetched_at='2026-11-15T08:00:00Z')},
                stat_labels=labels, updated_at=datetime.now(timezone.utc).isoformat(), players_loaded=True,
                managers_loaded=True, coverage=['Synthetic offline layout data'],
                drake_editions=[dict(league_key='preview', season='2026', through_week=week, published_at=f'2026-11-{day}T15:00:00Z', source_updated_at=f'2026-11-{day}T14:00:00Z',
                    entries=[dict(team_key=t['key'], rank=i+1, name=t['name'], blurb=f"{t['average']:.1f} points per completed week and {t['expected_wins']:.2f} xWins give this synthetic team a measurable scoring profile. The spreadsheet is convinced; the group chat is still conducting its own investigation.") for i,t in enumerate(teams if week==6 else teams[2:]+teams[:2])]) for week,day in [(6,'15'),(5,'08')]],
                records=dict(highest=dict(team=teams[0]['name'], points=412.55, week=6),
                             closest=dict(teams=[teams[4]['name'],teams[5]['name']], margin=.75, week=5),
                             comeback=dict(team=teams[2]['name'], opponent=teams[1]['name'], week=4, deficit=70.45, date='2026-11-01'), comeback_covered=21))


class PreviewHandler(BaseHTTPRequestHandler):
    data = preview_data()

    def do_GET(self):
        self.data['roster_profiles']={period:roster_profiles(self.data,period) for period in ('season','7','14','30')}
        self.data['trade_production']={tx['id']:{team:dict(points=round(35.5+i*2.3,2),complete=True,covered=10,expected=10,start='2026-11-01',end='2026-11-14') for team in {p['destination'] for p in tx['players']}} for i,tx in enumerate(self.data['transactions']) if tx['type']=='trade'}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(dict(data=self.data, running=False, error=None,
                                        message='Offline preview', requests=0, budget=240)).encode())

    def do_POST(self):
        if '/recent/' in self.path:
            days = int(self.path.rsplit('/',1)[1])
            self.data['recent'][str(days)] = dict(self.data['recent']['7'], points={k:round(v*days/7, 2) for k,v in self.data['recent']['7']['points'].items()},
                stats={player:{k:round(v*days/7, 3) if self.data['stat_labels'][k] not in ('GAA', 'SV%') else v for k,v in values.items()} for player,values in self.data['recent']['7']['stats'].items()})
        self.do_GET()

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    print(f'Offline SYNTHETIC preview API: http://127.0.0.1:{args.port}', flush=True)
    HTTPServer(('127.0.0.1', args.port), PreviewHandler).serve_forever()
