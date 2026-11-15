"""Small adapters for Yahoo's mixed list/dict response structure; whitelist public UI fields."""
from urllib.parse import urlsplit


def player_image(image):
    """Yahoo wraps a larger public headshot in a 46×60 thumbnail URL."""
    if not isinstance(image, str) or not image.startswith('https://'):
        return ''
    marker = '/https://s.yimg.com/'
    if urlsplit(image).hostname == 's.yimg.com' and marker in image:
        source = 'https://s.yimg.com/' + image.rsplit(marker, 1)[1]
        if urlsplit(source).hostname == 's.yimg.com' and '/players' in urlsplit(source).path:
            return source
    return image
def find(node, key):
    if isinstance(node, dict):
        for k, value in node.items():
            if k == key:
                yield value
            else:
                yield from find(value, key)
    elif isinstance(node, list):
        for item in node:
            yield from find(item, key)


def first(node, key, default=None):
    return next(find(node, key), default)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stat_number(value):
    if isinstance(value, str) and ':' in value:
        parts = value.split(':')
        if len(parts) == 2:
            minutes, seconds = number(parts[0]), number(parts[1])
            if minutes is not None and seconds is not None and 0 <= seconds < 60:
                return minutes + seconds / 60
        return None
    return number(value)


def team(node):
    standing = first(node, 'team_standings', {})
    outcomes = standing.get('outcome_totals', {})
    managers = list(find(first(node, 'managers', []), 'nickname'))
    return {'key': first(node, 'team_key'), 'name': first(node, 'name', 'Unnamed Team'),
            'manager': ' / '.join(str(n) for n in managers) or first(node, 'name', 'Manager'),
            'rank': number(standing.get('rank')), 'division': str(first(node, 'division_id', '-')),
            'wins': number(outcomes.get('wins')), 'losses': number(outcomes.get('losses')),
            'ties': number(outcomes.get('ties')), 'win_pct': number(outcomes.get('percentage')),
            'pf': number(standing.get('points_for')), 'pa': number(standing.get('points_against')),
            'moves': number(first(node, 'number_of_moves')), 'trades': number(first(node, 'number_of_trades'))}


def matchups(raw):
    out = []
    for m in find(raw, 'matchup'):
        entries = []
        for t in find(m, 'team'):
            entries.append({'key': first(t, 'team_key'), 'name': first(t, 'name'),
                            'points': number(first(t, 'team_points', {}).get('total'))})
        if len(entries) == 2:
            out.append({'week': int(m.get('week', 0)), 'status': m.get('status', 'unknown'),
                        'playoffs': str(m.get('is_playoffs', '0')) == '1',
                        'consolation': str(m.get('is_consolation', '0')) == '1',
                        'start': m.get('week_start'), 'end': m.get('week_end'), 'teams': entries})
    return out


def player(raw):
    positions = [p for p in find(first(raw, 'eligible_positions', []), 'position') if p != 'Util']
    stats = {str(s['stat_id']): stat_number(s.get('value')) for s in find(first(raw, 'player_stats', {}), 'stat') if 'stat_id' in s}
    rank_values = list(find(first(raw, 'player_ranks', []), 'player_rank'))
    season_rank = next((number(x.get('rank_value')) for x in rank_values if x.get('rank_type') == 'S'), None)
    image = first(raw, 'image_url', '')
    if not isinstance(image, str) or not image.startswith('https://'):
        image = ''
    return {'key': first(raw, 'player_key'), 'name': first(first(raw, 'name', {}), 'full', 'Unknown'),
            'nhl_team': first(raw, 'editorial_team_abbr', ''), 'positions': positions,
            'group': 'G' if 'G' in positions else 'D' if 'D' in positions else 'F',
            'image': player_image(image), 'image_fallback': image,
            'status': first(raw, 'status_full', first(raw, 'status', '')) or '',
            'status_code': first(raw, 'status', '') or '',
            'points': number(first(raw, 'player_points', {}).get('total')), 'stats': stats, 'rank': season_rank}
