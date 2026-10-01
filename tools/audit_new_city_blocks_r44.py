"""Whole proposed floors/doors/street datums and current exact inverse preflight."""
from pathlib import Path
from collections import Counter,deque
import argparse,gzip,json,math
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();out=a.output or a.plan/'whole_component_audit.json';assert not out.exists()
    rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')];after={tuple(r['pos']):r['after'] for r in rows};w=MeasuredWorld(WORLD)
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    x0,x1,z0,z1=district['bounds'];y0=min(r['pos'][1] for r in rows)-3;y1=max(r['pos'][1] for r in rows)+3
    # Unchanged air, lower support and landing surfaces are part of the
    # component. Loading changed-coordinate sections alone creates false None.
    w.box((x0-12,y0,z0-12),(x1+12,y1,z1+12))
    for b in district['buildings']:
        bx,bz,bX,bZ=b['bounds']
        bottom=math.floor(min(b['floor_feet']))-3
        top=max(math.ceil(max(b['floor_feet'])+2),math.ceil(b['roof'])+2)
        w.box((bx-2,bottom,bz-2),(bX+2,top,bZ+2))
    roads=json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']
    for r in roads:
        rx,rz=r['pos'];feet=r['native_feet']
        w.box((rx,math.floor(feet)-3,rz),(rx,math.ceil(feet)+3,rz))
    for c in json.loads((a.plan/'native_cases.json').read_text('utf8')):
        for first,last in zip(c['path'],c['path'][1:]):
            w.box(tuple(math.floor(min(first[k],last[k]))-3 for k in range(3)),tuple(math.ceil(max(first[k],last[k]))+3 for k in range(3)))
    w.load();shape={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    source_shapes={}
    if (a.plan/'source_shape_candidates.json').exists():
        source_shapes={canonical_state(r['state']):[[v/16 for v in b] for b in r['source_boxes_pixels']] for r in json.loads((a.plan/'source_shape_candidates.json').read_text('utf8'))['cases']}
    def state(x,y,z):return after.get((x,y,z),w.get(x,y,z))
    unknown=Counter();errors=[]
    def boxes(st,doors_open=False):
        if st in AIR or st=='minecraft:light':return []
        if doors_open and st and '_door[' in st:st=st.replace('open=false','open=true')
        # CityPersonnelDoorR44 inherits DoorBlock geometry unchanged and only
        # overrides use(). Alias the exact native IRON state, never a cube.
        if st and st.startswith('projectseele:city_personnel_door['):st=st.replace('projectseele:city_personnel_door[','minecraft:iron_door[')
        # Vanilla wood doors inherit the same DoorBlock voxel shape as iron;
        # use its measured cardinal/hinge/open state, not a full-cube guess.
        if st and any(st.startswith('minecraft:'+n+'_door[') for n in ['oak','spruce','birch','dark_oak']):st='minecraft:iron_door['+st.split('[',1)[1]
        v=shape.get(st,source_shapes.get(st))
        if v is None and st and st.startswith('minecraft:brick_stairs['):v=shape.get(st.replace('minecraft:brick_stairs[','minecraft:polished_andesite_stairs['))
        if v is None and st and st.startswith('minecraft:iron_door['):
            props=properties(st);heading=props.get('facing');source=st.replace('facing='+heading,'facing=north')
            native=shape.get(source)
            # DoorBlock cardinal states are rigid rotations of the same
            # native NORTH state; preserve hinge, half, open and powered.
            if native is not None:
                turns={'north':0,'east':1,'south':2,'west':3}[heading];v=[]
                for box in native:
                    corners=[(box[0],box[2]),(box[0],box[5]),(box[3],box[2]),(box[3],box[5])]
                    for _ in range(turns):corners=[(1-z,x) for x,z in corners]
                    v.append([min(x for x,z in corners),box[1],min(z for x,z in corners),max(x for x,z in corners),box[4],max(z for x,z in corners)])
        if v is None:unknown[str(st)]+=1
        return v
    def standable(x,z,feet):
        ys=range(math.floor(feet)-2,math.ceil(feet));supported=False
        for y in ys:
            bs=boxes(state(x,y,z))
            if bs is not None and any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<.001 for b in bs):supported=True
        if not supported:return False
        for y in range(math.floor(feet),math.ceil(feet+1.8)):
            bs=boxes(state(x,y,z),True)
            if bs is None or any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and y+b[1]<feet+1.8 and y+b[4]>feet+.001 for b in bs):return False
        return True
    def capsule_at(point,expected_feet=None,tolerance=0):
        px,feet,pz=point;expected=feet if expected_feet is None else expected_feet;supports=set()
        for xx in range(math.floor(px-.3+1e-7),math.floor(px+.3-1e-7)+1):
            for zz in range(math.floor(pz-.3+1e-7),math.floor(pz+.3-1e-7)+1):
                for yy in range(math.floor(expected-tolerance)-2,math.ceil(expected+tolerance)+1):
                    bs=boxes(state(xx,yy,zz),True)
                    if bs is None:continue
                    for t in bs:
                        if xx+t[0]<px+.3-1e-7 and xx+t[3]>px-.3+1e-7 and zz+t[2]<pz+.3-1e-7 and zz+t[5]>pz-.3+1e-7 and abs(yy+t[4]-expected)<=tolerance+.001:supports.add(yy+t[4])
        for actual in sorted(supports,key=lambda y:abs(y-expected)):
            clear=True
            for xx in range(math.floor(px-.3+1e-7),math.floor(px+.3-1e-7)+1):
                for zz in range(math.floor(pz-.3+1e-7),math.floor(pz+.3-1e-7)+1):
                    for yy in range(math.floor(actual),math.ceil(actual+1.8)):
                        bs=boxes(state(xx,yy,zz),True)
                        if bs is None or any(xx+t[0]<px+.3-1e-7 and xx+t[3]>px-.3+1e-7 and zz+t[2]<pz+.3-1e-7 and zz+t[5]>pz-.3+1e-7 and yy+t[1]<actual+1.8-1e-7 and yy+t[4]>actual+1e-7 for t in bs):clear=False
            if clear:return actual
        return None
    floors=[];floor_cases=[]
    for b in district['buildings']:
        x,z,X,Z=b['bounds']
        for n,feet in enumerate(b['floor_feet']):
            points={(xx,zz) for xx in range(x+1,X) for zz in range(z+1,Z) if standable(xx,zz,feet)}
            # The full open landing is the declared seed; a stair void is not an occupied floor.
            seed=tuple(b.get('landing_seed',[x+9,z+3]));reachable=set();parents={seed:None};todo=deque([seed]) if seed in points else deque()
            while todo:
                q=todo.popleft()
                if q in reachable:continue
                reachable.add(q)
                for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nxt=q[0]+dx,q[1]+dz
                    if nxt in points and nxt not in parents:parents[nxt]=q;todo.append(nxt)
            detached=points-reachable
            floors.append(dict(id=b['id']+f'/floor{n+1}',feet=feet,whole_standable_cells=len(points),reachable_from_public_landing=len(reachable),detached_cells=len(detached),detached_examples=sorted(detached)[:12]))
            if not reachable or detached:errors.append(dict(kind='WHOLE_OCCUPIED_FLOOR_NOT_CONNECTED_TO_ITS_REAL_PUBLIC_LANDING',floor=floors[-1]))
            else:
                # Every complete row segment belongs to a native case. The
                # BFS approach preserves furniture/room walls rather than
                # drawing diagonal shortcuts between nominal floor labels.
                def approach(q):
                    route=[]
                    while q is not None:route.append(q);q=parents[q]
                    return route[::-1]
                for zz in range(z+1,Z):
                    xs=sorted(xx for xx,zp in points if zp==zz);runs=[]
                    for xx in xs:
                        if not runs or xx>runs[-1][-1]+1:runs.append([xx])
                        else:runs[-1].append(xx)
                    for part,run in enumerate(runs):
                        route=approach((run[0],zz))+[(xx,zz) for xx in run[1:]]
                        if len(route)<2:continue
                        path=[[xx+.5,feet,zp+.5] for xx,zp in route]
                        identity=b['id']+f'/floor{n+1}/whole_row_{zz-z}_{part}'
                        floor_cases.append(dict(id=identity,path=path,native_passed=False,coverage='Full actual standable row; BFS approach from the actual public landing'))
        ex,feet,ez=b['entry']
        if not standable(ex,ez,feet):errors.append(dict(kind='NEW_DECLARED_ENTRANCE_NOT_STANDABLE',building=b['id'],entry=b['entry']))
    h={tuple(r['pos']):r['native_feet'] for r in roads};roaderrors=[];gradients=[]
    for q,feet in h.items():
        if not standable(*q,feet):roaderrors.append(dict(pos=[q[0],feet,q[1]],kind='FULL_STREET_FOOT_OR_HEADROOM_INVALID'))
        for dx,dz in [(1,0),(0,1)]:
            nxt=q[0]+dx,q[1]+dz
            if nxt in h and abs(h[nxt]-feet)>.501:roaderrors.append(dict(pos=[q[0],feet,q[1]],to=[nxt[0],h[nxt],nxt[1]],kind='UNDESIGNED_STREET_STEP'))
            if nxt in h:gradients.append(abs(h[nxt]-feet))
    errors.extend(roaderrors)
    doors=[]
    for q,st in after.items():
        if '_door[' in st and 'half=lower' in st:
            pair=state(q[0],q[1]+1,q[2]);complete=pair is not None and st.replace('half=lower','half=upper')==pair
            doors.append(dict(pos=q,complete=complete))
            if not complete:errors.append(dict(kind='INCOMPLETE_REAL_DOOR_PAIR',pos=q,state=st,upper=pair))
    court_cases=[];court_audits=[];public_seams=[]
    if (a.plan/'parcel_components.json').exists():
        parcel=json.loads((a.plan/'parcel_components.json').read_text('utf8'))
        # Individually reachable parcels and individually valid streets can
        # still meet at an unsafe vertical lip. Audit the assembled public
        # surface before splitting it into per-building BFS obligations.
        public_surface={q:dict(feet=feet,owner='retained_authorized_street') for q,feet in h.items()}
        for r in parcel['full_court_columns']:
            q=tuple(r['pos']);feet=r['native_feet']
            previous=public_surface.get(q)
            if previous is not None and abs(previous['feet']-feet)>.001:
                errors.append(dict(kind='PUBLIC_COMPONENTS_DISAGREE_ON_SAME_COLUMN',pos=q,
                                   first=previous,second=dict(feet=feet,owner=r['owner'])))
            public_surface[q]=dict(feet=feet,owner=r['owner'])
        for q,current in public_surface.items():
            for dx,dz in [(1,0),(0,1)]:
                nxt=q[0]+dx,q[1]+dz;other=public_surface.get(nxt)
                if other is None or abs(current['feet']-other['feet'])<=.501:continue
                if not standable(*q,current['feet']) or not standable(*nxt,other['feet']):continue
                public_seams.append(dict(kind='UNDESIGNED_PUBLIC_COMPONENT_SEAM',
                    pos=[q[0],current['feet'],q[1]],to=[nxt[0],other['feet'],nxt[1]],
                    owners=[current['owner'],other['owner']]))
        errors.extend(public_seams)
        for b in district['buildings']:
            declared=[r for r in parcel['full_court_columns'] if r['owner']==b['id']];court_heights={tuple(r['pos']):r['native_feet'] for r in declared}
            if not declared:continue  # Unchanged parcels are not part of a selected full-garden revision.
            points={q for q,feet in court_heights.items() if standable(*q,feet)};entry=tuple([b['entry'][0],b['entry'][2]])
            neighbours={q:feet for q,feet in h.items() if points and min(x for x,z in points)-1<=q[0]<=max(x for x,z in points)+1 and min(z for x,z in points)-1<=q[1]<=max(z for x,z in points)+1 and standable(*q,feet)}
            allowed_heights=dict(court_heights,**{})|neighbours;allowed=points|set(neighbours)
            start=min(points,key=lambda q:math.dist(q,entry)) if points else None;todo=deque([start]) if start else deque();parents={start:None} if start else {}
            while todo:
                q=todo.popleft()
                for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nxt=q[0]+dx,q[1]+dz
                    if nxt in allowed and nxt not in parents and abs(allowed_heights[nxt]-allowed_heights[q])<=.501:parents[nxt]=q;todo.append(nxt)
            detached=points-set(parents);court_audits.append(dict(building=b['id'],complete_declared_frontage_columns=len(court_heights),actual_standable_columns=len(points),retaining_or_fixture_columns=len(court_heights)-len(points),adjacent_authorized_street_handoff_columns=len(neighbours),detached_actual_standing_columns=len(detached),seed=start))
            if detached or not parents:errors.append(dict(kind='WHOLE_FRONT_COURT_NOT_CONNECTED_TO_ACTUAL_ENTRY',building=b['id'],detached=sorted(detached)))
            for zz in sorted({z for x,z in points}):
                xs=sorted(x for x,z in points if z==zz);runs=[]
                for xx in xs:
                    if not runs or xx>runs[-1][-1]+1:runs.append([xx])
                    else:runs[-1].append(xx)
                for n,run in enumerate(runs):
                    q=run[0],zz
                    if q not in parents:continue
                    route=[]
                    while q is not None:route.append(q);q=parents[q]
                    route.reverse();route.extend((xx,zz) for xx in run[1:])
                    if len(route)>1:court_cases.append(dict(id=b['id']+f'/whole_forecourt_row{zz}_{n}',path=[[xx+.5,allowed_heights[xx,zp],zp+.5] for xx,zp in route],native_passed=False))
    ports=[];path_witnesses=[]
    for case in json.loads((a.plan/'native_cases.json').read_text('utf8')):
        for which,point in [('start',case['path'][0]),('end',case['path'][-1])]:
            actual=capsule_at(point);ports.append(dict(id=case['id'],port=which,point=point,clear_supported=actual is not None))
            if actual is None:errors.append(dict(kind='THREE_DIMENSIONAL_DECLARED_PORT_UNSUPPORTED_OR_OBSTRUCTED',id=case['id'],port=which,point=point))
        bad=[]
        for first,last in zip(case['path'],case['path'][1:]):
            length=math.hypot(last[0]-first[0],last[2]-first[2]);n=max(1,math.ceil(length/.25))
            for i in range(n+1):
                point=[first[k]+(last[k]-first[k])*i/n for k in range(3)]
                if capsule_at(point,point[1],1.05 if abs(first[1]-last[1])>.01 else .001) is None:
                    bad.append(point);break
        path_witnesses.append(dict(id=case['id'],complete_declared_path_has_static_capsule_support=not bad,first_bad_samples=bad))
        if bad:errors.append(dict(kind='THREE_DIMENSIONAL_ROUTE_GEOMETRY_DIAGNOSTIC_FAIL',id=case['id'],first_bad_samples=bad))
    result=dict(new_buildings=len(district['buildings']),whole_floors=floors,street_columns=len(h),doors=doors,
        failures=errors,unknown_shapes=dict(unknown),source_shape_dependencies=list(source_shapes),source_shape_native_verification_pending=bool(source_shapes),whole_front_courts=court_audits,whole_public_component_seams=public_seams,
        three_dimensional_ports=ports,three_dimensional_route_witnesses=path_witnesses,static_passed=not errors and not unknown,native_walk_vehicle_passed=False,visual_passed=False,world_written=False,
        rule='Every actual standable interior cell is checked, while declared stair wells and furniture collision cells remain separate spaces. Doors are opened by their existing native property for path obligation only; natural interaction still requires root native testing. All street columns, not just route centres, preserve support/headroom and half-block adjacencies.')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(a.plan.name,'floor',len(floors),'street',len(h),'doors',len(doors),'fails',len(errors),'unknown',dict(unknown),flush=True)
    cases_path=out.with_name(out.stem+'.native_floor_cases.json')
    cases_path.write_text(json.dumps(floor_cases,ensure_ascii=False,indent=2),'utf8')
    out.with_name(out.stem+'.native_court_cases.json').write_text(json.dumps(court_cases,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
