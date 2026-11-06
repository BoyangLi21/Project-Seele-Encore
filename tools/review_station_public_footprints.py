"""Review explicit public floor footprints against frozen section captures.

No world access, inferred air, native mutation or repair is performed. A missing
floor remains in the declared denominator. Furniture exclusions require exact
observed fixtures and do not exempt their underlying floors from inspection.
"""
import argparse
from collections import Counter, deque
import json
import math
from pathlib import Path

import numpy as np

from audit_hakone_station_walks import Walker
from map_pipeline.station_sections import StationSections
from review_underground_station_evidence import Overlay, strict_walk


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def declared_cells(spec):
    cells = {}
    for row in spec.get('rectangles', []):
        x, z, X, Z = row['bounds_xz']
        for xx in range(x, X+1):
            for zz in range(z, Z+1):
                cells[xx, zz] = dict(pos=[xx+.5, row['feet_y'], zz+.5],
                                     component=row['id'], basis=row['basis'])
    for row in spec.get('cells', []):
        x, y, z = row['pos']
        cells[math.floor(x), math.floor(z)] = row
    return cells


def floor_probe(w, p):
    floors, unknown = w.floors(*p)
    exact = any(abs(v-p[1]) < .0001 for v in floors)
    return dict(exact=exact, unknown=unknown[:1], nearby=floors,
                body=w.body(*p) if exact else None)


def diagonal_edges(w, clear):
    """Probe diagonal corner approaches, where cardinal guard tests can miss gaps."""
    blocked=[];failures=[]
    for (x,z),p in clear.items():
        for dx,dz in ((-1,-1),(-1,1),(1,-1),(1,1)):
            if (x+dx,z+dz)in clear and abs(clear[x+dx,z+dz][1]-p[1])<=1:continue
            outside=[p[0]+dx,p[1],p[2]+dz];lower=None;unavailable=[]
            for down in range(17):
                heights,unknown=w.floors(outside[0],p[1]-down,outside[2])
                unavailable.extend(unknown[:1])
                found=[h for h in heights if h<=p[1]and w.body(outside[0],h,outside[2])is None]
                if found:lower=max(found);break
            if lower is not None and p[1]-lower<=1:continue
            hit=next((h for t in (.125,.25,.375,.5,.625,.75,.875,1.)
                      if(h:=w.body(p[0]+dx*t,p[1],p[2]+dz*t))is not None),None)
            row=dict(pos=p,direction=[dx,dz],lower_feet=lower,hit=hit,unknown=unavailable[:1])
            (blocked if hit and hit['kind']=='body_obstruction' else failures).append(row)
    return dict(high_drop_approaches=len(blocked)+len(failures),blocked=len(blocked),failures=failures,
                unprotected=len(failures),samples_per_approach=8)


def review(spec, shapes, out):
    w = Walker(Path(spec['source']), shapes)
    if spec.get('overlay_changes'):
        delta=json.loads(Path(spec['overlay_changes']).read_text('utf8'))
        w.reader=Overlay(w.reader,{tuple(q['pos']):q['after'] for q in delta})
    declared = declared_cells(spec)
    exclusions = {tuple(q['column']): q for q in spec.get('exclusions', [])}
    for key, row in exclusions.items():
        if key not in declared:
            raise ValueError('Exclusion outside declared footprint')
        for q in row['witnesses']:
            if w.reader.state(*q['pos']) != q['state']:
                raise ValueError('Fixture witness changed: '+str(q))
    rows = []; clear = {}; failures = []; excluded = []
    offsets = (-.19, 0., .19)
    for key, row in sorted(declared.items()):
        p = row['pos']; probes = []
        for dx in offsets:
            for dz in offsets:
                q = [p[0]+dx, p[1], p[2]+dz]
                probe = floor_probe(w, q)
                if not probe['exact'] or probe['unknown'] or (probe['body'] and key not in exclusions):
                    probes.append(dict(pos=q, **probe))
        result = dict(**row, excluded=key in exclusions, failures=probes)
        rows.append(result)
        if key in exclusions:
            excluded.append(dict(**exclusions[key], support_passed=not any(not p['exact'] or p['unknown'] for p in probes)))
        if probes:
            failures.append(result)
        elif key not in exclusions:
            clear[key] = p
    links = {key: [] for key in clear}; bad_links = []
    for key, p in clear.items():
        for dx, dz in ((1, 0), (0, 1)):
            other = key[0]+dx, key[1]+dz
            if other not in clear:
                continue
            q = clear[other]
            if abs(p[1]-q[1]) > .600001:
                # Different floors next to a stair's side are not a stair link.
                continue
            forward = strict_walk(w, [p, q]); reverse = strict_walk(w, [q, p])
            if forward['kind'] == reverse['kind'] == 'strict_static_clear':
                links[key].append(other); links[other].append(key)
            else:
                bad_links.append(dict(a=p, b=q, forward=forward, reverse=reverse))
    components = []; membership = {}
    for seed in clear:
        if seed in membership:
            continue
        ci = len(components); queue = deque([seed]); membership[seed] = ci; members=[]
        while queue:
            key = queue.popleft(); members.append(key)
            for other in links[key]:
                if other not in membership:
                    membership[other] = ci; queue.append(other)
        components.append(members)
    journeys = []
    for route in spec.get('routes', []):
        journeys.append(dict(**route, forward=strict_walk(w, route['path']),
                             reverse=strict_walk(w, list(reversed(route['path'])))))
    goals=[]
    for goal in spec.get('goals', []):
        key=math.floor(goal['pos'][0]),math.floor(goal['pos'][2])
        goals.append(dict(**goal, exact_floor=key in clear and abs(clear[key][1]-goal['pos'][1])<.0001,
                          component=membership.get(key)))
    edges=[]
    for key, p in clear.items():
        for dx, dz, side in ((1,0,'east'),(-1,0,'west'),(0,1,'south'),(0,-1,'north')):
            other=key[0]+dx,key[1]+dz
            if other in clear and abs(clear[other][1]-p[1]) <= .600001:
                continue
            outside=[p[0]+dx,p[1],p[2]+dz]
            heights, unknown=w.floors(*outside)
            nearby=[h for h in heights if abs(h-p[1])<=.600001 and w.body(outside[0],h,outside[2]) is None]
            # Thin bars may lie at the centre of the adjacent cell. Sweep the
            # whole boundary approach instead of declaring them absent at .55.
            hits=[(t,w.body(p[0]+dx*t,p[1],p[2]+dz*t)) for t in (.55,.8,1.)]
            hit_at,hit=next(((t,h)for t,h in hits if h is not None),(None,None))
            if unknown:
                kind='unknown_adjacent_capture'
            elif nearby:
                kind='adjacent_supported_surface'
            elif hit and hit['kind']=='body_obstruction':
                kind='fixed_boundary_or_rising_terrain'
            elif other in exclusions:
                kind='declared_fixture'
            else:
                kind='unresolved_exposed_edge'
            lower=None
            if kind=='unresolved_exposed_edge':
                for down in range(0,17):
                    hs,us=w.floors(outside[0],p[1]-down,outside[2])
                    candidates=[h for h in hs if h<=p[1] and w.body(outside[0],h,outside[2]) is None]
                    if candidates:
                        lower=max(candidates);break
                    if us:
                        kind='unknown_adjacent_capture';break
                if lower is not None and p[1]-lower<=1.000001:
                    kind='unguarded_one_block_step'
            edges.append(dict(pos=p,side=side,kind=kind,hit=hit,hit_at=hit_at,adjacent_floor_heights=heights,
                              measured_lower_feet=lower,drop=p[1]-lower if lower is not None else None))
    supports=[]
    for group in spec.get('support_volumes', []):
        x,y,z,X,Y,Z=group['bounds']; bad=[]; total=0
        for xx in range(x,X+1):
            for yy in range(y,Y+1):
                for zz in range(z,Z+1):
                    total+=1;state,boxes=w.boxes(xx,yy,zz)
                    if boxes is None or not any(b==[0.,0.,0.,1.,1.,1.] for b in boxes):
                        bad.append(dict(pos=[xx,yy,zz],state=state))
        supports.append(dict(**group, cells=total, failures=bad))
    negative=[]
    seed=next(p for key,p in clear.items() if key not in exclusions and p[1]%1==0)
    for label,patch in (
        ('missing_floor',{(math.floor(seed[0]),int(seed[1])-1,math.floor(seed[2])):'minecraft:air'}),
        ('headroom_block',{(math.floor(seed[0]),int(seed[1])+1,math.floor(seed[2])):'minecraft:stone_bricks'}),
        ('unknown_floor',{(math.floor(seed[0]),int(seed[1])-1,math.floor(seed[2])):None}),
    ):
        test=Walker(Path(spec['source']),shapes);test.reader=Overlay(w.reader,patch)
        r=strict_walk(test,[seed,seed]);negative.append(dict(case=label,result=r,rejected=r['kind']!='strict_static_clear'))
        if r['kind']=='strict_static_clear':raise ValueError('Negative case escaped: '+label)
    # The same probe that covers every edge must expose an injected guard loss.
    for edge in edges:
        h=edge['hit']
        if edge['kind']!='fixed_boundary_or_rising_terrain' or not h or not any(s in h.get('state','') for s in ('edge_rail','iron_bars')):
            continue
        p=edge['pos']; dx,dz={'east':(1,0),'west':(-1,0),'south':(0,1),'north':(0,-1)}[edge['side']]
        t=Walker(Path(spec['source']),shapes);t.reader=Overlay(w.reader,{tuple(h['pos']):'minecraft:air'})
        removed=t.body(p[0]+dx*edge['hit_at'],p[1],p[2]+dz*edge['hit_at'])
        if removed is None:
            negative.append(dict(case='guard_removed',intact=edge,removed_hit=removed,rejected=True));break
    result=dict(id=spec['id'],name=spec['name'],source=spec['source'],
        public_column_denominator=len(declared),clear_public_columns=len(clear),
        known_fixture_columns=len(exclusions),failed_public_columns=len(failures),
        component_sizes=sorted([len(c)for c in components],reverse=True),
        checked_bidirectional_neighbor_pairs=sum(map(len,links.values()))//2,
        failed_neighbor_pairs=bad_links,goals=goals,routes=journeys,
        edge_counts=dict(Counter(e['kind']for e in edges)),
        diagonal_edge_check=diagonal_edges(w,clear),
        unresolved_edges=[e for e in edges if e['kind'].startswith(('unknown','unresolved'))],
        support_volumes=supports,negative_cases=negative,
        component_column_membership=[dict(column=list(k),component=v)for k,v in sorted(membership.items())],
        caveats=spec.get('caveats',[]),full_public_footprint_support_and_headroom=not failures,
        static_shape_source='Retained native collision export; current runtime confirmation is stage 3.',
        dynamic_devices_opened=False,world_opened=False,world_written=False)
    write(out/(spec['id']+'-cells.json'),rows)
    write(out/(spec['id']+'-edges.json'),edges)
    write(out/(spec['id']+'-exclusions.json'),excluded)
    write(out/(spec['id']+'-failures.json'),failures)
    write(out/(spec['id']+'-review.json'),result)
    print(spec['name'],len(declared),'declared;',len(clear),'clear;',len(failures),'failed;',result['component_sizes'],'components;',result['edge_counts'],flush=True)
    return result


def run(args):
    doc=json.loads(args.manifest.read_text('utf8'));args.out.mkdir(parents=True,exist_ok=True)
    shapes=json.loads(Path(doc['shapes']).read_text('utf8'))
    rows=[review(s,shapes,args.out) for s in doc['stations']]
    write(args.out/'summary.json',dict(stations=[{k:v for k,v in r.items() if k not in ('component_column_membership','support_volumes','failed_neighbor_pairs','unresolved_edges')}for r in rows],
          manifest=str(args.manifest),whole_stage_two_complete=False,world_opened=False,world_written=False))


def build_connection(args):
    """Build a bounded reversible civil candidate from explicit desired cells.

    Destination identities and grades live in the reviewed specification. This
    routine cannot choose a destination or author a route from arbitrary air.
    """
    import nbtlib
    from author_hakone_lakefront import Editor
    from export_hakone_station_surface import export
    spec=json.loads(args.connection.read_text('utf8'));source=Path(spec['source'])
    shapes=json.loads(Path(spec['shapes']).read_text('utf8'))
    export(source,spec['export_bounds'],args.out);editor=Editor(args.out)
    reader=StationSections(source);changes={};reasons={};supports=[]
    tags=nbtlib.load(source/'devices.dat')['Devices']
    devices={tuple(int(t[k])for k in ('x','y','z'))for t in tags}
    natural={'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
    old_walker=Walker(source,shapes)
    def state(p):return changes.get(tuple(p),reader.state(*p))
    def put(p,s,why,allowed=None):
        p=tuple(map(int,p));old=reader.state(*p)
        if p in devices:raise ValueError('Device contact: '+str(p))
        if old is None:raise ValueError('Uncaptured candidate cell: '+str(p))
        if state(p)==s:return
        if old not in (natural if allowed is None else allowed):
            raise ValueError('Undeclared artificial contact: '+str((p,old,s,why)))
        changes[p]=s;reasons[p]=why
    def full(p):
        s=state(p);return any(b==[0.,0.,0.,1.,1.,1.]for b in shapes.get(s,[]))
    def support(x,top,z,kind):
        y=top-1
        while not full((x,y,z)):
            if top-y>16:raise ValueError('Unsupported civil column: '+str((x,top,z)))
            put((x,y,z),'minecraft:stone_bricks','continuous bearing '+kind);y-=1
        supports.append(dict(x=x,z=z,bottom=y,top=top,kind=kind,existing_base=state((x,y,z))))
    for q in spec.get('retire_cells',[]):
        if reader.state(*q['pos'])!=q['before']:raise ValueError('Retired remnant changed')
        put(q['pos'],'minecraft:air','Retire positively traced isolated former access stair',allowed={q['before']})
    floor_cells={tuple(q['column']):q['feet_y']for q in spec['new_floor']}
    for (x,z),feet in sorted(floor_cells.items()):
        floor=math.ceil(feet)-1
        support(x,floor,z,'public floor')
        material='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if feet%1 else'minecraft:smooth_stone'
        allowed=natural|{material}
        put((x,floor,z),material,'three-cell public stair or connection floor',allowed)
        for y in range(floor+1,math.ceil(feet)+3):
            if state((x,y,z))!='minecraft:air':put((x,y,z),'minecraft:air','measured natural headroom cut')
    # Only boundaries of this explicit stair/connection are eligible for guards.
    corridor={tuple(q['column']):q['feet_y']for q in spec['guarded_corridor']}
    temporary=Walker(source,shapes);temporary.reader=Overlay(reader,changes)
    guards={};existing_guards=[]
    for (x,z),feet in corridor.items():
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            key=x+dx,z+dz
            if key in corridor:continue
            outside=[key[0]+.5,feet,key[1]+.5]
            hit=next((h for t in (.55,.8,1.) if (h:=temporary.body(x+.5+dx*t,feet,z+.5+dz*t)) is not None),None)
            if hit and hit['kind']=='body_obstruction':
                existing_guards.append(dict(column=list(key),feet=feet,hit=hit));continue
            clear=[]
            for down in range(0,17):
                hs,unknown=temporary.floors(outside[0],feet-down,outside[2])
                if unknown:raise ValueError('Unknown guard foundation')
                clear=[h for h in hs if h<=feet and temporary.body(outside[0],h,outside[2])is None]
                if clear:break
            lower=max(clear)if clear else None
            if lower is not None and feet-lower<=1.000001:continue
            guards[key]=max(guards.get(key,-1000),math.ceil(feet))
    for row in spec.get('extra_guard_columns',[]):
        key=tuple(row['column'])
        if key in corridor:raise ValueError('Extra corner guard would narrow public corridor')
        guards[key]=max(guards.get(key,-1000),row['y'])
    for (x,z),y in sorted(guards.items()):
        support(x,y,z,'fall guard')
        # Prefer a bar aligned with the adjoining run. Its neighbouring cell
        # lies outside the full three-cell clear passenger width.
        along_z=(x-1,z)in corridor or(x+1,z)in corridor
        material='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'if along_z else'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'
        put((x,y,z),material,'continuous outside fall guard')
    rows=[dict(pos=list(p),before=reader.state(*p),after=s,purpose=reasons[p])for p,s in sorted(changes.items()) if reader.state(*p)!=s]
    for q in rows:
        if editor.state(*q['pos'])!=q['before']:raise ValueError('Export source precondition mismatch')
        editor.put(*q['pos'],q['after'])
    regions=editor.save();after=Walker(source,shapes);after.reader=Overlay(reader,changes)
    paths=[];errors=[]
    for q in spec['routes']:
        row=dict(**q,before=strict_walk(old_walker,q['path']),after=strict_walk(after,q['path']),reverse_after=strict_walk(after,list(reversed(q['path']))))
        paths.append(row)
        if row['after']['kind']!=row['reverse_after']['kind']or row['after']['kind']!='strict_static_clear':errors.append(['route',q['id']])
    floors=[]
    for (x,z),feet in corridor.items():
        bad=[]
        for dx in (-.19,0,.19):
            for dz in (-.19,0,.19):
                p=[x+.5+dx,feet,z+.5+dz];q=floor_probe(after,p)
                if not q['exact']or q['unknown']or q['body']:bad.append(dict(pos=p,result=q))
        floors.append(dict(column=[x,z],feet_y=feet,failures=bad))
        if bad:errors.append(['full_width',x,z])
    negative=[]
    anchor=spec['negative_anchor'];floor=math.ceil(anchor[1])-1
    for label,p,s in [('missing_tread',[int(anchor[0]),floor,int(anchor[2])],'minecraft:air'),('headroom_block',[int(anchor[0]),math.ceil(anchor[1])+1,int(anchor[2])],'minecraft:stone_bricks')]:
        test=Walker(source,shapes);test.reader=Overlay(after.reader,{tuple(p):s});r=strict_walk(test,[anchor,anchor]);reject=r['kind']!='strict_static_clear'
        negative.append(dict(case=label,rejected=reject,result=r))
        if not reject:errors.append(['negative',label])
    guard_tests=[]
    for (x,z),y in guards.items():
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            key=x+dx,z+dz
            if key not in corridor:continue
            feet=corridor[key];p=[x+.5,feet,z+.5];hit=after.body(*p)
            if hit is None:errors.append(['guard',x,z])
            guard_tests.append(dict(pos=p,hit=hit))
    if guards:
        x,z=next(iter(guards));y=guards[x,z]
        intact=after.body(x+.5,y,z+.5);test=Walker(source,shapes);test.reader=Overlay(after.reader,{(x,y,z):'minecraft:air'});removed=test.body(x+.5,y,z+.5)
        reject=intact is not None and removed is None;negative.append(dict(case='guard_removed',rejected=reject,intact=intact,removed=removed))
        if not reject:errors.append(['negative','guard_removed'])
    diagonal=diagonal_edges(after,{key:[key[0]+.5,feet,key[1]+.5]for key,feet in corridor.items()})
    if diagonal['failures']:errors.append(['diagonal_unguarded',diagonal['unprotected']])
    bounds=[min(q['pos'][i]for q in rows)for i in range(3)]+[max(q['pos'][i]for q in rows)for i in range(3)]
    report=dict(errors=errors,changed_cells=len(rows),new_floor_columns=len(floor_cells),corridor_columns=len(corridor),
        before_after_paths=paths,full_width_columns=floors,guard_columns=[dict(column=list(p),y=y)for p,y in sorted(guards.items())],
        existing_boundary_witnesses=existing_guards,guard_tests=guard_tests,support_columns=supports,negative_tests=negative,
        diagonal_edge_check=diagonal,
        protected_device_count=len(devices),devices_changed=0,actors_changed=0,native_changed=0,
        specification=str(args.connection),world_written=False,installed=False,geometry_only=True)
    cap=json.loads((args.out/'capture.json').read_text('utf8'))
    write(args.out/'manifest.json',dict(world=cap['world'],kind='retained-public-plaza-current-street-reconnection',bounds_xz=cap['bounds_xz'],bounds_3d=bounds,regions=regions,cells=len(rows),
          source_snapshot=str(source),device_changes=0,actor_changes=0,native_changes=0,functional_errors=errors,world_written=False,production_recipe_replay_pending=True))
    write(args.out/'functional-check.json',report);write(args.out/'changes.json',rows)
    write(args.out/'inverse.json',[dict(pos=q['pos'],before=q['after'],after=q['before'])for q in rows])
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(args.out/'block-entities.dat',gzipped=True)
    print('Public connection candidate:',len(rows),'cells;',len(guards),'new guard columns; errors',errors[:10],flush=True)
    if errors:raise ValueError('Candidate verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--manifest',type=Path);p.add_argument('--connection',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.connection:build_connection(a)
    elif a.manifest:run(a)
    else:p.error('Provide --manifest or --connection')
