"""Pure calculations. Missing and provisional scores never become finalized zeros."""
from collections import defaultdict
from statistics import mean, pstdev
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def enrich_teams(teams, matchups):
    results = {t['key']: dict(t, all_wins=0, all_losses=0, all_ties=0,
                               expected_wins=None, completed_weeks=0, average=None,
                               schedule_strength=None, margin=None, consistency=None) for t in teams}
    weeks = defaultdict(list)
    for matchup in matchups:
        if matchup['status'] == 'postevent' and not matchup.get('playoffs') and not matchup.get('consolation'):
            weeks[matchup['week']].append(matchup)
    scores, opponents, margins = defaultdict(list), defaultdict(list), defaultdict(list)
    expected = defaultdict(float)
    for matches in weeks.values():
        entries = [t for m in matches for t in m['teams']]
        # Complete league weeks only, so every team has the same comparison pool.
        if len(entries) != len(teams) or len({t['key'] for t in entries}) != len(teams):
            continue
        if any(t['points'] is None for t in entries):
            continue
        for team in entries:
            others = [x for x in entries if x['key'] != team['key']]
            r = results[team['key']]
            wins = sum(team['points'] > x['points'] for x in others)
            ties = sum(team['points'] == x['points'] for x in others)
            r['all_wins'] += wins
            r['all_ties'] += ties
            r['all_losses'] += len(others) - wins - ties
            r['completed_weeks'] += 1
            expected[team['key']] += (wins + ties * .5) / len(others)
            scores[team['key']].append(team['points'])
        for m in matches:
            a, b = m['teams']
            for team, opponent in ((a, b), (b, a)):
                opponents[team['key']].append(opponent['points'])
                margins[team['key']].append(team['points'] - opponent['points'])
    for key, r in results.items():
        if scores[key]:
            r.update(expected_wins=round(expected[key], 4), average=mean(scores[key]),
                     schedule_strength=mean(opponents[key]), margin=mean(margins[key]),
                     consistency=pstdev(scores[key]))
    return list(results.values())


def records(matchups):
    completed = [m for m in matchups if m['status'] == 'postevent' and not m.get('playoffs')
                 and not m.get('consolation') and all(t['points'] is not None for t in m['teams'])]
    entries = [(t, m) for m in completed for t in m['teams']]
    top = max(entries, key=lambda x: x[0]['points']) if entries else None
    non_ties = [m for m in completed if m['teams'][0]['points'] != m['teams'][1]['points']]
    closest = min(non_ties, key=lambda m: abs(m['teams'][0]['points'] - m['teams'][1]['points'])) if non_ties else None
    return {'highest': {'team': top[0]['name'], 'points': top[0]['points'], 'week': top[1]['week']} if top else None,
            'closest': {'teams': [t['name'] for t in closest['teams']], 'margin': abs(closest['teams'][0]['points'] - closest['teams'][1]['points']), 'week': closest['week']} if closest else None}


def biggest_comeback(matchups, daily_by_week):
    """Largest end-of-day deficit overcome to WIN a finalized regular-season matchup."""
    best = None
    covered = 0
    for matchup in matchups:
        if matchup['status'] != 'postevent' or matchup.get('playoffs') or matchup.get('consolation'):
            continue
        a, b = matchup['teams']
        if a['points'] is None or b['points'] is None or a['points'] == b['points']:
            continue
        winner, loser = (a, b) if a['points'] > b['points'] else (b, a)
        days = {d['date']: d['scores'] for d in daily_by_week.get(str(matchup['week']), [])}
        start, end = date.fromisoformat(matchup['start']), date.fromisoformat(matchup['end'])
        expected = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
        if any(day not in days or days[day].get(winner['key']) is None or days[day].get(loser['key']) is None for day in expected):
            continue
        won, lost, deficit, deficit_day = 0, 0, 0, None
        for day in expected:
            won += days[day][winner['key']]
            lost += days[day][loser['key']]
            if lost - won > deficit:
                deficit, deficit_day = lost - won, day
        # Historic stat corrections or differing coverage must not produce an invented record.
        if abs(won - winner['points']) > .15 or abs(lost - loser['points']) > .15:
            continue
        covered += 1
        if deficit > 0 and (best is None or deficit > best['deficit']):
            best = {'team': winner['name'], 'opponent': loser['name'], 'week': matchup['week'],
                    'deficit': round(deficit, 2), 'date': deficit_day}
    return {'record': best, 'covered_matchups': covered}


def pickup_spells(transactions, through):
    """Inclusive acquisition date through day BEFORE next exit; never includes next owner's production."""
    events = sorted(transactions, key=lambda t: (int(t['timestamp']), t['id']))
    zone = ZoneInfo('America/Los_Angeles')
    spells = []
    for i, tx in enumerate(events):
        added = datetime.fromtimestamp(int(tx['timestamp']), zone).date()
        for p in tx['players']:
            if p['action'] != 'add' or p['source_type'] not in ('waivers', 'freeagents') or not p['destination']:
                continue
            end = through
            active = True
            for future in events[i+1:]:
                exits = [x for x in future['players'] if x['player'] == p['player'] and
                         (x['source'] == p['destination'] or x['action'] == 'add')]
                if exits:
                    end = min(end, datetime.fromtimestamp(int(future['timestamp']), zone).date() - timedelta(days=1))
                    active = False
                    break
            spells.append({'id': f"{tx['id']}:{p['player']}", 'player': p['player'], 'name': p['name'],
                           'team': p['destination'], 'source': p['source_type'],
                           'start': added.isoformat(), 'end': end.isoformat(),
                           'days': max(0, (end - added).days + 1), 'active': active})
    return spells


def score_pickups(spells, daily):
    result = []
    for spell in spells:
        start = date.fromisoformat(spell['start'])
        values = [daily.get((start+timedelta(days=i)).isoformat(), {}).get(spell['player']) for i in range(spell['days'])]
        known = [v for v in values if v is not None]
        result.append(dict(spell, points=round(sum(known), 2) if known or not values else None,
                           points_complete=len(known) == len(values), covered_days=len(known)))
    return sorted(result, key=lambda p: (p['points'] is not None, p['points'] or 0), reverse=True)
