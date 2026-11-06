"""Readonly component review of R52's inherited road-column exceptions.

No station rectangle constitutes a pass.  This reads current native shapes,
measured paving tops and a few already declared public paths; it never changes
World, traffic, navigation, or the inherited survey.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse, hashlib, json, math, time
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque
from pathlib import Path
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

BASE = Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
WORLD = BASE/'WORLD_R52'
FLOORS = {'minecraft:black_concrete', 'minecraft:white_concrete',
          'minecraft:smooth_stone', 'minecraft:smooth_stone_slab',
          'minecraft:quartz_slab', 'minecraft:polished_blackstone_slab',
          'projectseele:road_asphalt_slab', 'projectseele:road_marking_slab',
          'projectseele:period_station_floor', 'projectseele:nerv_floor_panel'}
EMPTY = AIR | {'minecraft:light', 'minecraft:grass', 'minecraft:tall_grass',
              'minecraft:fern', 'minecraft:large_fern', 'minecraft:dandelion',
              'minecraft:poppy', 'minecraft:cornflower'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def hits(a, b): return all(a[k] < b[k+3]-1e-7 and a[k+3] > b[k]+1e-7 for k in range(3))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--remaining-ten', action='store_true',
                    help='Only four superseded link datums and six declared shelter columns; do not repeat airport QA')
    args = ap.parse_args(); start = time.monotonic()
    report_file = BASE/'final_map_audit/full_road_columns/CURRENT_ROAD_COLUMNS.json'
    audit = json.loads(report_file.read_text('utf8'))
    source = Path(audit['source_profile'])
    assert sha(source) == audit['source_sha256']
    old = np.load(source); coords = old['coordinates']
    index = {tuple(map(int, q)): i for i, q in enumerate(coords)}
    current_file = report_file.with_suffix('.npz'); current = np.load(current_file)
    assert np.array_equal(coords, current['coordinates'])
    shapes_file = WORLD/'native_collision_shapes.json'
    shapes = {canonical_state(k): v for k,v in json.loads(shapes_file.read_text('utf8')).items()}
    hints_file = Path('.Codex/r52_runtime_close/roads_readonly/station_domain_hints.json')
    hints = json.loads(hints_file.read_text('utf8'))
    outside = {tuple(q['position'][::2]) for q in hints['outside']}
    metadata_file = WORLD/'r45_school_hakone_components.json'
    metadata = json.loads(metadata_file.read_text('utf8'))
    components = [q for group in ('school','hakone') for q in metadata[group]['components']]
    shelter_file=Path('D:/eva/artifacts/facility_r24/kirisato_life/contract.json')
    shelter=json.loads(shelter_file.read_text('utf8'))
    for q in shelter['shelters']:
        components.append(dict(id='r24/kirisato/'+q['building']+'/bicycle_shelter',
            kind='declared_native_bicycle_shelter',bounds=q['bounds']))
    authority_file=Path('D:/eva/artifacts/rebuild_r44/surface_network/hakone_tokyo_link_ready_v11/road_authority.json')
    authority={tuple(q['pos']):q for q in json.loads(authority_file.read_text('utf8'))['columns']}
    cases_file = WORLD/'quality_walk_cases.json'
    cases = json.loads(cases_file.read_text('utf8'))
    chosen = [q for q in cases if q['id'] in (
        'r28/nerv_airport/terminal_to_concourse', 'r28/nerv_airport/airport_road_walk')]
    # Explicit public outside aisles, excluding service-room door interaction.
    chosen += [dict(id='r45/hakone/current_public_front_aisle',
                    path=[[-1520.5,105,632.5],[-1444.5,105,632.5]])]
    remaining_keys={(-1115,294),(-1115,295),(-1114,294),(-1114,295),
        (-2869,-1113),(-2781,-1113),(-2693,-1113),(-2869,-1017),(-2781,-1017),(-2693,-1017)}
    players = [q for q in audit['issues'] if q['kind']=='PLAYER_COMPONENT_REVIEW']
    if args.remaining_ten:
        players=[q for q in players if tuple(q['position'][::2]) in remaining_keys]
        assert len(players)==10
        chosen=[q for q in cases if q['id'].startswith('r24/kirisato/') and q['id'].endswith('/0')]
        assert len(chosen)==12
    w = MeasuredWorld(WORLD)
    for q in players:
        x,f,z = q['position']; i=index[x,z]
        expected=float(authority[x,z]['height2'])/2 if (x,z) in authority else float(old['expected_height2'][i])/2
        r = 7 if (x,z) in outside else 1
        w.box((x-r,math.floor(min(f,expected))-2,z-r),
              (x+r,math.ceil(max(f,expected))+8,z+r))
    for q in chosen:
        for a,b in zip(q['path'],q['path'][1:]):
            w.box(tuple(math.floor(min(a[k],b[k]))-2 for k in range(3)),
                  tuple(math.ceil(max(a[k],b[k]))+(8 if k==1 else 2) for k in range(3)))
    # Exact hanging-board columns and station-office canopy.
    w.box((416,69,73),(423,85,80)); w.box((-1462,102,681),(-1445,112,692))
    region_root=WORLD/'dimensions/projectseele/geofront/region'
    regions={region_root/f'r.{cx//32}.{cz//32}.mca' for cx,cz in w.selected}
    read_start=datetime.now(timezone.utc).isoformat()
    before={str(p):sha(p) for p in sorted(regions) if p.exists()}
    w.load(); unknown=Counter()
    def boxes(st):
        if st is None: return None
        if st.partition('[')[0] in EMPTY: return []
        result=shapes.get(st)
        if result is None: unknown[st]+=1
        return result
    def collision(p, height=1.8):
        x,f,z=p; body=(x-.3,f+.001,z-.3,x+.3,f+height,z+.3); result=[]
        for xx in range(math.floor(body[0]),math.floor(body[3]-1e-7)+1):
            for zz in range(math.floor(body[2]),math.floor(body[5]-1e-7)+1):
                for y in range(math.floor(f),math.ceil(f+height)):
                    st=w.get(xx,y,zz); bs=boxes(st)
                    if bs is None: result.append(dict(at=[xx,y,zz],state=st,unknown=True)); continue
                    for b in bs:
                        a=(xx+b[0],y+b[1],zz+b[2],xx+b[3],y+b[4],zz+b[5])
                        if hits(body,a): result.append(dict(at=[xx,y,zz],state=st,box=list(a)))
        return result
    def supported(x,z,f):
        y=math.floor(f-.001); st=w.get(x,y,z); bs=boxes(st)
        return bool(bs is not None and any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-f)<.001 for b in bs))
    def paving_candidates(x,z,f,expected):
        result=[]
        for candidate in (expected,f,f+.5):
            y=math.floor(candidate-.001); st=w.get(x,y,z)
            if st is None or st.partition('[')[0] not in FLOORS: continue
            bs=boxes(st)
            for b in bs or []:
                top=y+b[4]
                if b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(top-candidate)<=.501:
                    if not collision((x+.5,top,z+.5)):
                        v=dict(feet=top,state=st,at=[x,y,z],expected_feet=expected)
                        if v not in result: result.append(v)
        return result
    rows=[]; refinements={}; status_counts=Counter()
    for q in players:
        x,f,z=q['position']; i=index[x,z]; inherited_expected=float(old['expected_height2'][i])/2
        expected=float(authority[x,z]['height2'])/2 if (x,z) in authority else inherited_expected
        candidates=paving_candidates(x,z,f,expected)
        real=[a for a in candidates if abs(a['feet']-f)>.01]
        named=[c for c in components if c['bounds'][0]<=x<=c['bounds'][3] and c['bounds'][2]<=z<=c['bounds'][5]
               and c['bounds'][1] <= f+1.8 and c['bounds'][4]>=f]
        row=dict(q,expected_feet=expected,inherited_expected_feet=inherited_expected,
                 later_explicit_road_authority=authority.get((x,z)),station_domain_hint=(x,z) not in outside,
                 actual_clear_paving_candidates=candidates,declared_components=[c['id'] for c in named])
        if real:
            top=min(real,key=lambda a:abs(a['feet']-expected))
            row.update(status='ACTUAL_CLEAR_PAVING_AT_DIFFERENT_DATUM',actual_paving=top)
            refinements[x,z]=top['feet']
        elif named:
            row['status']='DECLARED_COMPONENT_OCCUPIES_HISTORICAL_COLUMN_REQUIRES_PATH_REVIEW'
        else: row['status']='ACTUAL_OBSTRUCTION_REQUIRES_COMPONENT_OR_PATH_REVIEW'
        status_counts[row['status']]+=1; rows.append(row)
    # True local bypass evidence around remaining non-station columns only.
    # Membership is restricted to the surveyed road mask; endpoints and every
    # 0.6 m body sample and connecting linear sweep use actual native shapes.
    node_cache={}
    def node(x,z):
        if (x,z) in node_cache:return node_cache[x,z]
        i=index.get((x,z)); result=None
        if i is not None:
            f=float(current['actual_feet'][i])
            if math.isfinite(f):
                expected=float(old['expected_height2'][i])/2
                opts=paving_candidates(x,z,f,expected)
                # Non-paving declared road supports still need exact floor/clearance.
                if supported(x,z,f) and not collision((x+.5,f,z+.5)):opts.append(dict(feet=f))
                if opts: result=min(opts,key=lambda q:abs(q['feet']-f))['feet']
        node_cache[x,z]=result;return result
    def sweep(a,b):
        # Exact linear swept player-box vs each actual native AABB.
        lo=[min(a[k],b[k])-(.3 if k!=1 else 0) for k in range(3)]
        hi=[max(a[k],b[k])+(.3 if k!=1 else 1.8) for k in range(3)]
        for x in range(math.floor(lo[0]),math.floor(hi[0]-1e-7)+1):
            for z in range(math.floor(lo[2]),math.floor(hi[2]-1e-7)+1):
                for y in range(math.floor(lo[1]),math.floor(hi[1]-1e-7)+1):
                    bs=boxes(w.get(x,y,z))
                    if bs is None:return False
                    for box in bs:
                        bounds=(x+box[0],y+box[1],z+box[2],x+box[3],y+box[4],z+box[5])
                        t0,t1=0.,1.
                        for k in range(3):
                            mn=bounds[k]-(.3 if k!=1 else 1.8)+1e-7
                            mx=bounds[k+3]+(.3 if k!=1 else -.001)-1e-7
                            d=b[k]-a[k]
                            if abs(d)<1e-12:
                                if not mn<a[k]<mx:t0,t1=1.,0.;break
                            else:
                                u,v=(mn-a[k])/d,(mx-a[k])/d
                                t0=max(t0,min(u,v));t1=min(t1,max(u,v))
                        if t0<t1:return False
        return True
    local=[]
    remaining=[q for q in rows if not q['station_domain_hint'] and q['status']!='ACTUAL_CLEAR_PAVING_AT_DIFFERENT_DATUM']
    bykey={(q['position'][0],q['position'][2]):q for q in remaining}; unseen=set(bykey)
    while unseen:
        seed=unseen.pop(); group=[seed]; todo=[seed]
        while todo:
            x,z=todo.pop()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                p=x+dx,z+dz
                if p in unseen and abs(bykey[p]['position'][1]-bykey[x,z]['position'][1])<=.501:
                    unseen.remove(p);group.append(p);todo.append(p)
        xs,zs=zip(*group); x0,x1,z0,z1=min(xs),max(xs),min(zs),max(zs)
        proof=dict(issue_columns=len(group),issue_positions=[bykey[p]['position'] for p in sorted(group)],
                   bounds=[x0,z0,x1,z1],status='NO_BOUNDED_PATH_PROOF',paths=[])
        # Bounded only; large walls require their actual owner/path contract.
        if x1-x0<=16 and z1-z0<=24:
            for axis in (0,1):
                endpoints=((x0-1,(z0+z1)//2),(x1+1,(z0+z1)//2)) if axis==0 else (((x0+x1)//2,z0-1),((x0+x1)//2,z1+1))
                a,b=endpoints
                if node(*a) is None or node(*b) is None:continue
                parent={a:None};queue=deque([a])
                while queue and b not in parent:
                    p=queue.popleft();pf=node(*p)
                    for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                        n=p[0]+dx,p[1]+dz
                        if n in parent or not x0-6<=n[0]<=x1+6 or not z0-6<=n[1]<=z1+6:continue
                        nf=node(*n)
                        if nf is None or abs(pf-nf)>.501:continue
                        if not sweep((p[0]+.5,pf,p[1]+.5),(n[0]+.5,nf,n[1]+.5)):continue
                        parent[n]=p;queue.append(n)
                if b in parent:
                    path=[];p=b
                    while p is not None:path.append([p[0]+.5,node(*p),p[1]+.5]);p=parent[p]
                    proof['paths'].append(dict(axis='xz'[axis],path=list(reversed(path))))
            if proof['paths']:proof['status']='FINITE_LOCAL_PLAYER_BYPASS_SHAPE_PROOF'
        local.append(proof)
    path_reports=[]
    def walking_edge(a,b):
        if abs(a[1]-b[1])>.501:return False
        # Actual half-block walking is a step/drop, not a diagonal line
        # through the old paving cube. Check the raised horizontal body and
        # the vertical adjustment separately; game walking remains pending.
        top=max(a[1],b[1]);aa=[a[0],top,a[2]];bb=[b[0],top,b[2]]
        return sweep(a,aa) and sweep(aa,bb) and sweep(bb,b)
    for case in chosen:
        samples=[];failures=[];last=None
        for a,b in zip(case['path'],case['path'][1:]):
            n=max(1,math.ceil(math.dist(a,b)/.25))
            for j in range(n+1):
                p=[a[k]+(b[k]-a[k])*j/n for k in range(3)];x,z=math.floor(p[0]),math.floor(p[2])
                # Quantized half-block native road top may differ from the
                # declared line by <= half block.  Never find an arbitrary roof.
                candidates=[]
                for xx in range(math.floor(p[0]-.3),math.floor(p[0]+.3-1e-7)+1):
                    for zz in range(math.floor(p[2]-.3),math.floor(p[2]+.3-1e-7)+1):
                        for yy in range(math.floor(p[1])-1,math.floor(p[1])+1):
                            for box in boxes(w.get(xx,yy,zz)) or []:
                                top=yy+box[4]
                                if (xx+box[0]<p[0]+.3 and xx+box[3]>p[0]-.3 and
                                    zz+box[2]<p[2]+.3 and zz+box[5]>p[2]-.3 and abs(top-p[1])<=.501):
                                    candidates.append(top)
                if not candidates:failures.append(dict(at=p,reason='NO_DECLARED_DATUM_BEARING'));continue
                f=max(candidates);actual=[p[0],f,p[2]]
                hit=collision(actual)
                if hit:failures.append(dict(at=actual,reason='ACTUAL_BODY_OBSTRUCTION',hits=hit[:4]))
                elif last is not None and not walking_edge(last,actual):
                    failures.append(dict(at=actual,reason='STEP_OR_SWEPT_BODY_OBSTRUCTION',from_point=last))
                samples.append(actual);last=actual
        path_reports.append(dict(id=case['id'],declared_path=case['path'],sample_spacing_m=.25,
            shape_sweep='exact raised-horizontal + vertical step/drop AABB, native step <=0.501m',
            samples=len(samples),failures=failures,status='FINITE_NATIVE_SHAPE_PATH_CLEAR' if not failures else 'ACTUAL_PATH_BLOCKER_REVIEW',
            native_game_walk_passed=False))
    vehicles=[q for q in audit['issues'] if q['kind']=='VEHICLE_COMPONENT_REVIEW']
    vehicle_groups=Counter((q['inherited_flags'],round(min(x[2] for x in q['obstruction'])-q['position'][1],4)) for q in vehicles)
    regressed=[dict(q,declared_components=[c['id'] for c in components if c['bounds'][0]<=q['position'][0]<=c['bounds'][3] and c['bounds'][2]<=q['position'][2]<=c['bounds'][5]])
               for q in vehicles if q['inherited_flags']&8]
    columns=[]
    for x,z in [(350,83),(360,83),(390,83),(420,77),(420,75),(-1455,688)]:
        lo,hi=(69,85) if x>0 else (103,111)
        columns.append(dict(x=x,z=z,states=[[y,w.get(x,y,z)] for y in range(lo,hi+1)]))
    after={str(p):sha(Path(p)) for p in before}
    assert before==after,'World region changed during read; this observation cannot be published'
    result=dict(schema='projectseele.r52.road-component-readonly-review.v1',world=str(WORLD),world_written=False,
        read_scope='remaining ten nonstation candidates' if args.remaining_ten else '1607 player exceptions + finite declared paths',
        read_started_utc=read_start,read_completed_utc=datetime.now(timezone.utc).isoformat(),
        actual_region_sha256=before,
        inputs=[dict(path=str(p),sha256=sha(p)) for p in (report_file,current_file,source,shapes_file,metadata_file,cases_file,shelter_file,authority_file)],
        full_declared_columns=int(len(coords)),original_review_counts=audit['counts'],
        player_status_counts=dict(status_counts),player_columns=rows,
        station_rectangles_are_only_hints=True,nonstation_local_components=local,declared_public_paths=path_reports,
        vehicle_capacity_groups=[dict(inherited_flags=k[0],headroom_m=k[1],columns=v) for k,v in sorted(vehicle_groups.items())],
        old_six_metre_clear_now_review=regressed,exact_columns=columns,unknown_shapes=dict(unknown),
        native_walk_passed=False,native_vehicle_route_passed=False,road_art_passed=False,
        limits=['No World or traffic writes. No whole-map or native journey PASS.',
                'Declared component bounds attribute ownership only; they never prove passability.',
                'Local bypass is a finite current-shape player proof, not vehicle width or an end-to-end route.',
                'Different datum paving is measured at surveyed expected height or a nearby half-block top, never arbitrary highest roof.',
                'Exact block-shape reader does not model moving entities or live ticket gates.'],seconds=time.monotonic()-start)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(player_status_counts=result['player_status_counts'],local_components=len(local),
        local_bypass_columns=sum(q['issue_columns'] for q in local if q['paths']),paths=[dict(id=q['id'],status=q['status'],failures=len(q['failures'])) for q in path_reports],
        vehicle_previous_six_clear=len(regressed),unknown_shapes=dict(unknown),seconds=result['seconds']),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
