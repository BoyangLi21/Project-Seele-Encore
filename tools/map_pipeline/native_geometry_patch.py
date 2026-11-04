"""Independently constrain a declared native railway geometry migration.

Comparison uses original bytes and parsed fields, retaining unchanged tokens,
opaque MessagePack tails, vehicle state and every undeclared member.
"""
import json
from pathlib import Path
from prepare_mtr_member_patch_r52 import Parser,point,edge,map_child
from native_transit_additions import inventory,assert_preserved


def decode(raw):
    parser=Parser(raw);node=parser.node()
    return node,raw[parser.offset:]


def expected(candidate):
    baseline=inventory(candidate/'preserved-native')
    manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
    filename=manifest.get('native_geometry_patch')
    if not filename:return baseline,dict(changed_members=0,existing_native_members_exact=True)
    if filename!='native-geometry/operations.json':raise ValueError('Unexpected native geometry manifest location')
    root=candidate/'native-geometry';report=json.loads((root/'operations.json').read_text('utf8'))
    station_lift=report.get('migration_kind')=='cable_station_vertical'
    if report.get('migration_kind')not in (None,'cable_station_vertical'):raise ValueError('Unknown geometry migration kind')
    current=dict(baseline);names=set();changed=set()
    for op in report['operations']:
        name=op['member'];rel=Path(name)
        allowed={'rails','depots','sidings'}|({'platforms'}if station_lift else set())
        if rel.is_absolute() or '..' in rel.parts or len(rel.parts)!=5 or rel.parts[:2]!=('projectseele','geofront') or rel.parts[2] not in allowed:
            raise ValueError('Native geometry operation outside finite rail/path scope')
        if name in names:raise ValueError('Duplicate native geometry member')
        names.add(name)
        if op['before']!=(name in baseline):raise ValueError('Incorrect native before presence')
        if op['before'] and (root/'before'/rel).read_bytes()!=baseline[name]:raise ValueError('Native baseline differs')
        if op['after']:current[name]=(root/'after'/rel).read_bytes()
        else:current.pop(name)
        changed.add(name)
    moves={tuple(m['before']):tuple(m['after']) for m in report['node_moves']}
    if len(moves)!=len(report['node_moves']):raise ValueError('Duplicate moved native node')
    if any(a[0]!=b[0] or a[2]!=b[2] or a[1]==b[1] or abs(a[1]-b[1])>(8 if station_lift else 4) for a,b in moves.items()):
        raise ValueError('This migration only supports bounded vertical junction corrections')
    if station_lift and (not moves or len({b[1]-a[1]for a,b in moves.items()})!=1):raise ValueError('Cable station must use a single declared vertical translation')
    rails={};rail_members=set();vehicles=0;paths=0
    for row in report['rail_geometry']:
        oldname,newname=row['before_member'],row['after_member']
        rail_members|={oldname,newname}
        old,tail=decode(baseline[oldname]);new,newtail=decode(current[newname]);a,b=old.value,new.value
        if tail!=newtail or set(a)!=set(b):raise ValueError('Rail opaque data changed')
        if station_lift:
            if a.get('transportMode')!='CABLE_CAR':raise ValueError('Cable station migration touches another transport mode')
        elif a['isPlatform'] or a['isSiding']:raise ValueError('Station/siding geometry needs an explicit identity migration')
        if abs(row['length_after']-row['length_before'])>1e-8:raise ValueError('Native path length changed')
        for key in a:
            if key in {'shape','verticalRadius'}:continue
            if key in {'position1','position2'}:
                if point(b[key])!=moves.get(point(a[key]),point(a[key])):raise ValueError('Undeclared native endpoint')
            elif map_child(old,key).raw!=map_child(new,key).raw:raise ValueError('Unrelated rail token changed '+key)
        if newname!=oldname and oldname in current:raise ValueError('Old endpoint member still exists')
        rails[edge(a['position1'],a['position2'])]=b
    if changed & {n for n in names if '/rails/' in n} != rail_members & changed:raise ValueError('Undeclared railway member operation')
    # Every original rail incident to a moved node must be represented.
    for name,raw in baseline.items():
        if '/rails/' not in name:continue
        row=decode(raw)[0].value
        if any(point(row[k]) in moves for k in ('position1','position2')) and name not in rail_members:
            raise ValueError('Moved native junction leaves an incident rail behind')
    allowed_paths={'path','pathSidingToMainRoute','pathMainRouteToSiding'}
    identities=[]
    for name in names-rail_members:
        if name not in baseline or name not in current:raise ValueError('Do not create/remove depots or sidings')
        old,tail=decode(baseline[name]);new,newtail=decode(current[name])
        if tail!=newtail or set(old.value)!=set(new.value):raise ValueError('Native owner schema changed')
        identity=station_lift and any('/'+kind+'/' in name for kind in ('platforms','sidings'))
        if identity and any(old.value[k]!=new.value[k]for k in ('position1','position2')):identities.append(name)
        for key in old.value:
            aa,bb=map_child(old,key),map_child(new,key)
            if identity and key in {'position1','position2'}:
                if old.value.get('transportMode')!='CABLE_CAR' or point(bb.value)!=moves.get(point(aa.value),point(aa.value)):raise ValueError('Undeclared station identity endpoint')
                continue
            if key not in allowed_paths:
                if aa.raw!=bb.raw:raise ValueError('Native identity, vehicle or timetable token changed '+key)
                if key=='vehicles':vehicles+=len(aa.value)
                continue
            if len(aa.value)!=len(bb.value):raise ValueError('Cached path length changed')
            for a,b in zip(aa.children,bb.children):
                if a.raw==b.raw:continue
                if set(a.value)!=set(b.value):raise ValueError('Path schema changed')
                rail=rails.get(edge(a.value['startPosition'],a.value['endPosition']))
                if rail is None:raise ValueError('Unrelated cached path edge changed')
                for k in a.value:
                    if k in {'startPosition','endPosition'}:
                        if point(b.value[k])!=moves.get(point(a.value[k]),point(a.value[k])):raise ValueError('Incorrect cached path endpoint')
                    elif k in {'shape','verticalRadius'}:
                        if b.value[k]!=rail[k]:raise ValueError('Cached path does not match native rail')
                    elif map_child(a,k).raw!=map_child(b,k).raw:raise ValueError('Cached path distance/angle/service token changed')
                paths+=1
    if paths!=report['cached_path_entries']:raise ValueError('Cached path coverage mismatch')
    if station_lift:
        if set(identities)!=set(report.get('station_identity_members',[])):raise ValueError('Station identity coverage mismatch')
        # All matching platform/siding objects must follow their native rail,
        # retaining IDs and every route, dwell, vehicle and timetable token.
        for name,raw in baseline.items():
            if not any('/'+kind+'/'in name for kind in ('platforms','sidings')):continue
            row=decode(raw)[0].value
            if any(point(row[k])in moves for k in ('position1','position2')) and name not in identities:raise ValueError('Moved station identity was omitted')
    return current,dict(changed_members=len(changed),rails=len(rails),cached_path_entries=paths,
                        vehicles_in_changed_owners_exact=vehicles,unmodified_native_members_exact=True,
                        existing_native_members_exact=False,unmodified_members=len(set(baseline)-changed),station_identities_retained=len(identities))


def prepare(candidate,world):
    final,report=expected(candidate);baseline=inventory(candidate/'preserved-native')
    assert_preserved(world,baseline)
    pairs=[]
    for name in sorted(set(baseline)|set(final)):
        if baseline.get(name)==final.get(name):continue
        pairs.append((world/'mtr'/name,candidate/'native-geometry/after'/name if name in final else None))
    return pairs,baseline,final,report
