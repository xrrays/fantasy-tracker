"""Historical starting-lineup contribution. Pure calculations, no fetching."""
from datetime import date, timedelta
from .roster_analysis import roster_profiles
from .player_periods import aggregate_stats, zero_point_day

ACTIVE = {'C','LW','RW','F','D','G','Util'}
INACTIVE = {'BN','IR','IR+','NA','IL','IL+'}


def weighted_points(stats, weights, group=None):
    if not stats:
        return None
    # An explicitly returned all-blank game stat line is Yahoo's no-stat-day form.
    if all(v is None for v in stats.values()):
        return 0.0
    if stats.get('0')==0 and all(stats.get(k) in (None,0) for k in weights):
        return 0.0
    if group:
        opposite={str(i) for i in (list(range(1,18))+[29,31,32,33,34] if group=='G' else list(range(18,29))+[30])}
        applicable=set(weights)-opposite
        if any(stats.get(k) is None for k in applicable):
            return None
    if any(k in stats and stats[k] is None for k in weights):
        return None
    return round(sum(stats.get(k,0)*weight for k,weight in weights.items()),2)


def credited_profiles(data, lineups, daily, daily_stats, through):
    starts=[m['start'] for m in data.get('matchups',[]) if m.get('start')]
    if not starts:
        return {'profiles':{},'coverage':{},'reconciliation':{'checked':0,'matched':0}}
    season_start=date.fromisoformat(min(starts))
    labels=data.get('stat_labels',{})
    identities={p['key']:p for p in data.get('players',[])}
    gp_ids=[k for k,v in labels.items() if v=='GP']

    def build(start, end):
        days=[(start+timedelta(days=i)).isoformat() for i in range(max(0,(end-start).days+1))]
        players=[]; owners={}; coverage={}; contributions={}
        for team in data['teams']:
            grouped={}; covered=0
            for day in days:
                entries=lineups.get(day,{}).get(team['key'])
                if entries is None: continue
                valid=True
                for entry in entries:
                    if entry['slot'] in INACTIVE: continue
                    if entry['slot'] not in ACTIVE: valid=False;continue
                    key=entry['player']; ident=identities.get(key)
                    points=daily.get(day,{}).get(key)
                    stats=daily_stats.get(day,{}).get(key)
                    if points is None or stats is None or ident is None: valid=False
                    normalized=zero_point_day(stats,points,labels)
                    gp=next((normalized[k] for k in gp_ids if normalized and normalized.get(k) is not None),None)
                    if gp is None: valid=False
                    # Count unique players who actually appeared, not idle lineup slots.
                    if gp==0 and points==0: continue
                    bucket=grouped.setdefault(key,{'points':[],'stats':[]})
                    bucket['points'].append(points);bucket['stats'].append(normalized)
                if valid: covered+=1
            coverage[team['key']]={'covered':covered,'expected':len(days)}
            for key,bucket in grouped.items():
                ident=identities.get(key,{'group':'F'})
                contribution=dict(ident,key=team['key']+'|'+key,
                    points=round(sum(bucket['points']),2) if all(v is not None for v in bucket['points']) else None,
                    stats=aggregate_stats(bucket['stats'],labels))
                players.append(contribution); owners[contribution['key']]=team['key']
                contributions.setdefault(team['key'],{})[key]=contribution
        rows=roster_profiles(dict(teams=data['teams'],players=players,roster_owners=owners,rosters_loaded=True,stat_labels=labels))
        complete=all(v['covered']==v['expected'] for v in coverage.values()) and bool(days)
        for row in rows:
            row['credit_coverage']=coverage[row['key']]
            if row['credit_coverage']['covered'] != len(days) or not days:
                for bucket in [row,*row['groups'].values()]:
                    bucket.update(points=None,average_points=None,average_pos_rank=None,stats={k:None for k in bucket['stats']})
            if not complete:
                for bucket in [row,*row['groups'].values()]: bucket.update(rank=None,total_rank=None,average_pos_rank=None)
        return rows,{'start':start.isoformat(),'end':end.isoformat(),'complete':complete,
                     'covered':min((v['covered'] for v in coverage.values()),default=0),'expected':len(days)}

    profiles={}; coverage={}
    for period in ('season','7','14','30'):
        start=season_start if period=='season' else max(season_start,through-timedelta(days=int(period)-1))
        profiles[period],coverage[period]=build(start,through)
    checked=matched=0; differences=[]
    weeks={m['week']:m for m in data.get('matchups',[]) if m.get('start') and m.get('end') and m['status']=='postevent' and date.fromisoformat(m['end'])<=through}
    for week,m in weeks.items():
        rows,info=build(date.fromisoformat(m['start']),date.fromisoformat(m['end']))
        if not info['complete']:continue
        totals={r['key']:r['points'] for r in rows}
        for matchup in [x for x in data['matchups'] if x['week']==week and x['status']=='postevent']:
            for team in matchup['teams']:
                actual=totals.get(team['key']);official=team['points']
                if actual is None or official is None:continue
                checked+=1
                if abs(actual-official)<=.15:matched+=1
                else:differences.append({'week':week,'team':team['key'],'calculated':actual,'official':official})
    official_days={d['date']:d['scores'] for rows in data.get('daily_by_week',{}).values() for d in rows}
    daily_checked=daily_matched=0
    for day,teams in lineups.items():
        if day>through.isoformat(): continue
        for team,entries in teams.items():
            values=[daily.get(day,{}).get(p['player']) for p in entries if p['slot'] in ACTIVE]
            official=official_days.get(day,{}).get(team)
            if official is None or any(v is None for v in values): continue
            daily_checked+=1
            if abs(sum(values)-official)<=.15: daily_matched+=1
    return {'profiles':profiles,'coverage':coverage,'reconciliation':{'checked':checked,'matched':matched,'differences':differences,
            'daily_checked':daily_checked,'daily_matched':daily_matched}}
