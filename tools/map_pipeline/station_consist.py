"""Bind each station platform's train and end margins to native rail identity."""
import math


def verified_platform_consists(proof, layout):
    actual = {(p['input_station_id'], p['input_rail_id']): p for p in proof['platforms']}
    if len(actual) != len(proof['platforms']):
        raise ValueError('Duplicate native platform identity')
    stations = {s['id']: s for s in proof['input_plan']['stations']}
    if len(stations) != len(proof['input_plan']['stations']):
        raise ValueError('Duplicate planned station identity')
    seen = set()
    result = []
    for station in layout['stations']:
        planned = stations.get(station['id'])
        if planned is None or planned['name'] != station['name']:
            raise ValueError('Consist station binding differs')
        requirements = [dict(rail_id=p['rail_id'], platform_name=p['name'],
                             required_train_length=p['required_train_length'],
                             minimum_end_margin=p['minimum_end_margin'])
                        for p in planned['platforms']]
        explicit = station.get('platform_consists')
        mixed = len({p['required_train_length'] for p in requirements}) > 1
        if (explicit is not None and explicit != requirements) or (mixed and explicit is None):
            raise ValueError('Per-platform consist declaration missing or differs')
        if len(requirements) != len(station['platform_lengths']):
            raise ValueError('Consist platform count differs')
        for required, length in zip(requirements, station['platform_lengths']):
            key = station['id'], required['rail_id']
            p = actual.get(key)
            if key in seen or p is None or p['station'] != station['name'] or p['platform_name'] != required['platform_name']:
                raise ValueError('Consist is bound to the wrong native platform')
            seen.add(key)
            train = required['required_train_length']
            margin = required['minimum_end_margin']
            values = (train, margin, length, p['platform_length'])
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                raise ValueError('Non-finite platform or consist dimensions')
            if train <= 0 or margin < 0 or abs(length-p['platform_length']) > 1e-6:
                raise ValueError('Platform dimensions or train requirement differs')
            if length + 1e-6 < train + 2*margin:
                raise ValueError('Platform cannot hold assigned consist and both end margins')
            result.append(dict(station_id=station['id'], station_name=station['name'],
                               **required, platform_length=length,
                               actual_centred_end_margin=(length-train)/2))
    if seen != set(actual) or {s['id'] for s in layout['stations']} != set(stations):
        raise ValueError('Native platform or station omitted from consist verification')
    return result
