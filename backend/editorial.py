"""Dated, AI-authored weekly editions. Reading/publishing never contacts Yahoo.

python -m backend.editorial context
python -m backend.editorial publish path/to/draft.json
"""
import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITION_ROOT = ROOT / 'data' / 'editorial' / 'drake'


def folder(league, root=EDITION_ROOT):
    if not isinstance(league, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', league):
        raise ValueError('Invalid league key.')
    return Path(root) / league


def validate(edition, data):
    if edition.get('league_key') != data['league']['key'] or str(edition.get('season')) != data['league']['season']:
        raise ValueError('Edition must belong to the loaded league and season.')
    week = edition.get('through_week')
    completed = {m['week'] for m in data.get('matchups', []) if m['status'] == 'postevent' and not m['playoffs'] and not m['consolation']}
    if type(week) is not int or week not in completed:
        raise ValueError('Edition needs a completed regular-season week.')
    matches = [m for m in data['matchups'] if m['week'] == week]
    keys = {t['key'] for t in data['teams']}
    if any(m['status'] != 'postevent' or m['playoffs'] or m['consolation'] or any(t['points'] is None for t in m['teams']) for m in matches) or {t['key'] for m in matches for t in m['teams']} != keys:
        raise ValueError('Week coverage is incomplete.')
    entries = edition.get('entries', [])
    if len(entries) != len(keys) or {e.get('team_key') for e in entries} != keys or [e.get('rank') for e in entries] != list(range(1, len(keys)+1)):
        raise ValueError('Rank every league team exactly once, in order.')
    for entry in entries:
        if not isinstance(entry.get('blurb'), str) or not 30 <= len(entry['blurb']) <= 1200:
            raise ValueError('Each team needs a short, substantial writeup.')
        entry['blurb'] = entry['blurb'].replace('\u2014', '-')
    for key in ('published_at', 'source_updated_at'):
        stamp = datetime.fromisoformat(edition[key].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            raise ValueError('Edition dates must be actual timestamps with time zones.')
    return edition


def load_editions(data, root=EDITION_ROOT):
    """Keep all editions on disk; only the newest two are needed for rank movement."""
    result = []
    for path in sorted(folder(data['league']['key'], root).glob('week-*.json'), reverse=True):
        try:
            edition = json.loads(path.read_text(encoding='utf-8'))
            validate(edition, data)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue  # A partial/invalid draft cannot replace the last published edition.
        result.append(edition)
        if len(result) == 2:
            break
    return result


def load_jordog(data, root=ROOT / 'data' / 'editorial' / 'jordog'):
    """Private manual editions belong to runtime data, never the frontend bundle."""
    path = folder(data['league']['key'], root) / 'editions.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        keys = {team['key'] for team in data['teams']}
        if not isinstance(value,dict): return {}
        return {month:rows for month,rows in value.items()
                if re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month) and isinstance(rows,list)
                and all(isinstance(key,str) for key in rows) and len(rows)==len(keys) and set(rows)==keys}
    except (OSError, ValueError, TypeError):
        return {}


def context(data, root=EDITION_ROOT):
    keys = {t['key'] for t in data['teams']}
    weeks = sorted({m['week'] for m in data['matchups'] if m['status'] == 'postevent' and not m['playoffs'] and not m['consolation']})
    complete = []
    for week in weeks:
        matches = [m for m in data['matchups'] if m['week'] == week]
        if all(m['status'] == 'postevent' and not m['playoffs'] and not m['consolation'] and all(t['points'] is not None for t in m['teams']) for m in matches) and {t['key'] for m in matches for t in m['teams']} == keys:
            complete.append(week)
    if not complete:
        raise ValueError('No complete regular-season week to publish yet.')
    teams = []
    for team in data['teams']:
        scores = [{'week': m['week'], 'points': next(t['points'] for t in m['teams'] if t['key'] == team['key'])}
                  for m in data['matchups'] if m['week'] in complete[-3:] and any(t['key'] == team['key'] for t in m['teams'])]
        teams.append({k: team.get(k) for k in ('key', 'name', 'manager', 'rank', 'wins', 'losses', 'ties', 'pf', 'pa', 'expected_wins', 'completed_weeks', 'average', 'schedule_strength')} | {'recent_scores': scores})
    return dict(league_key=data['league']['key'], season=data['league']['season'], through_week=max(complete),
                source_updated_at=data['updated_at'], generated_at=datetime.now(timezone.utc).isoformat(),
                teams=teams, previous_editions=load_editions(data, root),
                metric_note='xWins/average use complete regular-season weeks; official record/PF/PA can include the live week.')


def cached_dashboard():
    from .keys import LEAGUE_ID
    path = ROOT / 'data' / 'dashboard.sqlite3'
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('SELECT payload FROM dashboard WHERE league = ?', (LEAGUE_ID,)).fetchone()
    if row is None:
        raise ValueError('Open and refresh the local dashboard before publishing.')
    return json.loads(row[0])['data']


def publish(edition, data, root=EDITION_ROOT):
    edition = validate(edition, data)
    # Each weekly article is frozen. Normal dashboard refreshes cannot rewrite it.
    target = folder(data['league']['key'], root) / f"week-{edition['through_week']:02}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('This week already has a published edition.')
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['context', 'publish'])
    parser.add_argument('draft', nargs='?')
    args = parser.parse_args()
    data = cached_dashboard()
    if args.action == 'context':
        print(json.dumps(context(data), ensure_ascii=False, indent=2))
    elif not args.draft:
        parser.error('publish needs a draft JSON path')
    else:
        print(publish(json.loads(Path(args.draft).read_text(encoding='utf-8')), data))


if __name__ == '__main__':
    main()
