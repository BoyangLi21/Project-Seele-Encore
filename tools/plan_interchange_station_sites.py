"""Configuration-driven multigroup interchange authoring from frozen captures.

Never opens saves, native registries, Simulator, game windows or network sources.
"""
import argparse, collections, copy, gzip, json, math, shutil
from pathlib import Path
import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPoint, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep
from author_hakone_lakefront import Editor
from author_station_layout import read,write,open_state,collision,route_columns
from author_kamonomiya_station import ALLOWED,OPEN
from check_kamonomiya_visible_models import clipped_half_width
from map_pipeline.vehicle_envelopes import point,rectangle
from map_pipeline.mtr_vehicle_pose import pose,envelope

def context(c):
    source=Path(c['source']);cap=read(source/'capture.json');e=Editor(source)
    with np.load(source/'measured.npz')as f:m={k:f[k].copy()for k in f.files}
    l,t,r,b=cap['bounds_xz']
    with np.load(Path(c['authority'])/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);old=(f['walk']|f['road'])[t-az:b-az+1,l-ax:r-ax+1].copy();grade=f['grade2'][t-az:b-az+1,l-ax:r-ax+1].copy();road=f['road'][t-az:b-az+1,l-ax:r-ax+1].copy()
    features=json.loads(gzip.decompress(Path(c['features']).read_bytes()))['features']
    near=[dict(feature_index=i,**q)for i,q in enumerate(features)if q['properties'].get('source_layer')in('RailCL','WA','RvrCL','WStrL','BldA')and shape(q['geometry']).intersects(box(l,t,r+1,b+1))]
    waterfeatures=[q for q in near if q['properties']['source_layer']in('WA','RvrCL','WStrL')]
    return source,cap,e,m,old,grade,road,near,waterfeatures

def survey(a):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(exist_ok=False);out=[]
    for c in read(a.config)['sites']:
        source,cap,e,m,old,grade,road,near,wf=context(c);l,t,r,b=cap['bounds_xz']
        fig,ax=plt.subplots(figsize=(16,15));ax.imshow(m['top'],extent=(l,r+1,b+1,t),cmap='terrain')
        zz,xx=np.where(old);ax.scatter(xx+l+.5,zz+t+.5,s=5,c='black',label='Retained streets')
        zz,xx=np.where(m['protected']);ax.scatter(xx+l+.5,zz+t+.5,s=3,c='magenta',label='Protected source columns')
        station=[]
        for q in near:
            g=shape(q['geometry']);p=q['properties'];layer=p['source_layer']
            if layer=='RailCL':
                for line in getattr(g,'geoms',[g]):
                    xx,zz=line.xy;ax.plot(xx,zz,c='red'if p['vt_rtcode']=='JR'else'blue',lw=2 if p['vt_sngldbl']=='駅部分'else .7)
                if p['vt_sngldbl']=='駅部分' and g.distance(Point(c['centre']))<70:
                    station.append(q);cp=g.interpolate(.5,normalized=True);ax.text(cp.x,cp.y,str(q['feature_index']),size=8,bbox=dict(fc='white',alpha=.7))
            elif layer in('WA','RvrCL','WStrL'):
                for poly in getattr(g.buffer(3),'geoms',[g.buffer(3)]):
                    xx,zz=poly.exterior.xy;ax.fill(xx,zz,color='cyan',alpha=.35)
        for group in c.get('groups',[]):
            for rail in group['rails']:
                p=np.asarray([rail['from'],rail['to']]);ax.plot(p[:,0]+.5,p[:,2]+.5,c='lime',lw=2)
        ax.set(xlim=(l,r+1),ylim=(b+1,t),title=c['id']+' frozen source / geographic corridors',xlabel='World X',ylabel='World Z');ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(a.out/'survey.png',dpi=140);plt.close(fig)
        targets=[]
        for iz,ix in np.argwhere(old):
            x,z=int(ix+l),int(iz+t);g=int(grade[iz,ix]);h=(g+1)//2
            if all(open_state(e.state(x,y,z))for y in range(h+1,h+4)):
                targets.append(dict(x=x,z=z,grade2=g,distance=round(math.dist((x+.5,z+.5),c['centre']),3)))
        targets.sort(key=lambda q:q['distance'])
        out.append(dict(id=c['id'],station_corridors=station,near_geography=near,retained_street_targets=targets,source=str(source),world_written=False))
    write(a.out/'survey.json',out)

def profile(waypoints,spacing=1):
    rows=[]
    for a,b in zip(waypoints,waypoints[1:]):
        x,z,g=a;X,Z,G=b
        if x!=X and z!=Z:raise ValueError('Cardinal stair flights required')
        length=abs(X-x)+abs(Z-z);need=abs(G-g);slots=list(range(2,length-1,spacing))
        if need>len(slots):raise ValueError(('Insufficient stair length',a,b))
        changes=set(slots[:need])if need else set();dx=(X>x)-(X<x);dz=(Z>z)-(Z<z);grade=g
        for i in range(length+1):
            if i in changes:grade+=1 if G>g else -1
            row=[x+dx*i,z+dz*i,grade]
            if not rows or rows[-1]!=row:rows.append(row)
    route_columns(rows,3);return rows

def cells(poly,intersect=False):
    test=prep(poly)
    for x in range(math.floor(poly.bounds[0]),math.ceil(poly.bounds[2])):
        for z in range(math.floor(poly.bounds[1]),math.ceil(poly.bounds[3])):
            if test.intersects(box(x,z,x+1,z+1))if intersect else test.covers(Point(x+.5,z+.5)):yield x,z

def model_bands(g):
    bands={};lowwidth=0;extent=0
    for ident in g['models']:
        root=Path(g['model_source']);report=read(root/(ident+'.json'));extent=max(extent,max(abs(report['visible_motion_bounds'][j][2])for j in(0,1))+.04)
        with np.load(root/(ident+'-visible-cubes.npz'))as f:
            for h in range(math.floor(report['visible_motion_bounds'][0][1]-.03),math.ceil(report['visible_motion_bounds'][1][1]+.03)):
                widths=[q for v,s in zip(f['cubes'],f['door_slides'])if(q:=clipped_half_width(v,s,h-.03,h+1+.03))is not None]
                if widths:bands[h]=max(bands.get(h,0),max(widths)+.03)
            widths=[q for v,s in zip(f['cubes'],f['door_slides'])if(q:=clipped_half_width(v,s,-.03,.53))is not None]
            if widths:lowwidth=max(lowwidth,max(widths)+.03)
    return bands,lowwidth,extent

def departure_reservation(line,terminal_south=False,length=60):
    """Keep station structures outside finite future departure corridors."""
    ps=np.asarray(line.coords);rows=ps.tolist()
    if not terminal_south:
        u=ps[0]-ps[1];u/=np.linalg.norm(u);rows.insert(0,(ps[0]+u*length).tolist())
    u=ps[-1]-ps[-2];u/=np.linalg.norm(u);rows.append((ps[-1]+u*length).tolist())
    return LineString(rows)

def plan(a):
    c=read(a.config)['sites'][0];source,cap,e,m,old,grade,road,near,wf=context(c);l,t,r,b=cap['bounds_xz'];y=c['rail_y']
    a.out.mkdir(exist_ok=False);native=read(c['geometry']);geo={q['input_rail_id']:q for q in native['rails']};water=unary_union([shape(q['geometry'])for q in wf]).buffer(3)
    wetcache={}
    def wet(p):
        if p not in wetcache:wetcache[p]=water.intersects(box(p[0],p[1],p[0]+1,p[1]+1))
        return wetcache[p]
    operations=[];nodes=set();allplatform=set();groups=[];deck=set();trackcols=set();sweeps=[];allrails=[]
    for g in c['groups']:
        lines=[LineString(np.asarray(geo[r['id']]['points'])[:,[0,2]])for r in g['rails']];u=np.asarray(lines[0].coords[-1])-lines[0].coords[0];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]]);mid=np.mean([point(q,q.length/2)for q in lines],axis=0);bands,lw,extent=model_bands(g)
        reserved=[departure_reservation(q,g['id']=='branch_terminal',c.get('departure_reservation_length',60))for q in lines]
        fullsweep=unary_union([envelope(q,length=2*extent,width=2*bands[0],bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125)for q in reserved]);lowsweep=unary_union([envelope(q,length=2*extent,width=2*lw,bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125)for q in reserved])
        halfspace=np.linalg.norm(point(lines[0],lines[0].length/2)-point(lines[-1],lines[-1].length/2))/2
        across=(-halfspace,halfspace)if len(lines)==2 else(0,g.get('platform_outer_offset',14))
        region=rectangle(mid,u,n,-lines[0].length/2-12,lines[0].length/2+12,*across)
        full={p for p in cells(region)if not fullsweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1))};lip={p for p in cells(region)if p not in full and not lowsweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1))}
        platform=full|lip
        remaining=set(platform);components=[]
        while remaining:
            seed=remaining.pop();queue=collections.deque([seed]);comp={seed}
            while queue:
                x,z=queue.popleft()
                for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                    q=x+dx,z+dz
                    if q in remaining:remaining.remove(q);comp.add(q);queue.append(q)
            components.append(comp)
        platform=max(components,key=len);full&=platform;lip&=platform
        allplatform|=platform;nodes.update((x,z,2*y)for x,z in full);nodes.update((x,z,2*y-1)for x,z in lip);deck.update(cells(region));maxsweep=unary_union([envelope(q,length=2*extent,width=2*max(bands.values()),bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=.1,longitudinal_margin=0,spacing=.125)for q in reserved]);sweeps.append(maxsweep);trackcols.update(cells(maxsweep,True))
        for rail,line in zip(g['rails'],lines):
            allrails.append(rail)
            bed=set(cells(line.buffer(1.55,cap_style=2)));deck|=bed;trackcols.update(cells(line.buffer(2.5,cap_style=2)))
            for x,z in sorted(bed):operations.append(dict(kind='fill',bounds=[x,y-1,z,x,y-1,z],state='minecraft:gravel'))
            for h,width in bands.items():
                sweep=envelope(line,length=2*extent,width=2*width,bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125)
                for x,z in cells(sweep,True):operations.append(dict(kind='fill',bounds=[x,y+h,z,x,y+h,z],state='minecraft:air'))
        groups.append(dict(**g,platform_columns=[list(p)for p in sorted(platform)],full_platform_columns=[list(p)for p in sorted(full)],boarding_lip_columns=[list(p)for p in sorted(lip)],axis_u=u.tolist(),axis_n=n.tolist(),midpoint=mid.tolist(),full_model_bands=bands))
    routes=[]
    for q in c['routes']:
        centers=profile(q['waypoints'],q.get('spacing',1));cols=route_columns(centers,q.get('width',3));routes.append((q,centers,cols));nodes.update((x,z,g)for(x,z),g in cols.items())
    # Delete declarations covered by the actual upper stair floor/body volume;
    # physical lower paving stays, but an obstructed under-stair cell is not public.
    bycol=collections.defaultdict(set)
    for x,z,g in nodes:bycol[x,z].add(g)
    nodes={q for q in nodes if not any(0<G-q[2]<7 for G in bycol[q[:2]])}
    bycol=collections.defaultdict(set)
    for x,z,g in nodes:bycol[x,z].add(g)
    guards={};allowed=[];allsweep=unary_union(sweeps)
    for x,z,g in nodes:
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            p=x+dx,z+dz
            if any(abs(v-g)<=1 for v in bycol[p]):continue
            if old[p[1]-t,p[0]-l]and abs(int(grade[p[1]-t,p[0]-l])-g)<=1:continue
            if(x,z)in allplatform and g in(2*y,2*y-1)and allsweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1)):
                allowed.append([x,g,z,dx,dz]);continue
            guards[p[0],p[1],g]=g
    # One solid sidewall per contiguous grade cluster. Recording every half-step
    # guard at the same X/Z would let the upper base overwrite the lower glass.
    guardcolumns=collections.defaultdict(list)
    for x,z,g in guards:guardcolumns[x,z].append(g)
    merged={};guardbases=[]
    for (x,z),grades in guardcolumns.items():
        clusters=[]
        for g in sorted(set(grades)):
            if clusters and g-clusters[-1][-1]<=3:clusters[-1].append(g)
            else:clusters.append([g])
        for cluster in clusters:
            g=max(cluster);bottom=(min(cluster)+1)//2-1;top=(g+1)//2;merged[x,z,g]=g
            guardbases.append(dict(kind='fill',bounds=[x,bottom,z,x,top,z],state='minecraft:stone_bricks'))
    guards=merged
    base=[];piers=[];beam=set(deck)
    beam.update((x,z)for x,z,g in guards if g in(2*y,2*y-1))
    for x,z in sorted(beam):base.append(dict(kind='fill',bounds=[x,y-2,z,x,y-2,z],state='minecraft:stone_bricks'))
    # Repeated pier bents within the measured dry, unoccupied platform strip.
    for g in groups:
        u=np.asarray(g['axis_u']);mid=np.asarray(g['midpoint']);line=LineString(np.asarray(geo[g['rails'][0]['id']]['points'])[:,[0,2]])
        for s in np.arange(-line.length/2-6,line.length/2+7,12):
            cp=mid+u*s
            if len(g['rails'])==1:cp+=np.asarray(g['axis_n'])*7
            choices=sorted(g['full_platform_columns'],key=lambda p:math.dist(np.asarray(p)+.5,cp))
            selected=None
            for p in choices[:1000]:
                x,z=p;ps={(x+dx,z+dz)for dx in(0,1)for dz in(0,1)}
                if math.dist(np.asarray(p)+.5,cp)>18:break
                if all(q in beam and not wet(q)and not old[q[1]-t,q[0]-l]and int(m['top'][q[1]-t,q[0]-l])<=y-3 and all(e.state(q[0],h,q[1]).split('[')[0]in ALLOWED for h in range(int(m['top'][q[1]-t,q[0]-l])-1,y-1))for q in ps):selected=ps;break
            if selected is None:raise ValueError(('No protected-free pier location',g['id'],s))
            piers.extend(sorted(selected));base.append(dict(kind='foundation',columns=[list(p)for p in sorted(selected)],top=y-2,state='minecraft:stone_bricks'))
    # Stair and concourse piers use dry, non-rail columns and avoid all lower
    # declared public floors. Continuous deck undersides connect intermediate spans.
    for item,centers,cols in routes:
        for i,(x,z,g)in enumerate(centers):
            if i%10 and i not in(0,len(centers)-1):continue
            if old[z-t,x-l]or wet((x,z))or(x,z)in trackcols or any(v<g for v in bycol[x,z]):continue
            floor=(g+1)//2;terrain=int(m['top'][z-t,x-l])
            if floor-1>=terrain and floor-1-terrain<=c['maximum_support_height']:
                base.append(dict(kind='foundation',columns=[[x,z]],top=floor-1,state='minecraft:stone_bricks'));piers.append((x,z))
    operations=base+operations
    for g in groups:
        operations.append(dict(kind='surface',columns=[[x,z,2*y]for x,z in g['full_platform_columns']],support='deck',public=True))
        operations.append(dict(kind='surface',columns=[[x,z,2*y-1]for x,z in g['boarding_lip_columns']],support='deck',public=True))
        for x,z in g['boarding_lip_columns']:operations.append(dict(kind='fill',bounds=[x,y,z,x,y,z],state='minecraft:cut_sandstone_slab[type=bottom,waterlogged=false]'))
    for item,centers,cols in routes:operations.append(dict(kind='route',id=item['id'],centres=centers,width=item.get('width',3),support='deck',public=True))
    operations+=guardbases
    explicit=[]
    for x,z,g in sorted(guards):
        gy=(g+1)//2+1
        if any(q['kind']=='fill'and q['bounds'][0]<=x<=q['bounds'][3]and q['bounds'][1]<=gy<=q['bounds'][4]and q['bounds'][2]<=z<=q['bounds'][5]for q in c.get('fixtures',[])):continue
        explicit.append([x,z,g])
    operations.append(dict(kind='guard',columns=explicit,support='deck'))
    # Roofed concourse, platform canopies and small group identity signs.
    signs=[];posts=[]
    for q in c.get('fixtures',[]):
        if q['kind']=='fill'and q['bounds'][0]==q['bounds'][3]and q['bounds'][2]==q['bounds'][5]:
            px,lo,pz,_,hi,_=q['bounds']
            if any((px,pz)in cols and lo<cols[px,pz]/2+2.8 and hi+1>cols[px,pz]/2+1 for _,_,cols in routes):continue
        if q['kind']=='sign':signs.append({k:q[k]for k in('pos','facing')})
        operations.append(q)
    bounds=c['edit_bounds'];anchor=c['retained_street_anchor'];dest=[]
    for g in groups:
        for rail in g['rails']:
            line=LineString(np.asarray(geo[rail['id']]['points'])[:,[0,2]])
            for f in(.05,.5,.95):
                cp=point(line,line.length*f);target=cp+(np.asarray(g['midpoint'])-cp)*0
                p=min(g['full_platform_columns'],key=lambda p:math.dist(np.asarray(p)+.5,cp))
                dest.append([p[0]+.5,y+1,p[1]+.5])
    station=read(c['native_probe'])['stations'][0];station['min']=bounds[:3];station['max']=bounds[3:];stationplan=read(c['native_probe']);stationplan['stations']=[station];stationplan['expected_native_members']=c['expected_native_members']
    airborne=[bounds];ground=[[x,z,g]for x,z,g in nodes if old[z-t,x-l]and g==int(grade[z-t,x-l])]
    spec=dict(schema='station-layout-author-v1',source=str(source),authority=c['authority'],bounds=bounds,support_check_bounds=c['support_check_bounds'],maximum_ground_earthwork=8,maximum_support_height=c['maximum_support_height'],maximum_changes=100000,water_features=wf,water_buffer=3,airborne_water_spans=airborne,retained_public_overpasses=[bounds],operations=operations,ground_access_columns=ground,
        design=dict(id=c['id'],name=c['name'],rail_level=y,rails=allrails,groups=groups,platform_rails=[dict(rail_id=r['id'],platform_name=str(i+1),native_rail=r,group=g['id'],consist_length=g['consist_length'])for i,(g,r)in enumerate((g,r)for g in groups for r in g['rails'])],platform_columns=[list(p)for p in sorted(allplatform)],canopy_posts=posts,bridge_pier_columns=[list(p)for p in sorted(set(piers))],retained_street_anchor=anchor,second_street_anchor=c['second_street_anchor'],expected_signs=signs,allowed_open_edges=allowed,site_selection=c['site_selection']),
        release_layout=dict(schema='station-release-layout-v1',native_additions=15,stations=[dict(id=c['id'],name=c['name'],approach=[anchor[0]+.5,anchor[1],anchor[2]+.5],door=dest[0],destinations=dest+[[c['second_street_anchor'][0]+.5,c['second_street_anchor'][1],c['second_street_anchor'][2]+.5]],platform_lengths=[geo[r['id']]['length']for r in allrails],planned_consist_length=18.25,platform_required_consist_lengths=[p['required_train_length']for p in station['platforms']],occupied_bounds=bounds)]),
        native_plan=dict(rails=allrails,stations=[{k:v for k,v in station.items()if k!='platforms'}],lines=[]),station_set_plan=stationplan,verification_config=dict(schema='station-verification-v1',station=c['name'],cached_centre=c['centre'],site_selection=c['site_selection'],world_written=False),
        stage_three_interfaces=dict(through_service_complete=False,world_written=False,rail_endpoints=[[r['from'],r['to']]for r in allrails],groups=[dict(id=g['id'],cached_station_feature=g['cached_station_feature'],ports=[dict(rail_id=r['id'],south=r['from'],north=r['to'],south_angle=r['from_angle'],north_angle=r['to_angle'])for r in g['rails']],terminal=g['id']=='branch_terminal')for g in groups],pending=['All running lines and curve/grade approach integration','Stopped trains, door callbacks and actual boarding','External tunnels and bridges','Future waterways terrain implementation']))
    write(a.out/(c['id']+'-layout.json'),spec);write(a.out/'site-selection.json',c);write(a.out/'native-math-samples.json',native)
    print('Interchange planned',len(allrails),'rails',len(allplatform),'platform cells',len(nodes),'public nodes',len(operations),'operations',flush=True)

def verify(a):
    import nbtlib
    from audit_hakone_station_walks import Walker
    from review_underground_station_evidence import strict_walk
    from verify_tsukahara_iwahara_pair import exact_edits
    c=read(a.config)['sites'][0];candidate=a.candidate;spec=read(candidate/'layout-authoring.json');d=read(candidate/'station-design.json');source=Path(spec['source']);a.out.mkdir(exist_ok=False)
    e=Editor(candidate);edits,roundtrip=exact_edits(e);errors=[];generic=read(candidate/'offline-verification.json');native=read(c['geometry']);geo={q['input_rail_id']:q for q in native['rails']};y=c['rail_y']
    declared={tuple(q['pos']):(q['before'],q['after'])for q in read(candidate/'exact-edits.json')}
    sourcebytes=[dict(file=str(p.relative_to(source)),equal=p.read_bytes()==(candidate/p.relative_to(source)).read_bytes())for p in sorted((source/'source').glob('*.npz'))]
    for name in('capture.json','measured.npz','captured-devices.dat'):sourcebytes.append(dict(file=name,equal=(source/name).read_bytes()==(candidate/name).read_bytes()))
    if edits!=declared or not all(q['equal']for q in sourcebytes)or not all(q['forward_equal']and q['reverse_equal']and q['delta_preconditions']for q in roundtrip):errors.append('Exact source or forward/inverse patch mismatch')
    devices=nbtlib.load(source/'captured-devices.dat')['Devices'];devpos={tuple(int(q[k])for k in('x','y','z'))for q in devices}
    if devpos&edits.keys():errors.append('Original device changed')
    shapes=read(candidate/'authored-collision-shapes.json');w=Walker.__new__(Walker);w.reader=e;w.shapes=shapes;w.cache={};nodes={tuple(q)for q in d['station_multi_level_nodes']}
    anchor=d['retained_street_anchor'];start=anchor[0],round((anchor[1]-1)*2),anchor[2];parents={start:None};queue=collections.deque([start])
    while queue:
        x,g,z=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dg in(-1,0,1):
                q=x+dx,g+dg,z+dz
                if q in nodes and q not in parents:parents[q]=(x,g,z);queue.append(q)
    def route(q):
        if q not in parents:raise ValueError(('Unreachable destination',q))
        result=[]
        while q is not None:result.append([q[0]+.5,q[1]/2+1,q[2]+.5]);q=parents[q]
        return result[::-1]
    paths=[]
    def prove(name,path):
        f=strict_walk(w,path);r=strict_walk(w,path[::-1]);valid=f['kind']==r['kind']=='strict_static_clear';paths.append(dict(name=name,path=path,forward=f,reverse=r,valid=valid))
        if not valid:errors.append('Strict path failed '+name)
    destinations=spec['release_layout']['stations'][0]['destinations']
    for i,p in enumerate(destinations):prove('street-to-platform-and-second-street-'+str(i),route((math.floor(p[0]),round((p[1]-1)*2),math.floor(p[2]))))
    for q in d['full_width_routes']:prove('complete-profile-'+q['id'],[[x+.5,g/2+1,z+.5]for x,z,g in q['centres']])
    # Explicit pairwise transfers use the measured connected graph and test both
    # directions; no route is interpolated through a railway at platform level.
    groupnodes=[]
    for g in d['groups']:
        p=min((p for p in g['full_platform_columns']if(p[0],2*y,p[1])in nodes),key=lambda p:math.dist(p,g['midpoint']))
        groupnodes.append((g['id'],(p[0],2*y,p[1])))
    for i,(label,p)in enumerate(groupnodes):
        rp=route(p)
        for other,q in groupnodes[i+1:]:
            rq=route(q);k=0
            while k<min(len(rp),len(rq))and rp[k]==rq[k]:k+=1
            prove('transfer-'+label+'-to-'+other,rp[:k-1:-1]+rq[k-1:])
    with np.load(Path(spec['authority'])/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);old=f['walk']|f['road'];road=f['road'];grades=f['grade2'];l,t,R,B=read(source/'capture.json')['bounds_xz']
        for aname,ap in [('west',anchor),('east',d['second_street_anchor'])]:
            p=ap[0],ap[2];op={p:None};oq=collections.deque([p]);goal=None
            while oq:
                p=oq.popleft()
                if road[p[1]-az,p[0]-ax]:goal=p;break
                for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                    q=p[0]+dx,p[1]+dz
                    if l<=q[0]<=R and t<=q[1]<=B and q not in op and old[q[1]-az,q[0]-ax]and abs(int(grades[q[1]-az,q[0]-ax])-int(grades[p[1]-az,p[0]-ax]))<=1:op[q]=p;oq.append(q)
            retained=[];p=goal
            while p is not None:retained.append([p[0]+.5,int(grades[p[1]-az,p[0]-ax])/2+1,p[1]+.5]);p=op[p]
            if retained:prove(aname+'-retained-sidewalk-to-road',retained)
            else:errors.append('No actual road connection at '+aname)
        roadclear=[]
        for p,(before,after)in edits.items():
            if not open_state(after)and road[p[2]-az,p[0]-ax]:
                feet=int(grades[p[2]-az,p[0]-ax])/2+1;roadclear.append(dict(pos=list(p),clearance=p[1]-feet))
        if any(q['clearance']<4.25 for q in roadclear):errors.append('New obstruction within retained roadway vertical clearance')
    widths=[];sweeps=[];boarding=[];negative=[]
    for group in d['groups']:
        platform=set(map(tuple,group['platform_columns']));full=unary_union([box(x,z,x+1,z+1)for x,g,z in nodes if g==2*y and(x,z)in platform]);low=unary_union([box(x,z,x+1,z+1)for x,g,z in nodes if g==2*y-1 and(x,z)in platform]);modelroot=Path(group['model_source']);models={}
        for ident in group['models']:
            report=read(modelroot/(ident+'.json'))
            with np.load(modelroot/(ident+'-visible-cubes.npz'))as f:cubes=f['cubes'].copy();slides=f['door_slides'].copy()
            with np.load(modelroot/(ident+'-closed-cubes.npz'))as f:closed=f['cubes'].copy()
            if not report['all_selected_conditions_enclosed']:errors.append('Incomplete visible model conditions')
            models[ident]=(report,cubes,slides,closed)
        for rail in group['rails']:
            nr=geo[rail['id']];pts=np.asarray(nr['points']);line=LineString(pts[:,[0,2]]);expected=np.asarray([rail['from'],rail['to']],float);expected[:,[0,2]]+=.5
            sweep_line=departure_reservation(line,group['id']=='branch_terminal',c.get('departure_reservation_length',60))
            if not np.allclose(pts[[0,-1]],expected)or nr['maximum_grade']!=0:errors.append('Native geometry mismatch '+rail['id'])
            baseu=np.asarray(group['axis_u']);base_n=np.asarray(group['axis_n']);side=1 if len(group['rails'])==1 or np.dot(np.asarray(group['midpoint'])-point(line,line.length/2),base_n)>0 else -1;n=base_n*side
            for s in np.linspace(0,line.length,math.ceil(line.length*8)+1):
                cp,tu,tn=pose(line,float(s),group['bogie1_position'],group['bogie2_position']);tn=tn if np.dot(tn,n)>0 else -tn;inter=LineString([cp,cp+tn*25]).intersection(full);parts=[q for q in getattr(inter,'geoms',[inter])if q.geom_type=='LineString'and q.length>1e-8];parts.sort(key=lambda q:q.distance(Point(cp)));width=parts[0].length if parts else 0;widths.append(dict(rail=rail['id'],s=float(s),first_continuous_width=float(width)))
            for ident,(report,cubes,slides,closed)in models.items():
                extent=max(abs(report['visible_motion_bounds'][j][2])for j in(0,1))+.03;obstacles=[];tested=0;bands=[];shape_cache={}
                for h in range(math.floor(report['visible_motion_bounds'][0][1]-.03),math.ceil(report['visible_motion_bounds'][1][1]+.03)):
                    vals=[v for cube,slide in zip(cubes,slides)if(v:=clipped_half_width(cube,slide,h-.03,h+1+.03))is not None]
                    if not vals:continue
                    width=max(vals)+.03;bands.append(dict(y=[h,h+1],swept_half_width=width));poly=envelope(sweep_line,length=2*extent,width=2*width,bogie1_position=group['bogie1_position'],bogie2_position=group['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125)
                    for x,z in cells(poly,True):
                        state=e.state(x,y+h,z);tested+=1
                        for q in collision(state):
                            key=h+q[1],h+q[4]
                            if key not in shape_cache:
                                ww=[v for cube,slide in zip(cubes,slides)if(v:=clipped_half_width(cube,slide,key[0]-.03,key[1]+.03))is not None];shape_cache[key]=prep(envelope(sweep_line,length=2*extent,width=2*(max(ww)+.03),bogie1_position=group['bogie1_position'],bogie2_position=group['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125))if ww else None
                            p=shape_cache[key]
                            if p and p.intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):obstacles.append(dict(pos=[x,y+h,z],state=state,collision_box=q));break
                sweeps.append(dict(group=group['id'],rail=rail['id'],model=ident,bands=bands,tested_blocks=tested,obstacles=obstacles,actual_partial_block_height_clipping=True,station_native_curve_plus_finite_tangent_reservation=True,departure_reservation_length_per_running_end=c.get('departure_reservation_length',60),terminal_south_reserved_only_for_body_overhang=group['id']=='branch_terminal',external_native_curve_grade_and_service_complete=False))
                if obstacles:errors.append('Visible full model sweep '+rail['id']+'/'+ident)
            offsets=(-4.5,4.5)if len(group['models'])==1 else(-50,-30,-10,10,30,50)
            for direction in(-1,1):
                for ci,offset in enumerate(offsets):
                    ident=group['models'][0]if len(group['models'])==1 or ci==len(offsets)-1 else group['models'][2]if ci==0 else group['models'][1];report,cubes,slides,closed=models[ident];carcentre,u,veh_n=pose(line,line.length/2+direction*offset,group['bogie1_position'],group['bogie2_position'],direction=direction);local_side=1 if np.dot(veh_n,base_n*side)>0 else -1;n=veh_n*local_side
                    doors=[q for q in report['parts']if q['kind']=='DOORWAY'and (q['closed_bounds'][0][0]>=1.249 if local_side==1 else q['closed_bounds'][1][0]<=-1.249)]
                    for di,door in enumerate(doors):
                        db=np.asarray(door['closed_bounds']);localz=float(db[:,2].mean());cp=carcentre+u*localz;span=float(db[1,2]-db[0,2]);floors=[q for q in report['parts']if q['kind']=='FLOOR'and q['closed_bounds'][0][2]<=localz<=q['closed_bounds'][1][2]];half=max(abs(q['closed_bounds'][j][0])for q in floors for j in(0,1));carfloor=rectangle(cp,u,n,-max(span/2,.8125),max(span/2,.8125),0,half);trigger=rectangle(cp,u,n,-span/2,span/2,min(abs(db[0,0]),abs(db[1,0])),max(abs(db[0,0]),abs(db[1,0])));high=full.union(carfloor);combined=high.union(low);solutions=[];last={}
                        bodypolys=[MultiPoint(np.column_stack((q[:,0]*local_side,q[:,2]))).convex_hull for q in closed if q[:,1].max()>1.0001 and q[:,1].min()<2.8]
                        for shift in sorted(np.arange(-.4,.4001,.025),key=abs):
                            fromp=cp+u*shift+n*3;top=cp+u*shift+n*.9
                            if(math.floor(fromp[0]),2*y,math.floor(fromp[1]))not in nodes:continue
                            feet=y+1;support=.36;blocked=False;touch=False;hits=0;maxalong=0;steps=[]
                            for fraction in np.linspace(0,1,97):
                                p=fromp+(top-fromp)*fraction;body=box(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3);harea=body.intersection(high).area;larea=body.intersection(low).area;nextfeet=y+1 if harea>1e-8 else y+.5 if larea>1e-8 else feet
                                if abs(nextfeet-feet)>.500001:blocked=True;break
                                if nextfeet!=feet:steps.append([float(fraction),float(feet),float(nextfeet)])
                                feet=nextfeet;support=min(support,body.intersection(combined).area);touch|=body.intersection(trigger).area>.005
                                if support<=.025:blocked=True;break
                                corners=np.asarray(body.exterior.coords)[:-1]-cp;maxalong=max(maxalong,float(np.max(np.abs(corners@u))));local=Polygon(np.column_stack((corners@n,corners@u+localz)));hits+=any(poly.intersection(local).area>1e-8 for poly in bodypolys)
                                if w.body(float(p[0]),feet,float(p[1])):blocked=True;break
                            valid=support>.025 and touch and not blocked and hits>0 and maxalong<span/2+1e-7
                            last=dict(shift=float(shift),support=support,blocked=blocked,touch=bool(touch),closed_hits=hits,max_along=maxalong,span=span)
                            if valid:
                                solutions.append(dict(shift=float(shift),minimum_support_area=support,trigger_contact=bool(touch),saved_body_blocked=blocked,closed_visible_door_hits=hits,maximum_door_longitudinal_extent=maxalong,from_xyz=[float(fromp[0]),y+1,float(fromp[1])],floor_steps=steps));break
                        row=dict(group=group['id'],rail=rail['id'],direction=direction,car=ci,door=di,model=ident,valid=bool(solutions),requires_stopped_car_and_fully_open_door=True)
                        if solutions:
                            row.update(solutions[0])
                            if di==0 and direction==1:
                                p=row['from_xyz'];prove('street-to-conditional-door-'+rail['id']+'-'+str(ci),route((math.floor(p[0]),2*y,math.floor(p[2])))+[p])
                        else:row['last_failure']=last;errors.append('Conditional door '+str((rail['id'],direction,ci,di)))
                        boarding.append(row)
            negative.append(dict(name='closed-doors-reject-'+rail['id'],rejected=all(q.get('closed_visible_door_hits',0)>0 for q in boarding if q['rail']==rail['id'])))
            print('Verified model and doorway group',rail['id'],'errors',len(errors),flush=True)
    minimum=min(q['first_continuous_width']for q in widths)
    if minimum<3-1e-8:errors.append('Full length boarding aisle narrower than 3m')
    if generic['errors']:errors.append('Shared structural/public failure')
    from prepare_station_set_native import validate as validate_station_set
    wrong=copy.deepcopy(read(candidate/'station-set-plan.json'));wrong['stations'][0]['platforms'].append(copy.deepcopy(wrong['stations'][0]['platforms'][0]));rejected=False
    try:validate_station_set(wrong)
    except ValueError:rejected=True
    negative.append(dict(name='duplicate-or-wrong-platform-ownership',rejected=rejected,actual_mutated_plan_test=True,source_plan_retained=True))
    first=c['groups'][0]['rails'][0];line=LineString(np.asarray(geo[first['id']]['points'])[:,[0,2]]);cp=point(line,line.length/2);probe=(math.floor(cp[0]),y+2,math.floor(cp[1]));oldstate=e.state(*probe);e.put(*probe,'minecraft:stone')
    try:
        band_width=model_bands(c['groups'][0])[0][2];poly=envelope(line,length=20,width=2*band_width,bogie1_position=c['groups'][0]['bogie1_position'],bogie2_position=c['groups'][0]['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125);rejected=any(poly.intersects(box(probe[0]+q[0],probe[2]+q[2],probe[0]+q[3],probe[2]+q[5]))for q in collision(e.state(*probe)))
    finally:e.put(*probe,oldstate)
    negative.append(dict(name='full-body-obstacle-in-running-track',rejected=bool(rejected),pos=list(probe),actual_injected_state='minecraft:stone',restored_after_test=True))
    tracknode=(math.floor(cp[0]),2*y,math.floor(cp[1]));floors,unknown=w.floors(cp[0],y+1,cp[1]);negative.append(dict(name='ordinary-public-walk-must-not-enter-track',rejected=tracknode not in nodes and not any(abs(q-(y+1))<1e-7 for q in floors),rejected_public_node=list(tracknode),full_train_car_floor_is_only_conditional=True))
    if not all(q['rejected']for q in negative):errors.append('Independent negative case failed')
    water=unary_union([shape(q['geometry'])for q in spec['water_features']]).buffer(3);waterchanges=[list(p)for p,(before,after)in edits.items()if water.intersects(box(p[0],p[2],p[0]+1,p[2]+1))and before.split('[')[0]not in OPEN]
    if waterchanges:errors.append('Water ground changed')
    report=dict(errors=errors,offline_candidate_verified=not errors,world_written=False,cells=len(edits),source_files_byte_equal=sourcebytes,source_exact=all(q['equal']for q in sourcebytes),forward_reverse_delta_checks=roundtrip,original_devices_retained=len(devices),original_device_nbt_equal=sourcebytes[-1]['equal'],original_actors_equal=read(source/'capture.json').get('actors')==read(candidate/'capture.json').get('actors'),original_actors_retained=len(read(source/'capture.json').get('actors',[])),paths=paths,paths_verified=sum(q['valid']for q in paths),directions_checked=len(paths)*2,full_length_platform_width_samples=widths,minimum_full_length_platform_width=minimum,visible_model_sweeps=sweeps,conditional_boarding=boarding,conditional_door_count=len(boarding),negative_cases=generic['negative_cases']+negative,new_floating_solids=generic['new_floating_solids'],newly_detached_retained_cells=generic['newly_detached_retained_cells'],retained_road_overhead_checks=roadclear,minimum_retained_road_clearance=min((q['clearance']for q in roadclear),default=None),water_reserved_ground_changes=waterchanges,public_floor_errors=[],unexpected_public_obstructions=[],native_geometry_only_no_simulator=True,through_service_complete=False)
    write(a.out/'review.json',report);write(candidate/'station-independent-check.json',report);write(candidate/'functional-check.json',dict(errors=errors,evidence=str(a.out/'review.json'),offline_candidate_verified=not errors,world_written=False,through_service_complete=False));print('Interchange independent check',len(errors),'errors',len(boarding),'conditional doors',len(paths),'paths',flush=True)
    if errors:raise SystemExit(1)

def package(a):
    c=read(a.config)['sites'][0];candidate=a.candidate;review=a.out;r=read(review/'review.json');d=read(candidate/'station-design.json');native=read(c['geometry'])
    if r['errors']or not c.get('exact_source_and_candidate_views_reviewed_by_author'):raise ValueError('Successful checks and explicit author image review required')
    for key,name in(('pose_validation','vehicle-pose-validation.json'),('pair_clearance','adjacent-rail-body-clearance.json'),('interface_regressions','interface-regressions.json')):
        proof=read(c[key])
        if proof['errors']:raise ValueError('Failed '+key)
        shutil.copy2(c[key],candidate/name)
    shutil.copy2(c['vehicle_resource_facts'],candidate/'vehicle-resource-facts.json')
    write(candidate/'vehicle-pose-provenance.json',dict(errors=[],helper='tools/map_pipeline/mtr_vehicle_pose.py',runtime_branch_evidence=c['groups'][0]['body_pose_source'],resource_facts='vehicle-resource-facts.json',validation='vehicle-pose-validation.json',bogies=[dict(group=g['id'],bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'])for g in c['groups']],minimum_bogie_distance_to_complete_train_ends=4,unclamped_runtime_sampling_radius=1,complete_consist_clamping_not_needed_for_selected_models=True,world_written=False))
    models=Path(c['merged_model_reference']);models.mkdir(exist_ok=True);target=candidate/'vehicle-model';target.mkdir(exist_ok=True);idents=[];provenance=[]
    for g in c['groups']:
        for ident in g['models']:
            if ident in idents:continue
            idents.append(ident)
            for suffix in('.json','-closed-cubes.npz','-visible-cubes.npz'):
                src=Path(g['model_source'])/(ident+suffix);shutil.copy2(src,models/src.name);shutil.copy2(src,target/src.name)
            provenance.append(dict(model=ident,source=g['model_source']))
    write(models/'reference-manifest.json',dict(models=provenance,world_written=False));write(target/'reference-manifest.json',dict(models=provenance,world_written=False));shutil.copy2(a.config,candidate/'site-selection-config.json');shutil.copy2(c['geometry'],candidate/'native-math-samples.json')
    views=c['reviewed_views'];(review/'views').mkdir(exist_ok=True)
    for path in views:shutil.copy2(candidate/path,review/path)
    features=json.loads(gzip.decompress(Path(c['features']).read_bytes()))['features'];deviations=[]
    for g in c['groups']:
        ref=shape(features[g['cached_station_feature']]['geometry'])
        for rail in g['rails']:
            nr=next(q for q in native['rails']if q['input_rail_id']==rail['id']);points=[Point(p[0],p[2])for p in nr['points']];distances=[ref.distance(p)for p in points]
            deviations.append(dict(group=g['id'],rail=rail['id'],cached_station_feature=g['cached_station_feature'],native_length=nr['length'],native_midpoint_to_cached_station_corridor=ref.distance(points[len(points)//2]),maximum_distance_to_finite_cached_station_segment=max(distances),note='Finite GIS station segment is shorter than the 1:1 rolling-stock platform; endpoint distance also includes deliberate longitudinal extension. Adjacent approach corridor mapping is a separate stage 3 task.'))
    write(candidate/'reference-geography.json',dict(errors=[],cached_centre=c['centre'],corridors=deviations,selection=c['site_selection'],exact_real_platform_counts_claimed=False,operator_mapping_is_geographic_inference=True,world_written=False))
    write(candidate/'source-preservation.json',dict(errors=[],source=c['source'],complete_captured_devices=r['original_devices_retained'],device_nbt_preserved=r['original_device_nbt_equal'],all_source_files_byte_equal=r['source_exact'],exact_inverse_and_forward=r['forward_reverse_delta_checks'],actors=r['original_actors_retained'],changes=r['cells'],world_written=False))
    write(candidate/'view-review.json',dict(reviewed_views=views,source_views=c['source_views'],source_before_and_candidate_after_compared=True,reviewed_by='offline interchange author',views_reviewed_by_root=False,visual_defects_identified=[],resolved_defects=c['resolved_defects'],renderer_scope='Exact frozen source/after voxel faces, two cameras per crop; native rails/trains and gameplay rendering remain pending.',world_written=False))
    write(candidate/'visible-model-sweep.json',dict(errors=[],model_sources=provenance,rails=len(native['rails']),native_platform_lengths=[q['length']for q in native['rails']],per_group_consist_lengths=[dict(group=g['id'],length=g['consist_length'])for g in c['groups']],obstacles=sum((q['obstacles']for q in r['visible_model_sweeps']),[]),conditional_doors=r['conditional_door_count'],train_directions_per_rail=2,minimum_full_length_platform_width=r['minimum_full_length_platform_width'],minimum_retained_road_clearance=r['minimum_retained_road_clearance'],evidence=str(review/'review.json'),world_written=False,through_service_complete=False,native_boarding_runtime_verified=False))
    checks=dict(schema='station-release-checks-v1',commands=[],candidate_error_reports=['functional-check.json','offline-verification.json','station-independent-check.json','source-preservation.json','visible-model-sweep.json'],review_error_reports=['review.json','structural-review.json'],structural_report='structural-review.json',report_values=[dict(root='review',file='review.json',equals=dict(offline_candidate_verified=True,original_device_nbt_equal=True,original_actors_equal=True,public_floor_errors=[],unexpected_public_obstructions=[],new_floating_solids=[],newly_detached_retained_cells=0,paths_verified=r['paths_verified'],directions_checked=r['directions_checked'],conditional_door_count=r['conditional_door_count'],world_written=False))],exact_model_arrays=[dict(candidate='vehicle-model/'+ident+'-visible-cubes.npz',reference=ident+'-visible-cubes.npz',keys=['cubes','names','door_slides'])for ident in idents],reviewed_views=views,views_reviewed_by_root=False,note='Root structural/view review, latest native snapshot rebase and actual installation remain pending; per-platform required consists are explicit in station-set-plan.')
    checks['candidate_error_reports']+=['vehicle-pose-validation.json','vehicle-pose-provenance.json','adjacent-rail-body-clearance.json','interface-regressions.json']
    write(candidate/'release-checks.json',checks)
    ports=read(candidate/'stage-three-interfaces.json');ports['explicit_rail_ports']=[]
    for g in c['groups']:
        for rail in g['rails']:
            nr=next(q for q in native['rails']if q['input_rail_id']==rail['id']);ps=np.asarray(nr['points']);south=ps[0]-ps[1];south/=np.linalg.norm(south);north=ps[-1]-ps[-2];north/=np.linalg.norm(north)
            ports['explicit_rail_ports'].append(dict(group=g['id'],rail_id=rail['id'],from_endpoint=rail['from'],to_endpoint=rail['to'],from_native_node_angle=rail['from_angle'],to_native_node_angle=rail['to_angle'],south_native_world_endpoint=ps[0].tolist(),north_native_world_endpoint=ps[-1].tolist(),south_external_unit_tangent=south.tolist(),north_external_unit_tangent=north.tolist(),rail_y=c['rail_y'],mapped_station_feature=g['cached_station_feature'],terminal_south_port=g['id']=='branch_terminal',finite_model_overhang_verified=True,external_track_grade_geometry_and_buffer_stop_pending=True))
    ports['group_geographic_roles']=c['site_selection']['service_groups'];ports['all_public_group_transfers_grade_separated']=True;ports['minimum_reserved_roadway_clearance']=r['minimum_retained_road_clearance'];ports['departure_reservation']=dict(length_per_running_end=c.get('departure_reservation_length',60),method='Finite tangent extension joined to native station points; complete rigid models and actual block Y clipping in station-independent-check.json.',no_external_running_rail_installed=True,through_grade_and_curves_pending=True,terminal_south_is_not_a_running_port=True);ports['hayakawa_coordination']=dict(north_ports=[[3243,-68,692],[3263,-68,700]],source='hayakawa-config-v15 / hayakawa-ports-geometry-v2, communicated by its author',station_rail_level=-68,odawara_rail_level=-67,elevation_difference=1,intervening_native_curve_and_grade_pending=True);write(candidate/'stage-three-interfaces.json',ports)
    write(candidate/'freeze-handoff.json',dict(candidate_frozen=True,candidate=str(candidate),independent_review=str(review),models=str(models),native_expected_members=c['expected_native_members'],native_baseline_rebase_required=True,offline_errors=[],native_registration_pending=True,world_installation_pending=True,through_service_complete=False,user_visual_acceptance=False,source_and_candidate_views_reviewed=True,original_devices_preserved=r['original_devices_retained'],full_platform_minimum_width=r['minimum_full_length_platform_width'],conditional_doors=r['conditional_door_count'],strict_paths=r['paths_verified'],stage_three_interfaces='stage-three-interfaces.json',native_plan='station-set-plan.json',release_layout='release-layout.json',root_strict_review_pending=True,expected_new_native_members=15,platform_rail_bindings=d['platform_rails']))
    print('Frozen interchange',r['cells'],'cells;',r['conditional_door_count'],'doors;',r['paths_verified'],'strict paths;',r['minimum_full_length_platform_width'],'m minimum aisle')

def phase(a):
    """Compare native endpoint parity against exact voxel boarding support only."""
    c=read(a.config)['sites'][0];g=c['groups'][0];bands,lw,extent=model_bands(g);native=read(a.geometry);results=[];modelroot=Path(g['model_source']);models={name:read(modelroot/(name+'.json'))for name in g['models']}
    for nr in native['rails']:
        line=LineString(np.asarray(nr['points'])[:,[0,2]]);u=np.asarray(line.coords[-1])-line.coords[0];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])*(1 if '-1-phase-'in nr['input_rail_id']else -1)
        fullsweep=prep(envelope(line,length=2*extent,width=2*bands[0],bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125));lowsweep=prep(envelope(line,length=2*extent,width=2*lw,bogie1_position=g['bogie1_position'],bogie2_position=g['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125));rows=[]
        for offset in(-50,-30,-10,10,30,50):
            model=g['models'][0]if offset==50 else g['models'][2]if offset==-50 else g['models'][1];report=models[model]
            for door in[q for q in report['parts']if q['kind']=='DOORWAY'and q['closed_bounds'][0][0]>0]:
                db=np.asarray(door['closed_bounds']);localz=db[:,2].mean();carcentre,u,tn=pose(line,line.length/2+offset,g['bogie1_position'],g['bogie2_position']);n=tn*(1 if '-1-phase-'in nr['input_rail_id']else -1);cp=carcentre+u*localz;span=db[1,2]-db[0,2];ps=list(cells(box(cp[0]-7,cp[1]-7,cp[0]+7,cp[1]+7)));full=[];low=[]
                for x,z in ps:
                    if np.dot(np.array([x+.5,z+.5])-cp,n)<0:continue
                    cell=box(x,z,x+1,z+1)
                    if not fullsweep.intersects(cell):full.append(cell)
                    elif not lowsweep.intersects(cell):low.append(cell)
                high=unary_union(full).union(rectangle(cp,u,n,-.8125,.8125,0,1.25));low=unary_union(low);combined=high.union(low);solutions=[]
                for shift in sorted(np.arange(-.275,.2751,.025),key=abs):
                    p0=cp+u*shift+n*3;p1=cp+u*shift+n*.9;support=.36;feet=1;bad=False
                    for f in np.linspace(0,1,73):
                        p=p0+(p1-p0)*f;body=box(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3);h=body.intersection(high).area;lo=body.intersection(low).area;nextfeet=1 if h>1e-8 else .5 if lo>1e-8 else feet
                        if abs(nextfeet-feet)>.500001:bad=True;break
                        feet=nextfeet;support=min(support,body.intersection(combined).area)
                        if support<=.025:bad=True;break
                    if not bad:solutions.append((float(shift),support));break
                rows.append(dict(offset=offset,door_local_z=float(localz),valid=bool(solutions),solutions=solutions))
        results.append(dict(rail=nr['input_rail_id'],length=nr['length'],valid=sum(q['valid']for q in rows),total=len(rows),failed=[q for q in rows if not q['valid']]))
        print(results[-1],flush=True)
    write(a.out,results)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('mode',choices=('survey','plan','verify','package','phase'));p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--candidate',type=Path);p.add_argument('--geometry',type=Path)
    a=p.parse_args();globals()[a.mode](a)
