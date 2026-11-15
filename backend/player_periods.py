"""Aggregate a player's actual daily stats; never substitute season totals."""
import re


def display_stats(stats, points, labels):
    """Normalize explicit zero/blank period lines and shooting percentages for display.

    Leaves retained Yahoo facts untouched. Missing rows and partly missing lines
    stay unknown; a zero point total alone is not proof of zero stats.
    """
    result = dict(zero_point_day(stats, points, labels) or {})
    def value(label):
        return next((result[key] for key,name in labels.items() if name.upper()==label and result.get(key) is not None),None)
    goals, shots = value('G'), value('SOG')
    for key, label in labels.items():
        if label.upper() in ('SH%', 'SHPCT', 'S%') and key in result:
            result[key] = round(goals/shots*100,4) if goals is not None and shots is not None and shots>0 else None
    return result


def zero_point_day(stats, points, labels):
    """Yahoo reports zero points plus all-blank counting categories on no-stat days.

    Only this explicit response combination implies zero counts. Missing rows,
    partly missing categories, nonzero/unknown points and rates stay unavailable.
    """
    if not stats or points != 0 or any(value is not None for value in stats.values()):
        return stats
    return {key: None if re.search(r'%|PCT|GAA|/G|/60|AVG', labels.get(key, '').upper()) else 0
            for key in stats}


def aggregate_stats(days, labels, expected=()):
    keys = set(expected) | {key for day in days if day is not None for key in day}
    by_label = {}
    for key, label in labels.items():
        by_label.setdefault(label.upper().replace(' ', ''), []).append(key)
    gp_keys = by_label.get('GP', [])

    def total(key):
        values = []
        applicable = key in expected or any(day is not None and day.get(key) is not None for day in days)
        for day in days:
            if day is None:
                return None
            value = day.get(key)
            # An explicit zero games played can establish a zero counting stat.
            games = [day[gp] for gp in gp_keys if day.get(gp) is not None]
            if value is None and applicable and games and all(gp == 0 for gp in games):
                value = 0
            if value is None:
                return None
            values.append(value)
        # NHL game-context stat 33 is total ice time in seconds.
        # Other TOI fields and the UI use minutes.
        scale = 60 if key == '33' and labels.get(key, '').upper() == 'TOI' else 1
        return round(sum(values) / scale, 4) if applicable else None

    def known(*names):
        for name in names:
            for key in by_label.get(name, []):
                value = total(key)
                if value is not None:
                    return value
        return None

    def ratio(numerator, denominator, multiplier=1):
        return round(numerator / denominator * multiplier, 4) if numerator is not None and denominator is not None and denominator > 0 else None

    result = {}
    for key in keys:
        label = labels.get(key, '').upper().replace(' ', '')
        if label in ('SV%', 'SVPCT'):
            shots = known('SA')
            if shots is None:
                saves, goals = known('SV'), known('GA')
                shots = saves + goals if saves is not None and goals is not None else None
            result[key] = ratio(known('SV'), shots)
        elif label == 'GAA':
            result[key] = ratio(known('GA'), known('TOI', 'MIN', 'MP'), 60)
        elif label in ('SH%', 'SHPCT', 'S%'):
            result[key] = ratio(known('G'), known('SOG'), 100)
        elif label in ('TOI/G', 'ATOI'):
            result[key] = ratio(known('TOI'), known('GP'))
        elif '%' in label or 'PCT' in label or re.search(r'/G|/60|AVG', label):
            result[key] = None  # Unsupported rates are unavailable, never summed or averaged.
        else:
            result[key] = total(key)
    return result
