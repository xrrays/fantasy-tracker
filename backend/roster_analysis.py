"""Current-roster strength, distinct from fantasy-team lineup credit. No fetching."""
from statistics import mean


def roster_profiles(data, period='season'):
    players = data.get('players', [])
    owners = data.get('roster_owners', {})
    recent = data.get('recent', {}).get(str(period), {})
    labels = data.get('stat_labels', {})
    def stats(p):
        return p.get('stats', {}) if period == 'season' else recent.get('stats', {}).get(p['key'], {})
    def total_stat(pool, label):
        ids = [key for key,value in labels.items() if value.upper() == label]
        eligible = [p for p in pool if label not in ('SV','W') or p['group']=='G']
        if label in ('G','A','SOG'): eligible = [p for p in pool if p['group']!='G']
        values = [next((stats(p)[key] for key in ids if stats(p).get(key) is not None), None) for p in eligible]
        return sum(values) if ids and all(v is not None for v in values) else None
    def points(p):
        return p.get('points') if period == 'season' else recent.get('points', {}).get(p['key'])
    def ranks_for(pool):
        ordered=sorted((p for p in pool if points(p) is not None),key=points,reverse=True)
        result={}
        previous=None
        rank=0
        for i,p in enumerate(ordered,1):
            if points(p)!=previous:
                rank=i
            result[p['key']]=rank
            previous=points(p)
        return result
    ranks = ranks_for(players)
    position_ranks = {}
    for group in ('F','D','G'):
        position_ranks.update(ranks_for([p for p in players if p['group']==group]))
    result = []
    for team in data.get('teams', []):
        roster = [p for p in players if owners.get(p['key']) == team['key']]
        missing = len([key for key,owner in owners.items() if owner == team['key'] and key not in {p['key'] for p in players}])
        def group_profile(pool, unknown=0):
            values = [points(p) for p in pool]
            known = [v for v in values if v is not None]
            pos = [position_ranks.get(p['key']) for p in pool if position_ranks.get(p['key']) is not None]
            return dict(count=len(pool)+unknown, covered=len(known),
                points=round(sum(known),2) if not unknown and len(known)==len(values) else None,
                average_points=round(mean(known),4) if pool and not unknown and len(known)==len(values) else None,
                stats={label:total_stat(pool,label) if not unknown else None for label in ('GP','G','A','SOG','SV','W')},
                average_pos_rank=round(mean(pos),1) if pos and len(pos)==len(pool) and not unknown else None,
                top100=sum(ranks.get(p['key']) is not None and ranks.get(p['key']) <= 100 for p in pool))
        groups = {group:group_profile([p for p in roster if p['group']==group]) for group in ('F','D','G')}
        if missing:
            for bucket in groups.values(): bucket.update(points=None,average_points=None)
        result.append(dict(key=team['key'], name=team['name'], manager=team['manager'],
            **group_profile(roster,missing), groups=groups,
            status_flags=sum(bool(p.get('status')) for p in roster),
            player_ranks={p['key']:dict(rank=ranks.get(p['key']),pos_rank=position_ranks.get(p['key'])) for p in roster}))
    if not data.get('rosters_loaded'):
        for row in result:
            row.update(points=None,average_points=None)
            for bucket in row['groups'].values(): bucket.update(points=None,average_points=None)
    for row in result:
        row['total_rank'] = None if row['points'] is None else 1+sum(x['points'] is not None and x['points']>row['points'] for x in result)
        row['rank'] = None if row['average_points'] is None else 1+sum(x['average_points'] is not None and x['average_points']>row['average_points'] for x in result)
        for group in ('F','D','G'):
            bucket=row['groups'][group]
            bucket['total_rank'] = None if bucket['points'] is None or not bucket['count'] else 1+sum(
                x['groups'][group]['count'] and x['groups'][group]['points'] is not None and x['groups'][group]['points']>bucket['points'] for x in result)
            bucket['rank'] = None if bucket['average_points'] is None else 1+sum(
                x['groups'][group]['average_points'] is not None and x['groups'][group]['average_points']>bucket['average_points'] for x in result)
    return result
