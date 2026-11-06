"""Independently verify the saved two-station offline candidate and its limits.

Reads immutable exports only. No world, Simulator, native database or JAR access.
"""
import argparse, collections, json, math
from pathlib import Path
import numpy as np
import nbtlib
from shapely.geometry import Point, Polygon, LineString, MultiPoint, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from author_kamonomiya_station import voxel_box
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk, Overlay
from evaluate_tsukahara_iwahara_geometry import point
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR

OPEN=AIR|{'minecraft:light'}
ALLOWED=SOIL|OPEN|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=lambda q:q.item()),'utf8')

def walker(e,shapes):
    w=Walker.__new__(Walker);w.reader=e;w.shapes=shapes;w.cache={};return w

def exact_edits(e):
    result={};roundtrip=[]
    for file in sorted((e.folder/'delta').glob('*.npz')):
        with np.load(file)as f:
            palette=list(map(str,f['palette']));coords=f['coordinates'];ranges=f['ranges'];indices=f['indices'];before=f['before'];after=f['after']
            rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
            forward=r['before'].copy();reverse=r['after'].copy();valid=True
            for i,(cx,cz)in enumerate(coords):
                ri=r['index'][int(cx),int(cz)]
                for j in range(int(ranges[i]),int(ranges[i+1])):
                    at=int(indices[j]);p=int(cx)*16+at%16,at//256-128,int(cz)*16+(at%256)//16
                    old,new=palette[int(before[j])],palette[int(after[j])]
                    valid&=p not in result and old!=new and old==e.state(*p,True) and new==e.state(*p)
                    result[p]=(old,new)
                    forward[ri].reshape(-1)[at]=r['ids'][new]
                    reverse[ri].reshape(-1)[at]=r['ids'][old]
            roundtrip.append(dict(region=file.name,delta_preconditions=bool(valid),forward_equal=bool(np.array_equal(forward,r['after'])),reverse_equal=bool(np.array_equal(reverse,r['before']))))
    return result,roundtrip

def water_geometry(geometry):
    evidence=json.loads((geometry/'site-evidence.json').read_text('utf8'));features={f['index']:f for s in evidence['stations']for f in s['nearby_gis']}
    return unary_union([shape(f['geometry'])for f in features.values()if f['properties']['source_layer']in('WA','RvrCL','WStrL')]).buffer(3)

def main(a):
    a.out.mkdir(exist_ok=False);errors=[];e=Editor(a.candidate)
    d=json.loads((a.candidate/'station-design.json').read_text('utf8'));m=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    cap=json.loads((a.candidate/'capture.json').read_text('utf8'));shapes=json.loads(a.shapes.read_text('utf8'));edits,roundtrip=exact_edits(e)
    source_equal=[]
    for f in sorted((a.source/'source').glob('*.npz')):
        with np.load(f)as left,np.load(a.candidate/'source'/f.name)as right:
            source_equal.append(dict(region=f.name,equal=left.files==right.files and all(np.array_equal(left[k],right[k])for k in left.files)))
    exact_declared={tuple(q['pos']):(q['before'],q['after'])for q in json.loads((a.candidate/'exact-edits.json').read_text('utf8'))}
    if edits!=exact_declared:errors.append('saved delta and declared exact edits differ')
    if len(edits)!=m['cells']:errors.append('manifest cell count differs')
    if not all(v['equal']for v in source_equal)or not all(v['delta_preconditions']and v['forward_equal']and v['reverse_equal']for v in roundtrip):errors.append('source or reversible delta mismatch')
    devices=nbtlib.load(a.candidate/'captured-devices.dat')['Devices'];device_positions={tuple(int(t[k])for k in('x','y','z'))for t in devices}
    devices_equal=devices==nbtlib.load(a.source/'captured-devices.dat')['Devices']
    actors_equal=cap.get('actors')==json.loads((a.source/'capture.json').read_text('utf8')).get('actors')==[]
    with np.load(a.authority/'network.npz')as f:ax,az,*_=map(int,f['bounds']);walk=f['walk'];road=f['road']
    water=water_geometry(a.geometry);wet=prep(water)
    def reserve(p):return wet.intersects(box(p[0],p[2],p[0]+1,p[2]+1))
    def bridgevolume(p):return 2729<=p[0]<=2744 and -687<=p[2]<=-683 and p[1]>=-73
    def protect(p,before,after):
        reasons=[]
        if before.split('[')[0]not in ALLOWED:reasons.append('original artificial object')
        if p in device_positions:reasons.append('original device')
        if walk[p[2]-az,p[0]-ax]or road[p[2]-az,p[0]-ax]:reasons.append('original public street')
        if reserve(p)and not bridgevolume(p):reasons.append('reserved watercourse')
        if not (2672<=p[0]<=2799 and -832<=p[2]<=-625 and -128<=p[1]<=319):reasons.append('outside complete source')
        return reasons
    violations=[dict(pos=p,reasons=protect(p,*v))for p,v in edits.items()if protect(p,*v)]
    if violations:errors.append('protected original object or water/street changed')
    if not devices_equal or not actors_equal or device_positions&edits.keys():errors.append('original devices or actors changed')
    sign_errors=[];sign_expected={tuple(q['pos']):q for q in d.get('expected_signs',[])};sign_changes=nbtlib.load(a.candidate/'block-entities.dat')['Changes']
    if len(sign_changes)!=len(sign_expected):sign_errors.append('new sign payload count differs')
    for row in sign_changes:
        tag=row.get('After')
        if tag is None:sign_errors.append('missing sign After');continue
        p=tuple(int(tag[k])for k in('x','y','z'))
        if p not in sign_expected or p in device_positions or 'Before'in row:sign_errors.append('sign touches original device or unexpected position');continue
        if e.state(*p)!='minecraft:oak_wall_sign[facing=east,waterlogged=false]'or e.state(p[0]-1,p[1],p[2])!='minecraft:polished_andesite':sign_errors.append('sign host or load-bearing post incorrect')
        if sign_expected[p]['name']not in str(tag)or not all(k in tag for k in('front_text','back_text','is_waxed')):sign_errors.append('sign name or complete text NBT missing')
    if sign_errors:errors.append('new signs invalid')
    original_water=sum(1 for p,(b,n)in edits.items()if b.startswith('minecraft:water'))
    bridge_below_changes=[p for p in edits if reserve(p)and p[1]<-73]
    # Exact column foot heights are read back, and the actual actor body excludes
    # canopy posts. Four-neighbour walking stays inside the declared public floor.
    w=walker(e,shapes);public={(x,z):g/2+1 for x,z,g in d['public_columns']};nodes={};floor_errors=[];blocked=[]
    for p,h in public.items():
        x,z=p;heights,unknown=w.floors(x+.5,h,z+.5)
        if not any(abs(v-h)<.00001 for v in heights):floor_errors.append(dict(pos=[x,h,z],heights=heights,unknown=unknown[:1]));continue
        issue=w.body(x+.5,h,z+.5)
        if issue:blocked.append(dict(pos=[x,h,z],reason=issue));continue
        nodes[p]=h
    post_columns={tuple(p)for c in d['canopies']for p in c['posts']}
    unexpected_blocked=[p for p in blocked if(p['pos'][0],p['pos'][2])not in post_columns]
    if floor_errors or unexpected_blocked:errors.append('public floor or headroom invalid')
    proofs=[];reachability=[]
    def path_to(parents,q):
        path=[]
        while q is not None:path.append([q[0]+.5,nodes[q],q[1]+.5]);q=parents[q]
        return path[::-1]
    for station,pathspec in zip(d['stations'],d['paths']):
        target=pathspec['street_target']['xyz'];start=math.floor(target[0]),math.floor(target[2]);parents={start:None}if start in nodes else{};queue=collections.deque(parents)
        while queue:
            p=queue.popleft()
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                q=p[0]+dx,p[1]+dz
                if q in nodes and q not in parents and abs(nodes[p]-nodes[q])<=.5:
                    parents[q]=p;queue.append(q)
        allplatform=set(map(tuple,station['platform_columns']));unreachable=allplatform-parents.keys()-post_columns
        reachability.append(dict(station=station['name'],street=target,platform_cells=len(allplatform),canopy_post_cells=len(allplatform&post_columns),reachable_platform_cells=len(allplatform&parents.keys()),unreachable=sorted(unreachable)))
        if unreachable or start not in parents:errors.append('station platform disconnected from exact old street '+station['name'])
        goals=[]
        for i,door in enumerate(station['doorway_candidates']):
            sol=door['solutions'][0];q=tuple(map(math.floor,sol['from_xz']));goals.append(('door_'+str(i+1),q,sol['from_xz']))
        ordered=sorted(allplatform,key=lambda p:p[0]+p[1])
        for name,cells in(('north_end',ordered[:25]),('south_end',ordered[-25:]),('covered_waiting',ordered[len(ordered)//2-12:len(ordered)//2+12])):
            valid=[p for p in cells if p in parents]
            if valid:goals.append((name,valid[len(valid)//2],None))
        for name,goal,precise in goals:
            if goal not in parents:errors.append('goal not reachable '+station['name']+' '+name);continue
            route=path_to(parents,goal)
            if precise:route.append([precise[0],-73,precise[1]])
            forward=strict_walk(w,route);reverse=strict_walk(w,route[::-1])
            if forward['kind']!='strict_static_clear'or reverse['kind']!='strict_static_clear':errors.append('strict actor path failed '+station['name']+' '+name)
            proofs.append(dict(station=station['name'],goal=name,path=route,forward=forward,reverse=reverse))
    additional=[]
    for row in d['paths']:
        route=[[x,public[math.floor(x),math.floor(z)],z]for x,y,z in row['centreline']]
        additional.append((row['name'],'exact_designed_access_centreline',route))
    for lane in(-1,0,1):additional.append(('岩原駅','bridge_lane_'+str(lane),[[x+.5,-71,-684.5+lane]for x in range(2729,2745)]))
    for name,goal,route in additional:
        forward=strict_walk(w,route);reverse=strict_walk(w,route[::-1])
        if forward['kind']!='strict_static_clear'or reverse['kind']!='strict_static_clear':errors.append('strict actor path failed '+name+' '+goal)
        proofs.append(dict(station=name,goal=goal,path=route,forward=forward,reverse=reverse))
    # Both complete bridge beams and all four bank piers must be present, with
    # exact contiguous connection to measured ground. No soil below is removed.
    def structural_check(reader):
        issues=[]
        for z in(-687,-683):
            for x in range(2729,2745):
                for y in(-73,-72):
                    if reader.state(x,y,z)!='minecraft:polished_deepslate':issues.append([x,y,z,'side beam'])
        for x,lo,z,_,hi,_ in d['bridge_supports']:
            if reserve((x,lo,z)):issues.append([x,lo,z,'bank pier enters water reservation'])
            for y in range(lo,hi+1):
                if reader.state(x,y,z)!='minecraft:stone_bricks':issues.append([x,y,z,'bank pier'])
            if reader.state(x,lo-1,z).split('[')[0]in OPEN:issues.append([x,lo-1,z,'unsupported pier root'])
        for x in range(2729,2745):
            for z in range(-686,-683):
                if reader.state(x,-73,z)!='minecraft:polished_deepslate':issues.append([x,-73,z,'cross deck beam'])
        return issues
    support_issues=structural_check(e)
    if support_issues:errors.append('bridge structural continuity failed')
    # Solid connectivity is rooted at the real soil floor of the crop. Before
    # and after graphs also detect newly disconnected retained artificial cells.
    ps=np.asarray(list(edits));lo=ps.min(0)-2;hi=ps.max(0)+2;lo[1]=min(-80,int(lo[1]));bounds=[*map(int,lo),*map(int,hi)]
    blocks,palette=voxel_box(e,bounds);solid=np.asarray([s.split('[')[0]not in OPEN for s in palette])[blocks];labels,n=label(solid);roots=set(map(int,np.unique(labels[0])))-{0}
    floating=[]
    for p,(b,s)in edits.items():
        if s.split('[')[0]in OPEN:continue
        k=int(labels[p[1]-lo[1],p[2]-lo[2],p[0]-lo[0]])
        if k not in roots:floating.append(p)
    if floating:errors.append('new ungrounded solid component')
    original_blocks,original_palette=voxel_box(Editor(a.source),bounds)
    original_solid=np.asarray([s.split('[')[0]not in OPEN for s in original_palette])[original_blocks]
    original_labels,_=label(original_solid);original_roots=set(map(int,np.unique(original_labels[0])))-{0}
    grounded_before=np.isin(original_labels,list(original_roots))&original_solid
    grounded_after=np.isin(labels,list(roots))&solid
    newly_detached=[]
    for iy,iz,ix in np.argwhere(grounded_before&solid&~grounded_after):
        p=int(ix+lo[0]),int(iy+lo[1]),int(iz+lo[2])
        if p not in edits:newly_detached.append(p)
    if newly_detached:errors.append('retained component lost its original measured-ground connection')
    new_natural_faces=collections.defaultdict(set)
    for(x,y,z),(before,after)in edits.items():
        if before.split('[')[0]in OPEN or after.split('[')[0]not in OPEN:continue
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=x+dx,y,z+dz
            if e.state(*q).split('[')[0]in SOIL:new_natural_faces[x+dx,z+dz,dx,dz].add(y)
    longest_new_natural_face=0
    for heights in new_natural_faces.values():
        ordered=sorted(heights);run=0;previous=None
        for y in ordered:
            run=run+1 if previous is not None and y==previous+1 else 1;previous=y;longest_new_natural_face=max(longest_new_natural_face,run)
    if longest_new_natural_face>2:errors.append('new exposed vertical natural sidewall needs engineered closure')
    # A conservative closed-car rectangle covers every visible cube, including
    # bogies. It is swept at .125 m using 9 m bogie span, not rail points alone.
    samples={q['id']:q for q in json.loads((a.geometry/'native-samples.json').read_text('utf8'))}
    edges=json.loads(a.edges.read_text('utf8'));variant=next(v for v in edges['variants']if v['variant']==d['variant'])
    if not all(samples[k]['valid']for k in variant['native_segments']):errors.append('native RailMath rejected a selected segment')
    if max(variant['joint_tangent_errors_degrees'])>1 or variant['maximum_native_grade']>.000001:errors.append('selected native tangent continuity or flat rail height failed')
    built=variant['native_segments'][1:4];line=LineString(np.concatenate([np.asarray(samples[k]['points'])[:,[0,2]]if i==0 else np.asarray(samples[k]['points'])[1:,[0,2]]for i,k in enumerate(variant['native_segments'])]))
    offset=samples[variant['native_segments'][0]]['native_length'];builtlength=sum(samples[k]['native_length']for k in built);polygons=[]
    for s in np.arange(offset,offset+builtlength+.0625,.125):
        c=point(line,s);u=point(line,s+4.5)-point(line,s-4.5);u/=np.linalg.norm(u);normal=np.array([-u[1],u[0]])
        polygons.append(Polygon([c+u*along+normal*across for along,across in[(-4.665,-1.3525),(4.665,-1.3525),(4.665,1.3525),(-4.665,1.3525)]]))
    envelope=unary_union(polygons);ep=prep(envelope);l,b,r,t=envelope.bounds;obstacles=[];sweep_columns=0
    for x in range(math.floor(l),math.ceil(r)):
        for z in range(math.floor(b),math.ceil(t)):
            if not ep.intersects(box(x,z,x+1,z+1)):continue
            sweep_columns+=1
            for y in range(-74,-70):
                st,boxes=w.boxes(x,y,z)
                if boxes is None:obstacles.append(dict(pos=[x,y,z],state=st,kind='unknown collision'));continue
                for q in boxes:
                    if y+q[1]<-70.3125 and y+q[4]>-73.96875 and ep.intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):
                        obstacles.append(dict(pos=[x,y,z],state=st,kind='visible-car conservative envelope'));break
    if obstacles:errors.append('visible vehicle envelope intersects world')
    # Conditional open-door boarding proof: floor union and true nonvisible
    # trigger are distinct. Static world space alone cannot establish boarding.
    boarding=[];closed_door_negatives=[]
    # The all-selected "closed" export also contains FLOOR / DOORWAY helper
    # geometry. Only the NORMAL visible export represents actual closed body.
    with np.load(a.models/'e44_mini_cab_3-visible-cubes.npz')as f:closed_cubes=f['cubes']
    model_lo=closed_cubes.reshape(-1,3).min(0);model_hi=closed_cubes.reshape(-1,3).max(0)
    if model_lo[0]<-1.3125001 or model_hi[0]>1.3125001 or model_lo[2]<-4.6250001 or model_hi[2]>4.6250001 or model_lo[1]<.0312499 or model_hi[1]>3.6875001:errors.append('actual visible model exceeds assumed sweep dimensions')
    closed_body_polys=[MultiPoint(cube[:,[0,2]]).convex_hull for cube in closed_cubes if cube[:,1].max()>1.00001 and cube[:,1].min()<2.79999]
    for station in d['stations']:
        p=np.asarray(samples[station['rail_id']]['points'])[:,[0,2]];rail=LineString(p);u=p[-1]-p[0];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        floor=unary_union([box(x,z,x+1,z+1)for x,z in station['platform_columns'] if e.state(x,-74,z).split('[')[0]not in OPEN])
        for car,door in enumerate(station['doorway_candidates']):
            c=point(rail,door['car_centre_s']);sol=door['solutions'][0];start=np.asarray(sol['from_xz']);end=np.asarray(sol['to_xz'])
            def rect(al,ah,nl,nh):return Polygon([c+u*A+n*N for A,N in((al,nl),(ah,nl),(ah,nh),(al,nh))])
            vehiclefloor=rect(-1.1875,1.1875,0,1.25);trigger=rect(-.875,.875,1.25,1.5);allfloor=floor.union(vehiclefloor);minimum=1.;maxalong=0.;touch=False;worldhits=[]
            closed_hits=0
            for f in np.linspace(0,1,177):
                q=start+(end-start)*f;body=box(q[0]-.3,q[1]-.3,q[0]+.3,q[1]+.3);minimum=min(minimum,body.intersection(allfloor).area);maxalong=max(maxalong,float(np.max(np.abs((np.asarray(body.exterior.coords)[:-1]-c)@u))));touch|=body.intersection(trigger).area>.005
                hit=w.body(q[0],-73,q[1])
                if hit:worldhits.append(hit)
                corners=np.asarray(body.exterior.coords)[:-1]-c;local_body=Polygon(np.column_stack((corners@n,corners@u)))
                if any(poly.intersection(local_body).area>1e-8 for poly in closed_body_polys):closed_hits+=1
            okay=minimum>.025 and maxalong<.875 and touch and not worldhits
            if not okay:errors.append('conditional door floor path failed')
            boarding.append(dict(station=station['name'],car=car+1,from_xyz=[start[0],-73,start[1]],to_xyz=[end[0],-73,end[1]],min_bearing_area=minimum,maximum_door_longitudinal_extent=maxalong,door_clear_halfwidth=.875,trigger_contact=bool(touch),world_body_hits=worldhits[:3],clear=okay,requires_stopped_car_and_fully_open_door=True))
            closed_door_negatives.append(dict(case='closed_visible_door_blocks_boarding',station=station['name'],car=car+1,closed_model_samples_intersecting_actor=closed_hits,rejected=closed_hits>0,trigger_alone_is_not_open_door_proof=True))
    negative=[]
    for proof in(proofs[:1]+proofs[-1:]):
        route=proof['path'];x,y,z=route[0];pos=math.floor(x),math.floor(y)-1,math.floor(z)
        for name,change in(('remove_measured_walking_floor',{pos:'minecraft:air'}),('block_real_path_head',{(pos[0],math.floor(y)+1,pos[2]):'minecraft:glass'})):
            nw=walker(Overlay(e,change),shapes);v=strict_walk(nw,[route[0],route[0]])
            negative.append(dict(case=name,station=proof['station'],mutations=[dict(pos=p,before=e.state(*p),after=s)for p,s in change.items()],rejected=v['kind']!='strict_static_clear',result=v))
    for pos in sorted(device_positions)[:1]:negative.append(dict(case='overwrite_original_device',pos=pos,before=e.state(*pos,True),after='minecraft:air',rejected=bool(protect(pos,e.state(*pos,True),'minecraft:air'))))
    p=(2735,-76,-685);negative.append(dict(case='remove_real_reserved_ground',pos=p,before=e.state(*p,True),after='minecraft:air',rejected=bool(protect(p,e.state(*p,True),'minecraft:air'))))
    # Structural fault injection checks the same explicit four-pier chain.
    for case,p in(('remove_measured_bank_pier_root',tuple(d['bridge_supports'][0][:3])),('cut_continuous_bridge_beam',(2736,-73,-687))):
        defects=structural_check(Overlay(e,{p:'minecraft:air'}));negative.append(dict(case=case,pos=p,before=e.state(*p),after='minecraft:air',rejected=bool(defects),detected=defects))
    negative.extend(closed_door_negatives)
    rejected=next((v for v in edges['variants']if max(v['joint_tangent_errors_degrees'])>1),None)
    if rejected:negative.append(dict(case='discontinuous_native_tangents_despite_valid_segments',variant=rejected['variant'],joint_tangent_errors_degrees=rejected['joint_tangent_errors_degrees'],rejected=max(rejected['joint_tangent_errors_degrees'])>1))
    if not all(v['rejected']for v in negative):errors.append('negative defect case not rejected')
    result=dict(errors=errors,cells=len(edits),exact_saved_delta_matches=edits==exact_declared,source_array_comparisons=source_equal,forward_reverse_delta_checks=roundtrip,
        original_devices_retained=len(devices),original_device_nbt_equal=bool(devices_equal),original_actors_equal=bool(actors_equal),protected_change_violations=violations,new_signs=len(sign_changes),sign_errors=sign_errors,
        original_water_blocks_changed=original_water,water_reserved_ground_changes=bridge_below_changes,water_reserve_is_gis_not_claim_of_actual_water=True,
        reachable_platforms=reachability,public_floor_errors=floor_errors,unexpected_public_obstructions=unexpected_blocked,designed_canopy_posts=blocked,
        paths=proofs,paths_verified=sum(p['forward']['kind']==p['reverse']['kind']=='strict_static_clear'for p in proofs),directions_checked=2*len(proofs),
        bridge_support_issues=support_issues,new_floating_solids=floating,newly_detached_retained_cells=newly_detached,newly_exposed_natural_side_faces=sum(map(len,new_natural_faces.values())),longest_new_natural_vertical_face=longest_new_natural_face,visible_model_sweep=dict(sample_pitch=.125,width=2.625,length=9.25,bogie_span=9,margin=.04,columns=sweep_columns,obstacles=obstacles,scope='paired platforms and interstation connection; outer approaches reserved'),
        conditional_boarding=boarding,actual_closed_model_bounds=[model_lo.tolist(),model_hi.tolist()],negative_cases=negative,native_joint_tangent_errors_degrees=variant['joint_tangent_errors_degrees'],native_maximum_grade=variant['maximum_native_grade'],
        pending=['native platform/station/rail registration by parent','outer approach bridge/civil interfaces and through-service','actual door opening, stopped train placement, door trigger and live boarding','production recipes, world preconditions and installed readback by parent','human in-game review'],
        offline_candidate_verified=not errors,world_written=False,whole_stage_two_accepted=False,operating_service_claimed=False)
    dump(a.out/'review.json',result);dump(a.candidate/'functional-check.json',dict(errors=errors,evidence=str(a.out/'review.json'),offline_candidate_verified=not errors,world_written=False,operating_service_claimed=False))
    print('Paired station check:',len(edits),'cells;',result['paths_verified'],'paths;',len(errors),'errors',flush=True)
    for error in errors:print(error[:500],flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','source','authority','geometry','edges','shapes','models','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
