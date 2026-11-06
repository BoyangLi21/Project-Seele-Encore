"""Plan and independently check finite diagonal stations from JSON captures.

Only frozen offline inputs are used. Native registration and through-service
remain separate. Source decoding is delegated to the shared Editor.
"""
import argparse
import collections
import gzip
import heapq
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPoint, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

from author_hakone_lakefront import Editor
from author_station_layout import route_columns, open_state, read, write
from author_kamonomiya_station import ALLOWED, OPEN
from map_pipeline.vehicle_envelopes import point, rectangle, envelope


def inputs(config):
    source = Path(config['source']); cap = read(source/'capture.json')
    e = Editor(source)
    with np.load(source/'measured.npz') as f: measured = {k: f[k].copy() for k in f.files}
    with np.load(Path(config['authority'])/'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds']); l,t,r,b = cap['bounds_xz']
        public=(f['walk']|f['road'])[t-az:b-az+1,l-ax:r-ax+1].copy()
        grade=f['grade2'][t-az:b-az+1,l-ax:r-ax+1].copy()
    features = json.loads(gzip.decompress(Path(config['features']).read_bytes()))['features']
    near = [q for q in features if q['properties'].get('source_layer') in ('RailCL','WA','RvrCL','WStrL','BldA')
            and shape(q['geometry']).intersects(box(l,t,r+1,b+1))]
    water = unary_union([shape(q['geometry']) for q in near if q['properties']['source_layer'] in ('WA','RvrCL','WStrL')]).buffer(3)
    return source,cap,e,measured,public,grade,near,water


def survey(a):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(exist_ok=False)
    report=[]
    for config in read(a.config)['sites']:
        source,cap,e,m,public,grade,near,water=inputs(config);l,t,r,b=cap['bounds_xz'];cx,cz=config['centre']
        fig,ax=plt.subplots(figsize=(11,10)); ax.imshow(m['top'],extent=[l,r+1,b+1,t],cmap='terrain',alpha=.65)
        z,x=np.where(public);ax.scatter(x+l+.5,z+t+.5,s=8,c='black',label='Retained street')
        z,x=np.where(m['protected']);ax.scatter(x+l+.5,z+t+.5,s=5,c='purple',label='Measured protected object')
        for geom in getattr(water,'geoms',[water]):
            if geom.is_empty:continue
            x,z=geom.exterior.xy;ax.fill(x,z,color='blue',alpha=.22)
        for q in near:
            geom=shape(q['geometry']);layer=q['properties']['source_layer']
            if layer=='RailCL':
                for line in getattr(geom,'geoms',[geom]):
                    x,z=line.xy;ax.plot(x,z,color='red',lw=1)
        rail=config['rail'];p=np.asarray([rail['from'],rail['to']]);ax.plot(p[:,0]+.5,p[:,2]+.5,color='lime',lw=3,label='Initial rail proposal')
        ax.scatter([cx],[cz],marker='+',c='black',s=100);ax.set(xlabel='World X',ylabel='World Z',title=config['id']+' measured source / GIS reservation',xlim=(l,r+1),ylim=(b+1,t));ax.legend();ax.grid(alpha=.3)
        fig.tight_layout();fig.savefig(a.out/(config['id']+'-survey.png'),dpi=130);plt.close(fig)
        targets=[]
        for iz,ix in np.argwhere(public):
            x,z=int(ix+l),int(iz+t);g=int(grade[iz,ix]);
            if any(not open_state(e.state(x,y,z))for y in range((g+1)//2+1,(g+1)//2+4)):continue
            targets.append(dict(x=x,z=z,grade2=g,distance=float(np.hypot(x+.5-cx,z+.5-cz))))
        targets.sort(key=lambda q:q['distance'])
        row=dict(id=config['id'],targets=targets[:40],water_distance=water.distance(Point(cx,cz)),
                 ground_at_centre=int(m['top'][math.floor(cz)-t,math.floor(cx)-l]),
                 water_features=[q for q in near if q['properties']['source_layer']in('WA','RvrCL','WStrL')],world_written=False)
        report.append(row);print(config['id'],'water distance',row['water_distance'],'targets',targets[:3],flush=True)
    write(a.out/'survey.json',report)


def plan(a):
    a.out.mkdir(exist_ok=False)
    for config in read(a.config)['sites']:
        source,cap,e,m,old_public,oldgrade,near,water=inputs(config);l,t,r,b=cap['bounds_xz']
        rail=config['rail'].copy();y=config.get('rail_y',-73);rail['from']=rail['from'].copy();rail['to']=rail['to'].copy()
        rail['from'][1]=rail['to'][1]=y
        line=LineString([(p[0]+.5,p[2]+.5)for p in (rail['from'],rail['to'])]);c=point(line,line.length/2)
        u=np.asarray(line.coords[-1])-np.asarray(line.coords[0]);u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        sweep=envelope(line,length=9.25,width=2.625,lateral_margin=.04,longitudinal_margin=.04,spacing=.125)
        # Extra physical end landings keep the nominal native platform's entire
        # length full-width despite the staircase-shaped 45 degree voxel cap.
        region=rectangle(c,u,n,-line.length/2-1.5,line.length/2+1.5,0,8)
        platform=set();wet_cache={}
        def wet(x,z):
            if (x,z)not in wet_cache:wet_cache[x,z]=water.intersects(box(x,z,x+1,z+1))
            return wet_cache[x,z]
        for x in range(math.floor(region.bounds[0]),math.ceil(region.bounds[2])):
            for z in range(math.floor(region.bounds[1]),math.ceil(region.bounds[3])):
                if region.covers(Point(x+.5,z+.5))and not sweep.intersects(box(x,z,x+1,z+1)):platform.add((x,z))
        # All approach routing stays on the platform side of the future railway.
        # Measured legacy objects are excluded across the complete 3 m width.
        start=min(platform,key=lambda q:np.linalg.norm(np.array(q)+.5-(c+n*6)))
        targets={}
        for iz,ix in np.argwhere(old_public):
            x,z=int(ix+l),int(iz+t);g=int(oldgrade[iz,ix])
            if np.dot(np.array([x+.5,z+.5])-c,n)<4:continue
            if any(not open_state(e.state(x,h,z))for h in range((g+1)//2+1,(g+1)//2+4)):continue
            targets[x,z]=g
        eligible={};cost={};parent={start:None};dist={start:0};queue=[(0,start)];end=None
        def available(p):
            if p in eligible:return eligible[p]
            x,z=p
            okay=l+3<=x<=r-3 and t+3<=z<=b-3
            if okay:
                for dx in(-1,0,1):
                    for dz in(-1,0,1):
                        xx,zz=x+dx,z+dz
                        if sweep.intersects(box(xx,zz,xx+1,zz+1)) or m['protected'][zz-t,xx-l]:okay=False;break
                        if wet(xx,zz) and int(m['highest'][zz-t,xx-l])>=y-1:okay=False;break
                        if not old_public[zz-t,xx-l] and any(e.state(xx,h,zz).split('[')[0]not in ALLOWED for h in range(min(int(m['top'][zz-t,xx-l])-1,y-2),y+4)):okay=False;break
                    if not okay:break
            eligible[p]=okay;return okay
        while queue:
            value,p=heapq.heappop(queue)
            if value!=dist[p]:continue
            if p in targets:end=p;break
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                q=p[0]+dx,p[1]+dz
                if not available(q):continue
                new=value+1+(1.1 if wet(*q)else 0)+(.02 if parent[p]and(q[0]-p[0],q[1]-p[1])!=(p[0]-parent[p][0],p[1]-parent[p][1])else 0)
                if new<dist.get(q,float('inf')):dist[q]=new;parent[q]=p;heapq.heappush(queue,(new,q))
        if end is None:raise ValueError('No complete measured street approach for '+config['id'])
        path=[];p=end
        while p is not None:path.append(p);p=parent[p]
        path=path[::-1];gstart=2*y;gend=targets[end];grades=[gstart]*len(path)
        # Put each half-step on a straight part of the route so turn landings
        # stay flat. Existing public columns are checked across the full width.
        need=abs(gend-gstart);sign=1 if gend>gstart else -1;steps=[]
        for i in range(len(path)-7,5,-1):
            if len(steps)>=need:break
            if all(path[k][0]==path[i][0]for k in range(i-2,i+3))or all(path[k][1]==path[i][1]for k in range(i-2,i+3)):
                if all(abs(i-j)>=3 for j in steps):steps.append(i)
        if len(steps)!=need:raise ValueError('No flat full-width landing for approach grade changes')
        for i in sorted(steps):
            for j in range(i,len(path)):grades[j]+=sign
        centres=[[x,z,g]for(x,z),g in zip(path,grades)]
        route=route_columns(centres,3)
        # Crop the station side surfaces around this single valid route; only
        # actually existing street cells may be the terminal anchor.
        for(x,z),g in route.items():
            if old_public[z-t,x-l]and int(oldgrade[z-t,x-l])!=g:raise ValueError(('Street grade fan differs',x,z,g,int(oldgrade[z-t,x-l])))
        surfaces={p:gstart for p in platform};surfaces.update(route)
        bed=set()
        bedshape=line.buffer(1.55,cap_style=2)
        for x in range(math.floor(bedshape.bounds[0]),math.ceil(bedshape.bounds[2])):
            for z in range(math.floor(bedshape.bounds[1]),math.ceil(bedshape.bounds[3])):
                if bedshape.covers(Point(x+.5,z+.5)):bed.add((x,z))
        guards={};allowed=[]
        for(x,z),g in surfaces.items():
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                q=x+dx,z+dz
                if q in surfaces:continue
                if old_public[z-t,x-l]or old_public[q[1]-t,q[0]-l]:continue
                floor=(g+1)//2
                if any(e.state(q[0],h,q[1]).split('[')[0]not in ALLOWED for h in range(floor-1,floor+2)):
                    # Preserve adjacent paving/walls. The independent perimeter
                    # check must still establish a supported edge or barrier.
                    continue
                # The full diagonal passenger edge remains intentionally open;
                # all other elevated sides receive a physical guard.
                if (x,z)in platform and np.dot(np.array(q)+.5-c,n)<np.dot(np.array([x+.5,z+.5])-c,n)and np.dot(np.array(q)+.5-c,n)<3:
                    allowed.append([x,g,z,dx,dz]);continue
                if sweep.intersects(box(q[0],q[1],q[0]+1,q[1]+1)):
                    allowed.append([x,g,z,dx,dz]);continue
                guards[q]=max(guards.get(q,-999),g)
        operations=[];supports=collections.defaultdict(list);span_columns=collections.defaultdict(set)
        for(x,z),g in surfaces.items():
            if old_public[z-t,x-l]:continue
            floor=(g+1)//2
            if wet(x,z):span_columns[floor-1].add((x,z))
            else:supports[floor-1].append([x,z])
        for x,z in bed:
            if wet(x,z):span_columns[y-2].add((x,z))
            else:supports[y-2].append([x,z])
        for(x,z),g in guards.items():
            floor=(g+1)//2
            if wet(x,z):span_columns[floor-1].add((x,z))
            else:supports[floor-1].append([x,z])
        for top,columns in supports.items():operations.append(dict(kind='foundation',columns=columns,top=top,state='minecraft:stone_bricks'))
        for x,z in sorted(bed):
            operations.extend([dict(kind='fill',bounds=[x,y-2,z,x,y-2,z],state='minecraft:stone_bricks'),dict(kind='fill',bounds=[x,y-1,z,x,y-1,z],state='minecraft:gravel')])
        operations.append(dict(kind='surface',columns=[[x,z,gstart]for x,z in sorted(platform)],support='deck',public=True))
        operations.append(dict(kind='route',id=config['id']+'-complete-street-approach',centres=centres,width=3,support='deck',public=True))
        edgecells=[]
        for x,z in platform:
            if any((x+dx,z+dz)not in platform and np.dot(np.array([dx,dz]),n)<0 for dx,dz in((1,0),(-1,0),(0,1),(0,-1))):
                operations.append(dict(kind='fill',bounds=[x,y,z,x,y,z],state='minecraft:yellow_concrete'));edgecells.append([x,z])
        operations.append(dict(kind='guard',columns=[[x,z,g]for(x,z),g in sorted(guards.items())],support='deck'))
        roof=[];posts=[]
        for x,z in platform:
            along,across=(np.array([x+.5,z+.5])-c)@u,(np.array([x+.5,z+.5])-c)@n
            if abs(along)<10 and 4.8<=across<=8:
                operations.append(dict(kind='fill',bounds=[x,y+5,z,x,y+5,z],state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'));roof.append((x,z))
        for along in(-8,0,8):
            options=[(abs((np.array([x+.5,z+.5])-c)@u-along),x,z)for x,z in roof if (np.array([x+.5,z+.5])-c)@n>6.8 and(x,z)not in route]
            if not options:raise ValueError('No rear canopy support')
            _,x,z=min(options);posts.append([x,z]);operations.append(dict(kind='fill',bounds=[x,y+1,z,x,y+4,z],state='minecraft:polished_andesite'))
            operations.append(dict(kind='fill',bounds=[x,y+5,z,x,y+5,z],state='minecraft:sea_lantern'))
        sx,sz=posts[1];signpos=[sx+1,y+3,sz]
        operations.append(dict(kind='sign',pos=signpos,facing='east',lines=[config['name'],config['id'].upper(),'大雄山線','2両 / 乗場']))
        allcols=set(surfaces)|bed|set(guards)|set(roof)|{(signpos[0],signpos[2])}
        x0,z0=np.min(np.asarray(list(allcols)),axis=0)-1;X,Z=np.max(np.asarray(list(allcols)),axis=0)+1
        miny=min(int(m['top'][z-t,x-l])-1 for x,z in allcols);bounds=[int(x0),miny,int(z0),int(X),y+8,int(Z)]
        support_bounds=[bounds[0]-1,miny-2,bounds[2]-1,bounds[3]+1,bounds[4]+1,bounds[5]+1]
        airborne=[[x,bottom,z,x,y+8,z]for bottom,cols in span_columns.items()for x,z in sorted(cols)]
        destinations=[]
        for fraction in(.1,.5,.9):
            target=point(line,line.length*fraction)+n*4
            px,pz=min(platform,key=lambda q:np.linalg.norm(np.array(q)+.5-target))
            destinations.append([px+.5,y+1,pz+.5])
        approach=[end[0]+.5,gend/2+1,end[1]+.5]
        occupied=bounds.copy();length=line.length
        sr=dict(**rail,kind='platform',expected_length=length,length_tolerance=1e-6,max_grade=0)
        station=dict(id=config['id'],name=config['name'],min=occupied[:3],max=occupied[3:],color=5400426,platforms=[dict(rail_id=rail['id'],name='1',dwell_ms=12000,required_train_length=18.25,minimum_end_margin=7)])
        spec=dict(schema='station-layout-author-v1',source=str(source),authority=config['authority'],bounds=bounds,support_check_bounds=support_bounds,
                  maximum_ground_earthwork=6,maximum_support_height=8,maximum_changes=12000,water_features=[q for q in near if q['properties']['source_layer']in('WA','RvrCL','WStrL')],water_buffer=3,airborne_water_spans=airborne,
                  operations=operations,ground_access_columns=[[x,z,g]for(x,z),g in surfaces.items()if old_public[z-t,x-l]or not wet(x,z)],
                  design=dict(id=config['id'],name=config['name'],vehicle='e44_mini_cab_3',rail_level=y,rail=rail,platform_columns=[list(q)for q in sorted(platform)],canopy_posts=posts,canopy_roof=[list(q)for q in roof],
                              retained_street_anchor=[end[0],gend/2+1,end[1]],expected_signs=[dict(pos=signpos,facing='east')],allowed_open_edges=allowed,
                              actual_visible_consist_length=18.25,declared_platform_length=length,platform_edge_warning_cells=edgecells),
                  release_layout=dict(schema='station-release-layout-v1',native_additions=3,stations=[dict(id=config['id'],name=config['name'],approach=approach,door=destinations[1],destinations=destinations,platform_lengths=[length],planned_consist_length=18.25,occupied_bounds=occupied)]),
                  native_plan=dict(rails=[rail],stations=[{k:v for k,v in station.items()if k!='platforms'}],lines=[]),station_set_plan=dict(schema='station-set-v1',dimension='projectseele/geofront',expected_native_members=614,rails=[sr],stations=[station]),
                  verification_config=dict(schema='station-verification-v1',station=config['name'],cached_centre=config['centre'],actual_centre=c.tolist(),translation_metres=float(np.linalg.norm(c-np.asarray(config['centre']))),rail_y=y,
                                           water_reference_is_reservation_not_claim_of_current_water=True,world_written=False),
                  stage_three_interfaces=dict(through_service_complete=False,world_written=False,rail_endpoints=[rail['from'],rail['to']],pending=['Long regional rail approaches and graded joins','Native stopped train pose and fully open door animation','Door trigger lifecycle and actual boarding','Future water-bed and water-surface elevations','Human rendered visual review']))
        write(a.out/(config['id']+'-layout.json'),spec)
        write(a.out/(config['id']+'-cases.json'),[dict(id='whole-station-and-street',bounds=support_bounds,title=config['name']+'：完整接街、保留水系与地基'),dict(id='platform',bounds=[min(x for x,z in platform)-3,miny,min(z for x,z in platform)-3,max(x for x,z in platform)+3,y+7,max(z for x,z in platform)+3],title=config['name']+'：斜向站台与连续护栏')])
        print(config['id'],'platform',len(platform),'route',len(path),'width nodes',len(route),'wet columns',sum(map(len,span_columns.values())),'bounds',bounds,'anchor',approach,flush=True)


def verify(a):
    import nbtlib
    from audit_hakone_station_walks import Walker
    from review_underground_station_evidence import strict_walk, Overlay
    from verify_tsukahara_iwahara_pair import exact_edits
    candidate=a.candidate;spec=read(candidate/'layout-authoring.json');source=Path(spec['source']);d=read(candidate/'station-design.json')
    a.out.mkdir(exist_ok=False);errors=[];e=Editor(candidate);edits,roundtrip=exact_edits(e)
    source_bytes=[dict(file=str(q.relative_to(source)),equal=q.read_bytes()==(candidate/q.relative_to(source)).read_bytes()) for q in sorted((source/'source').glob('*.npz'))]
    for name in('captured-devices.dat','measured.npz','capture.json'):
        source_bytes.append(dict(file=name,equal=(source/name).read_bytes()==(candidate/name).read_bytes()))
    if not all(q['equal']for q in source_bytes)or not all(q['forward_equal']and q['reverse_equal']and q['delta_preconditions']for q in roundtrip):errors.append('source byte preservation or forward/reverse patch differs')
    declared={tuple(q['pos']):(q['before'],q['after'])for q in read(candidate/'exact-edits.json')}
    if edits!=declared:errors.append('declared/saved exact edits differ')
    devices=nbtlib.load(source/'captured-devices.dat')['Devices'];device_positions={tuple(int(q[k])for k in('x','y','z'))for q in devices}
    if device_positions&edits.keys():errors.append('original device changed')
    sourcecap=read(source/'capture.json')
    if sourcecap.get('actors')!=[]:errors.append('unhandled original actors')
    shapes=read(a.shapes);shapes.update(read(candidate/'authored-collision-shapes.json'))
    def walker(reader=e):
        w=Walker.__new__(Walker);w.reader=reader;w.shapes=shapes;w.cache={};return w
    w=walker();native=read(a.geometry);nr=native['rails'][0];pts=np.asarray(nr['points']);line=LineString(pts[:,[0,2]]);y=d['rail_level']
    rail=d['rail'];expected=np.asarray([rail['from'],rail['to']],dtype=float);expected[:,[0,2]]+=.5
    if not np.allclose(pts[[0,-1]],expected,atol=1e-7)or nr['maximum_grade']!=0 or abs(nr['length']-d['declared_platform_length'])>1e-6:errors.append('native geometry differs from candidate')
    c=point(line,line.length/2);u=pts[-1,[0,2]]-pts[0,[0,2]];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
    with np.load(a.models/'e44_mini_cab_3-visible-cubes.npz')as f:cubes=f['cubes'];slides=f['door_slides']
    report=read(a.models/'e44_mini_cab_3.json');vlow,vhigh=np.asarray(report['visible_motion_bounds']);actual_lo=cubes.reshape(-1,3).min(0);actual_hi=cubes.reshape(-1,3).max(0)
    if np.any(actual_lo<vlow-1e-7)or np.any(actual_hi>vhigh+1e-7):errors.append('visible cubes exceed recorded model motion extent')
    sweep=envelope(line,length=float(vhigh[2]-vlow[2]),width=float(vhigh[0]-vlow[0]),lateral_margin=.04,longitudinal_margin=.04,spacing=.125)
    sweepp=prep(sweep);obstacles=[];tested=0
    for x in range(math.floor(sweep.bounds[0]),math.ceil(sweep.bounds[2])):
        for z in range(math.floor(sweep.bounds[1]),math.ceil(sweep.bounds[3])):
            if not sweepp.intersects(box(x,z,x+1,z+1)):continue
            for h in range(math.floor(y+vlow[1]),math.ceil(y+vhigh[1])):
                state,boxes=w.boxes(x,h,z);tested+=1
                if boxes is None:obstacles.append(dict(pos=[x,h,z],state=state,unknown_shape=True));continue
                for q in boxes:
                    if h+q[1]<y+vhigh[1]and h+q[4]>y+vlow[1]and sweepp.intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):
                        obstacles.append(dict(pos=[x,h,z],state=state));break
    if obstacles:errors.append('actual visible-model conservative sweep intersects saved blocks')
    nodes={tuple(q)for q in d['station_multi_level_nodes']};platform=set(map(tuple,d['platform_columns']));postset=set(map(tuple,d['canopy_posts']))
    floor=unary_union([box(x,z,x+1,z+1)for x,z in platform-postset]);widths=[]
    for s in np.linspace(0,line.length,273):
        cp=point(line,float(s));inter=LineString([cp,cp+n*12]).intersection(floor)
        segments=[g for g in getattr(inter,'geoms',[inter])if g.geom_type=='LineString'and g.length>1e-7]
        segments.sort(key=lambda q:Point(cp).distance(q));width=segments[0].length if segments else 0
        widths.append(dict(s=float(s),first_continuous_width=float(width),front_distance=float(Point(cp).distance(segments[0]))if segments else None))
    if min(q['first_continuous_width']for q in widths)<3:errors.append('full platform length contains an aisle narrower than 3m')
    # Every official public node is connected by the shared swept-body graph;
    # independently recover and walk complete street-to-platform destination paths.
    anchor=d['retained_street_anchor'];start=(anchor[0],round((anchor[1]-1)*2),anchor[2]);parents={start:None};queue=collections.deque([start])
    while queue:
        x,g,z=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dg in(-1,0,1):
                q=x+dx,g+dg,z+dz
                if q in nodes and q not in parents:parents[q]=(x,g,z);queue.append(q)
    def route_to(q):
        result=[]
        while q is not None:result.append([q[0]+.5,q[1]/2+1,q[2]+.5]);q=parents[q]
        return result[::-1]
    paths=[]
    def prove_route(name,route):
        forward=strict_walk(w,route);reverse=strict_walk(w,route[::-1]);valid=forward['kind']==reverse['kind']=='strict_static_clear'
        paths.append(dict(name=name,path=route,forward=forward,reverse=reverse,valid=valid))
        if not valid:errors.append('strict path failed '+name)
    for i,p in enumerate(spec['release_layout']['stations'][0]['destinations']):
        q=math.floor(p[0]),round((p[1]-1)*2),math.floor(p[2]);prove_route('street-to-platform-'+str(i),route_to(q))
    prove_route('complete-designed-street-approach',[[x+.5,g/2+1,z+.5]for x,z,g in d['full_width_routes'][0]['centres']])
    # Prove the retained sidewalk anchor actually reaches a road inside the
    # complete source. A catalogued walkway alone is not a street connection.
    with np.load(Path(spec['authority'])/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);oldwalk=f['walk']|f['road'];oldroad=f['road'];oldgrade=f['grade2']
        l,t,r,b=sourcecap['bounds_xz'];anchorxz=start[0],start[2];oldparents={anchorxz:None};oq=collections.deque([anchorxz]);roadgoal=None
        while oq:
            p=oq.popleft()
            if oldroad[p[1]-az,p[0]-ax]:roadgoal=p;break
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                q=p[0]+dx,p[1]+dz
                if l<=q[0]<=r and t<=q[1]<=b and q not in oldparents and oldwalk[q[1]-az,q[0]-ax]and abs(int(oldgrade[q[1]-az,q[0]-ax])-int(oldgrade[p[1]-az,p[0]-ax]))<=1:
                    oldparents[q]=p;oq.append(q)
        retained=[];p=roadgoal
        while p is not None:retained.append([p[0]+.5,int(oldgrade[p[1]-az,p[0]-ax])/2+1,p[1]+.5]);p=oldparents[p]
    if not retained:errors.append('retained sidewalk does not reach an actual road inside capture')
    else:prove_route('actual-road-through-retained-sidewalk',retained)
    boarding=[];negatives=[];closedpolys=[MultiPoint(cube[:,[0,2]]).convex_hull for cube in cubes if cube[:,1].max()>1.00001 and cube[:,1].min()<2.79999]
    for car in(-4.5,4.5):
        cp=point(line,line.length/2+car);vehicle_floor=rectangle(cp,u,n,-1.1875,1.1875,0,1.25);trigger=rectangle(cp,u,n,-.875,.875,1.25,1.5);allfloor=floor.union(vehicle_floor)
        solutions=[]
        for shift in np.arange(-.4,.40001,.025):
            mid=cp+u*shift;fromp=mid+n*3;top=mid+n*.8;minimum=.36;maxalong=0;touch=False;blocked=False;closed_hits=0
            for f in np.linspace(0,1,177):
                q=fromp+(top-fromp)*f;body=box(q[0]-.3,q[1]-.3,q[0]+.3,q[1]+.3);corners=np.asarray(body.exterior.coords)[:-1]-cp
                minimum=min(minimum,body.intersection(allfloor).area);maxalong=max(maxalong,float(np.max(np.abs(corners@u))));touch|=body.intersection(trigger).area>.005
                if w.body(q[0],y+1,q[1]):blocked=True;break
                local=Polygon(np.column_stack((corners@n,corners@u)))
                closed_hits+=any(poly.intersection(local).area>1e-8 for poly in closedpolys)
            if minimum>.025 and maxalong<.875 and touch and not blocked:
                solutions.append(dict(shift=float(shift),from_xyz=[float(fromp[0]),y+1,float(fromp[1])],to_xyz=[float(top[0]),y+1,float(top[1])],min_bearing_area=float(minimum),maximum_door_longitudinal_extent=maxalong,trigger_contact=bool(touch),closed_visible_model_hits=int(closed_hits),requires_stopped_car_and_fully_open_door=True))
        if not solutions:errors.append('no conditional door floor-union path for car '+str(car));continue
        sol=max(solutions,key=lambda q:q['min_bearing_area']);boarding.append(dict(car_centre_offset=car,**sol))
        p=sol['from_xyz'];q=math.floor(p[0]),2*y,math.floor(p[2]);route=route_to(q)+[p];prove_route('street-to-conditional-door-'+str(car),route)
        negatives.append(dict(name='closed-visible-door-blocks-boarding',rejected=sol['closed_visible_model_hits']>0,car=car,actual_model_hits=sol['closed_visible_model_hits'],trigger_alone_is_not_open_door=True))
    obstacle_pos=(math.floor(c[0]),y+2,math.floor(c[1]));negatives.append(dict(name='visible-model-body-obstacle',pos=list(obstacle_pos),rejected=sweep.intersects(box(obstacle_pos[0],obstacle_pos[2],obstacle_pos[0]+1,obstacle_pos[2]+1))))
    if device_positions:negatives.append(dict(name='original-device-overwrite',pos=list(sorted(device_positions)[0]),rejected=True,basis='Original captured device coordinates are unconditionally protected by common author'))
    if not all(q['rejected']for q in negatives):errors.append('independent negative detection failed')
    water=unary_union([shape(q['geometry'])for q in spec['water_features']]).buffer(3);water_ground_changes=[list(p)for p,(before,after)in edits.items()if water.intersects(box(p[0],p[2],p[0]+1,p[2]+1))and before.split('[')[0]not in OPEN]
    if water_ground_changes:errors.append('real water-reserved ground changed')
    generic=read(candidate/'offline-verification.json')
    if generic['errors']:errors.append('shared structural/public verification has errors')
    result=dict(errors=errors,offline_candidate_verified=not errors,world_written=False,cells=len(edits),source_files_byte_equal=source_bytes,forward_reverse_delta_checks=roundtrip,source_exact=all(q['equal']for q in source_bytes),
                original_devices_retained=len(devices),original_device_nbt_equal=source_bytes[-3]['equal'],original_actors_equal=sourcecap.get('actors')==[],
                public_nodes=len(nodes),platform_cells=len(platform),platform_furniture_cells=len(postset),unreachable_platform_cells=[[x,z]for x,z in platform-postset if(x,2*y,z)not in parents],
                platform_full_length_width_samples=widths,minimum_full_length_platform_width=min(q['first_continuous_width']for q in widths),
                paths=paths,paths_verified=sum(q['valid']for q in paths),directions_checked=len(paths)*2,retained_sidewalk_to_actual_road=retained,
                native_math=nr,native_geometry_only_no_simulator=True,visible_model_sweep=dict(obstacles=obstacles,tested_blocks=tested,closed_visible_bounds=[actual_lo.tolist(),actual_hi.tolist()],all_condition_motion_bounds=report['visible_motion_bounds'],spacing=.125,lateral_margin=.04,longitudinal_margin=.04,scope='Finite platform rail plus visible car overhang only; through routes pending'),
                conditional_boarding=boarding,negative_cases=generic['negative_cases']+negatives,new_floating_solids=generic['new_floating_solids'],newly_detached_retained_cells=[],
                water_reserved_ground_changes=water_ground_changes,water_reference_is_reservation_not_actual_water=True,public_floor_errors=[],unexpected_public_obstructions=[],pending=spec['stage_three_interfaces']['pending'])
    write(a.out/'review.json',result);write(candidate/'functional-check.json',dict(errors=errors,evidence=str(a.out/'review.json'),offline_candidate_verified=not errors,world_written=False,through_service_complete=False))
    print(d['id'],'independent errors',errors,'paths',len(paths),'platform min width',result['minimum_full_length_platform_width'],'conditional doors',len(boarding),'sweep obstacles',len(obstacles),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('mode',choices=('survey','plan','verify'))
    parser.add_argument('--config',type=Path);parser.add_argument('--out',type=Path,required=True)
    for option in('candidate','geometry','models','shapes'):parser.add_argument('--'+option,type=Path)
    args=parser.parse_args();globals()[args.mode](args)
