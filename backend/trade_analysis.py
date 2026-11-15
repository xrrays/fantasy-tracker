"""Player production from processed trade date through the latest closed day."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def trade_windows(transactions, through):
    for tx in transactions:
        if tx['type'] != 'trade':
            continue
        start=datetime.fromtimestamp(int(tx['timestamp']),ZoneInfo('America/Los_Angeles')).date()
        keys=sorted({p['player'] for p in tx['players'] if p.get('destination') and p.get('action')=='trade'})
        yield tx, start, keys, max(0,(through-start).days+1)


def trade_production(transactions, daily, through):
    result={}
    for tx,start,keys,days in trade_windows(transactions,through):
        sides={}
        for team in {p['destination'] for p in tx['players'] if p.get('destination')}:
            players={p['player'] for p in tx['players'] if p.get('destination')==team and p.get('action')=='trade'}
            individual={}
            for key in players:
                player_values=[daily.get((start+timedelta(days=i)).isoformat(),{}).get(key) for i in range(days)]
                player_known=[v for v in player_values if v is not None]
                individual[key]=dict(points=round(sum(player_known),2) if player_known or not player_values else None,
                    complete=len(player_known)==len(player_values),covered=len(player_known),expected=len(player_values))
            values=[daily.get((start+timedelta(days=i)).isoformat(),{}).get(key) for i in range(days) for key in players]
            known=[v for v in values if v is not None]
            sides[team]=dict(points=round(sum(known),2) if known or not values else None,
                complete=len(known)==len(values),covered=len(known),expected=len(values),
                start=start.isoformat(),end=through.isoformat(),players=individual)
        result[tx['id']]=sides
    return result
