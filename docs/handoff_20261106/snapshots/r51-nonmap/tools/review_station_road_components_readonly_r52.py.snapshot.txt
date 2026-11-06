"""Attribute 528 retained station exceptions and inspect real flat public paths.

Native fare gates/escalators are named operations, not roads to excavate.
No World, traffic, navigation, entity, source-resource or gameplay writes.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,math,hashlib
from collections import Counter,deque
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from classify_current_vehicle_roof_sources_r52 import primitive_index,ART,sha
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

BASE=ART/'r52_fresh_from_r51_20261009';WORLD=BASE/'WORLD_R52'
OUT=Path('.Codex/r52_runtime_close/roads_readonly/STATION_528_ACTUAL_COMPONENTS_AND_PUBLIC_PATHS.json')

def main():
    origin=OUT.with_name('CURRENT_ROAD_COMPONENT_REVIEW.json')
    old=json.loads(origin.read_text('utf8'))
    rows=[q for q in old['player_columns'] if q['station_domain_hint'] and q['status']=='ACTUAL_OBSTRUCTION_REQUIRES_COMPONENT_OR_PATH_REVIEW']
    assert len(rows)==528
    states={o[1] for q in rows for o in q['obstruction']}
    extras=[ART/'world_repair_r21/airport/nerv_un_airports/ops.json.gz',
        ART/'facility_r25/station_maps/all_stop_station_maps/ops.json.gz',
        ART/'facility_r25/map_finish/connected_sign_posts_and_hq_transfer/ops.json.gz',
        ART/'facility_r28/map_access/reachable_station_route_diagrams/ops.json.gz',
        ART/'facility_r24/station_civil_details/station_names_and_drainage/ops.json.gz',
        ART/'facility_r30/terminal_detail/nerv_terminal_furnishings/ops.json.gz',
        ART/'rebuild_r42/station_entrances/station_entry_legibility/ops.json.gz']
    buckets,_,pins=primitive_index(states,extras)
    civil_file=ART/'access_r22/transit/civil/station_contract.json'
    civil=json.loads(civil_file.read_text('utf8'))['stations']
    support_candidates={}
    for i,row in enumerate(rows):
        x,f,z=row['position']
        if row['obstruction'][0][1]!='minecraft:light_gray_concrete':continue
        for s in civil:
            cx,y,cz=s['center'];g=s['ground'];h=s['half']
            if abs(f-(g+1))>.01:continue
            u=x-cx if s['horizontal'] else z-cz;cross=z-cz if s['horizontal'] else x-cx
            if abs(cross)!=18 or not -h<=u<=h:continue
            # support_ops places the lower leg on side18; its original U
            # can be a regular frame station or ±3 beside a published port.
            regular=list(range(-h+2,h,16))
            if not any(abs(u-v)<=3 for v in regular):continue
            support_candidates[i]=dict(station=s['station'],line=s['line'],platform_ids=s['platform_ids'],
                local_u=u,local_side=cross//18,ground=g,platform_y=y,half=h,
                source='tools/station_lower_support_r45.py:support_ops',station_contract=str(civil_file))
    map_files=[ART/'facility_r25/station_maps/contract.json',ART/'facility_r28/map_access/contract.json']
    maps25=json.loads(map_files[0].read_text('utf8'))['boards'];maps28=json.loads(map_files[1].read_text('utf8'))['maps']
    case_file=WORLD/'quality_walk_cases.json';cases=json.loads(case_file.read_text('utf8'))
    issue_points=np.asarray([[q['position'][0]+.5,q['position'][1],q['position'][2]+.5] for q in rows])
    selected=[]
    public_words=('ground_access','public','ground_port','street_entry','concourse','centreline','centerline','ground_walk','station/','platform/','station_map','map_approach','station_prop','shop/','station_entrance')
    for case in cases:
        pts=case.get('path') or [case.get('start'),case.get('end')]
        if len(pts)<2 or any(p is None for p in pts):continue
        if not any(word in case['id'] for word in public_words):continue
        if max(p[1] for p in pts)-min(p[1] for p in pts)>.001:continue
        if sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))>300:continue
        touched=set()
        for a,b in zip(pts,pts[1:]):
            A=np.asarray(a);B=np.asarray(b);delta=(B-A)[[0,2]]
            denominator=float(delta@delta)
            t=np.clip(((issue_points[:,[0,2]]-A[[0,2]])@delta)/max(denominator,1e-12),0,1)
            closest=A[[0,2]]+t[:,None]*delta
            radius=4. if case.get('readingBoard') or 'map_approach' in case['id'] else 1.1
            near=(np.sum((issue_points[:,[0,2]]-closest)**2,axis=1)<=radius**2)&(np.abs(issue_points[:,1]-A[1])<=.501)
            touched.update(map(int,np.flatnonzero(near)))
        if touched:selected.append(dict(case=case,path=pts,touched=sorted(touched)))
    world=MeasuredWorld(WORLD)
    for q in rows:
        x,f,z=q['position'];world.box((x-1,math.floor(f)-2,z-1),(x+1,math.ceil(f)+4,z+1))
    for i,s in support_candidates.items():
        x,f,z=rows[i]['position'];world.box((x-5,math.floor(f)-2,z-5),(x+5,s['platform_y']+1,z+5))
    for q in selected:
        for a,b in zip(q['path'],q['path'][1:]):
            world.box(tuple(math.floor(min(a[k],b[k]))-(2 if k!=1 else 2) for k in range(3)),
                      tuple(math.ceil(max(a[k],b[k]))+(2 if k!=1 else 4) for k in range(3)))
    # Whole tea-room roof/side wall and its outside east route and two entries.
    world.box((-129,78,-192),(-111,88,-180))
    region_root=WORLD/'dimensions/projectseele/geofront/region'
    regions={region_root/f'r.{x//32}.{z//32}.mca' for x,z in world.selected}
    before={str(p):sha(p) for p in regions};started=datetime.now(timezone.utc).isoformat();world.load()
    shape_file=WORLD/'native_collision_shapes.json'
    shapes={canonical_state(k):v for k,v in json.loads(shape_file.read_text('utf8')).items()};unknown=Counter()
    def boxes(x,y,z):
        st=world.get(x,y,z)
        if st in AIR or st=='minecraft:light':return []
        bs=shapes.get(st)
        if bs is None:unknown[str(st)]+=1
        return bs
    def body(p,height=1.8):
        x,f,z=p;out=[]
        for X in range(math.floor(x-.3)-1,math.floor(x+.3-1e-7)+2):
            for Z in range(math.floor(z-.3)-1,math.floor(z+.3-1e-7)+2):
                for y in range(math.floor(f),math.ceil(f+height)):
                    for b in boxes(X,y,Z) or []:
                        if X+b[0]<x+.3-1e-7 and X+b[3]>x-.3+1e-7 and Z+b[2]<z+.3-1e-7 and Z+b[5]>z-.3+1e-7 and y+b[1]<f+height-1e-7 and y+b[4]>f+.001:
                            out.append(dict(at=[X,y,Z],state=world.get(X,y,Z),box=b))
        return out
    def floor(p):
        x,f,z=p;tops=[]
        for X in range(math.floor(x-.3),math.floor(x+.3-1e-7)+1):
            for Z in range(math.floor(z-.3),math.floor(z+.3-1e-7)+1):
                for y in range(math.floor(f)-1,math.floor(f)+1):
                    for b in boxes(X,y,Z) or []:
                        top=y+b[4]
                        if abs(top-f)<=.501 and X+b[0]<x+.3 and X+b[3]>x-.3 and Z+b[2]<z+.3 and Z+b[5]>z-.3:tops.append(top)
        return max(tops) if tops else None
    def inspect_path(identifier,path):
        hits=[];missing=[];step=[];last=None;count=0
        for a,b in zip(path,path[1:]):
            n=max(1,math.ceil(math.dist(a,b)/.25))
            for j in range(n+1):
                p=[a[k]+(b[k]-a[k])*j/n for k in range(3)];f=floor(p);count+=1
                if f is None:missing.append(p);continue
                actual=[p[0],f,p[2]];h=body(actual)
                if h:hits.append(dict(at=actual,hits=h))
                if last is not None and abs(f-last[1])>.501:step.append(dict(from_point=last,to_point=actual))
                last=actual
        static=[q for q in hits if any(not h['state'].startswith(('mtr:ticket_barrier','mtr:escalator','mtr:apg')) and '_door[' not in h['state'] and 'city_personnel_door[' not in h['state'] for h in q['hits'])]
        equipment=[q for q in hits if q not in static]
        return dict(id=identifier,path=path,sample_spacing_m=.25,samples=count,
                    static_body_obstructions=static,native_equipment_operation_samples=equipment,
                    missing_bearing=missing,step_gt_half=step,
                    status='STATIC_PUBLIC_PATH_REVIEW' if static or missing or step else 'NAMED_NATIVE_OPERATION_REQUIRED' if equipment else 'FINITE_SAVED_SHAPE_PATH_CLEAR',
                    native_walk_passed=False)
    observations=[];counts=Counter();mismatch=[]
    for i,q in enumerate(rows):
        x,f,z=q['position'];actual=[];matches=[]
        for y,st,mn in q['obstruction']:
            now=world.get(x,y,z);actual.append(dict(at=[x,y,z],expected_state=st,actual_state=now))
            if now!=st:mismatch.append(actual[-1]);continue
            for primitive in buckets[x//16,z//16]:
                b=primitive['box']
                if st==primitive['state'] and b[0]<=x<=b[3] and b[1]<=y<=b[4] and b[2]<=z<=b[5]:
                    if primitive not in matches:matches.append(primitive)
        declarations=[]
        for case in cases:
            a=case.get('readingBoard')
            if a and any(p['at']==a for p in actual):
                declarations.append(dict(kind='CURRENT_NAMED_ROUTE_MAP_READER',id=case['id'],anchor=a,
                    path=case.get('path') or [case.get('start'),case.get('end')],source=str(case_file)))
            if a and all(abs(a[k]-[x,f,z][k])<=3 for k in (0,2)):
                st=world.get(*a)
                if st and st.startswith('projectseele:station_departure_board['):
                    along=(1,0) if 'facing=north' in st or 'facing=south' in st else (0,1)
                    slots={(a[0]+side*along[0],Y,a[2]+side*along[1]) for side in (-1,1) for Y in range(a[1]-1,a[1]+2)}
                    post='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
                    if any(tuple(p['at']) in slots and p['actual_state']==post for p in actual):
                        declarations.append(dict(kind='CURRENT_NAMED_MAP_CONTINUOUS_STAND',id=case['id'],anchor=a,
                            actual_anchor_state=st,stand_recipe='tools/build_station_route_maps_r25.py + finish_station_maps_r25.py: two side posts',
                            source=str(case_file),literal_historical_op_match=False))
        for board in maps25:
            anchor=board['position']
            positions={tuple(anchor),*[tuple(p) for p in board['supports']],*[tuple([p[0],p[1]+1,p[2]]) for p in board['supports']]}
            if any(tuple(p['at']) in positions for p in actual):
                declarations.append(dict(kind='PUBLISHED_ROUTE_MAP_OR_SUPPORT',station=board['station'],line=board['line'],
                    platform_id=board['platform'],anchor=anchor,recipe_facing=board['facing'],reader=board['reader'],source=str(map_files[0]),
                    current_face_is_retained_observation=True))
        for board in maps28:
            a=board['board'];along=(1,0) if board['new_face'] in ('north','south') else (0,1)
            slots={tuple(a)}|{(a[0]+side*along[0],Y,a[2]+side*along[1]) for side in (-1,1) for Y in range(a[1]-1,a[1]+2)}
            if any(tuple(p['at']) in slots for p in actual):
                declarations.append(dict(kind='PUBLISHED_REACHABLE_ROUTE_MAP_OR_STAND',id=board['id'],anchor=a,
                    recipe_facing=board['new_face'],reader=board['reader'],approach=board['approach'],source=str(map_files[1])))
        support=support_candidates.get(i)
        if support:
            connected=all(world.get(x,Y,z)=='minecraft:light_gray_concrete' for Y in range(support['ground']+1,support['platform_y']-2))
            support=dict(support,actual_continuous_lower_column=connected,
                         upper_connection_state=world.get(x,support['platform_y']-2,z),bearing_state=world.get(x,support['ground'],z))
            if connected:declarations.append(dict(kind='ACTUAL_LOWER_STATION_FRAME_MATCHES_PUBLISHED_RECIPE',**support))
        native=[r for r in actual if r['actual_state'].startswith('mtr:')]
        if native:
            kind='NATIVE_FARE_GATE' if any('ticket_barrier' in r['actual_state'] for r in native) else 'NATIVE_ESCALATOR'
        elif declarations:kind='DECLARED_MAP_OR_CONNECTED_STATION_FRAME'
        elif matches:
            owner=matches[0]['owner'];kind='RECIPE_NAMED_COMPONENT'
            if 'station' in owner:kind='STATION_STRUCTURE_OR_FIXTURE'
            if 'airport' in owner:kind='AIRPORT_TERMINAL_COMPONENT'
        else:kind='EXACT_SOURCE_MATCH_NOT_FOUND'
        counts[kind]+=1
        observations.append(dict(q,current_observation=actual,source_primitive_matches=matches,published_component_declarations=declarations,component_kind=kind,
            public_flat_case_ids=[r['case']['id'] for r in selected if i in r['touched']],
            inherited_column_reopened=False,component_passed=False))
    paths=[dict(inspect_path(q['case']['id'],q['path']),touched_issue_indices=q['touched'],
                interaction_metadata={k:v for k,v in q['case'].items() if k not in ('path','start','end','id')}) for q in selected]
    support_detours=[]
    for i,s in support_candidates.items():
        x,f,z=rows[i]['position'];proof=dict(at=[x,f,z],station=s['station'],paths=[])
        cache={}
        def node(q):
            if q not in cache:
                p=[q[0]+.5,f,q[1]+.5];g=floor(p)
                cache[q]=g if g is not None and not body([p[0],g,p[2]]) else None
            return cache[q]
        for dx,dz in ((1,0),(0,1)):
            start=(x-dx,z-dz);end=(x+dx,z+dz)
            if node(start) is None or node(end) is None:continue
            parents={start:None};queue=deque([start])
            while queue and end not in parents:
                p=queue.popleft()
                for ox,oz in ((1,0),(-1,0),(0,1),(0,-1)):
                    q=p[0]+ox,p[1]+oz
                    if q in parents or not x-4<=q[0]<=x+4 or not z-4<=q[1]<=z+4:continue
                    if node(q) is None or abs(node(q)-node(p))>.501:continue
                    # Body is .6m wide; quarter-metre edge samples are also
                    # checked in the final finite actual path readback below.
                    parents[q]=p;queue.append(q)
            if end in parents:
                result=[];q=end
                while q is not None:result.append([q[0]+.5,node(q),q[1]+.5]);q=parents[q]
                checked=inspect_path('station_lower_frame/local_detour/'+str(i),list(reversed(result)))
                if checked['status']=='FINITE_SAVED_SHAPE_PATH_CLEAR':proof['paths'].append(checked)
        proof['status']='FINITE_CURRENT_PLINTH_DETOUR' if proof['paths'] else 'NO_LOCAL_PLINTH_DETOUR_PROOF'
        support_detours.append(proof)
    cafe_paths=[inspect_path('current_tea_room_east_1m_clear_path',[[-113.5,81,-190.5],[-113.5,81,-181.5]])]
    for c in cases:
        if c['id'] in ('r24/shop/第三新东京中央/-2.5/in','r24/shop/第三新东京中央/2.5/in'):
            cafe_paths.append(inspect_path(c['id'],c.get('path') or [c['start'],c['end']]))
    roof=[dict(at=[x,85,z],state=world.get(x,85,z),west_neighbor=world.get(x-1,85,z),below=world.get(x,84,z))
          for x in range(-127,-113) for z in range(-189,-182)]
    walls=[dict(at=[-115,y,z],state=world.get(-115,y,z)) for y in range(81,85) for z in range(-188,-183)]
    after={str(p):sha(Path(p)) for p in before};assert before==after,'World changed during component read'
    result=dict(schema='projectseele.r52.station-road-component-readonly.v1',world=str(WORLD),world_written=False,
        read_started_utc=started,read_completed_utc=datetime.now(timezone.utc).isoformat(),actual_region_sha256=before,
        source_component_pins=pins+[{ 'path':str(p),'sha256':sha(p)} for p in (origin,case_file,shape_file,civil_file,*map_files,Path('tools/station_lower_support_r45.py'))],
        station_old_columns_checked=len(observations),current_state_mismatches=mismatch,component_counts=dict(counts),
        columns=observations,selected_actual_flat_public_paths=paths,actual_lower_frame_local_detours=support_detours,
        tea_room_complete_roof_98=roof,tea_room_east_support_wall=walls,tea_room_public_paths=cafe_paths,
        unknown_shapes=dict(unknown),native_walk_passed=False,all_station_roads_passed=False,
        limits=['Recipe matching requires actual XYZ and actual current state; no rectangle pass.',
            'Closed fare gates, real moving escalators and doors are retained native uses, not roads to excavate.',
            'Finite public paths use quarter-metre actual-bearing/body samples; this is not complete swept-native gameplay.',
            'Sloped stairs/escalator paths remain named native operations; flat-path static failures are review findings, not automatic demolition.',
            'The entire tea-room roof and its actual east support were read; do not retire one isolated edge cell.'])
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(columns=len(observations),components=dict(counts),source_unmatched=sum(not q['source_primitive_matches'] for q in observations),
        state_mismatches=len(mismatch),public_paths=len(paths),path_statuses=dict(Counter(q['status'] for q in paths)),
        cafe=[dict(id=q['id'],status=q['status'],hits=len(q['static_body_obstructions']),missing=len(q['missing_bearing'])) for q in cafe_paths],unknown=dict(unknown)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
