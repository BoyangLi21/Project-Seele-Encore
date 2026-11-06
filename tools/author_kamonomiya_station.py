"""Author a two-track station solely in an immutable offline candidate.

The sampled native rail mathematics and 20 m rigid carriage envelope determine
platform clearance. No Simulator, live save, native database or JAR is written.
"""
import argparse,collections,copy,json,math,shutil
from pathlib import Path
import numpy as np
import nbtlib
from shapely.geometry import Point,LineString,Polygon,box,mapping,shape
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from prepare_hakone_city_cross import packed

ALLOWED=SOIL|AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:light'}
OPEN=AIR|{'minecraft:light'}
BASE=-78

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def voxel_box(e,bounds):
    x,y,z,X,Y,Z=bounds;palette=['minecraft:air'];ids={palette[0]:0};data=np.zeros((Y-y+1,Z-z+1,X-x+1),np.uint16)
    for rx in range(x//512,X//512+1):
        for rz in range(z//512,Z//512+1):
            r=e.region(rx*512,rz*512);codes=[]
            for st in r['names']:
                if st not in ids:ids[st]=len(palette);palette.append(st)
                codes.append(ids[st])
            remap=np.asarray(codes,np.uint16)
            for(cx,cz),v in zip(r['coords'],r['after']):
                cx,cz=int(cx),int(cz);l,b,R,T=max(x,cx*16),max(z,cz*16),min(X,cx*16+15),min(Z,cz*16+15)
                if l>R or b>T:continue
                data[:,b-z:T-z+1,l-x:R-x+1]=remap[v[y+128:Y+129,b-cz*16:T-cz*16+1,l-cx*16:R-cx*16+1]]
    return data,palette

def rigid_envelope(line,length=20,width=2.5):
    rectangles=[]
    def pos(s):
        if s<0:
            a=np.asarray(line.interpolate(0).coords[0]);b=np.asarray(line.interpolate(.125).coords[0]);return a+(b-a)/np.linalg.norm(b-a)*s
        if s>line.length:
            a=np.asarray(line.interpolate(line.length).coords[0]);b=np.asarray(line.interpolate(line.length-.125).coords[0]);return a+(a-b)/np.linalg.norm(a-b)*(s-line.length)
        return np.asarray(line.interpolate(s).coords[0])
    for s in np.arange(0,line.length+.125,.25):
        s=min(s,line.length);c=pos(s);u=pos(s+length/2)-pos(s-length/2);u/=np.linalg.norm(u);n=np.asarray([-u[1],u[0]])
        rectangles.append(Polygon([c+u*length/2+n*width/2,c-u*length/2+n*width/2,c-u*length/2-n*width/2,c+u*length/2-n*width/2]))
    return unary_union(rectangles).buffer(.08)

def author(a):
    if a.out.exists():raise ValueError('Use a fresh candidate directory')
    a.out.mkdir();shutil.copytree(a.source/'source',a.out/'source');(a.out/'delta').mkdir()
    for name in ('capture.json','measured.npz','captured-devices.dat'):shutil.copy2(a.source/name,a.out/name)
    cap=json.loads((a.source/'capture.json').read_text('utf8'));bounds=cap['bounds_xz'];x,z,X,Z=bounds
    with np.load(a.authority/'network.npz')as f:
        ax,az,aX,aZ=map(int,f['bounds']);oldwalk=f['walk'];oldgrade=f['grade2']
    with np.load(a.source/'measured.npz')as f:ground=f['top'].copy()
    devices={tuple(int(d[k])for k in('x','y','z')) for d in nbtlib.load(a.source/'captured-devices.dat')['Devices']}
    site_plan=json.loads(a.site.read_text('utf8'))
    cached_water=unary_union([shape(q['geometry'])for q in site_plan['nearby_water_interfaces']]).buffer(3)
    e=Editor(a.out);s=Station(e);public=set();owned=set();parts=[]
    def put(px,py,pz,name):
        if not(x<=px<=X and z<=pz<=Z):raise ValueError(('Outside captured source',px,py,pz))
        before=e.state(px,py,pz,True)
        if e.state(px,py,pz)==name:return
        if box(px,pz,px+1,pz+1).intersects(cached_water):raise ValueError(('Reserved three-block water buffer',px,py,pz))
        if before.split('[')[0]not in ALLOWED:raise ValueError(('Protected original cell',px,py,pz,before,name))
        if(px,py,pz)in devices:raise ValueError(('Existing device',px,py,pz))
        if oldwalk[pz-az,px-ax]:raise ValueError(('Existing public column',px,py,pz))
        e.put(px,py,pz,name);owned.add((px,py,pz))
    def column(px,pz,g2,foundation=True,declare=True):
        if oldwalk[pz-az,px-ax]:
            if declare:public.add((px,pz,int(oldgrade[pz-az,px-ax])))
            return
        py=(g2+1)//2
        if foundation:
            bottom=int(ground[pz-z,px-x])-1
            if bottom<BASE-6:raise ValueError(('Unbounded foundation',px,pz,bottom))
            for y in range(bottom,py):put(px,y,pz,'minecraft:stone_bricks')
        put(px,py,pz,'minecraft:smooth_stone' if g2%2==0 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        if declare:public.add((px,pz,g2))
    def points(poly):
        l,b,r,t=poly.bounds
        for pz in range(math.floor(b)-1,math.ceil(t)+1):
            for px in range(math.floor(l)-1,math.ceil(r)+1):
                if poly.covers(Point(px+.5,pz+.5)):yield px,pz
    def floor(poly,g2,foundation=True):
        for px,pz in points(poly):column(px,pz,g2,foundation)
    def rect(c,u,n,L,W):return Polygon([c+u*L+n*W,c-u*L+n*W,c-u*L-n*W,c+u*L-n*W])
    raw=json.loads(a.native_input.read_text('utf8'));samples=json.loads(a.samples.read_text('utf8'))
    if len(samples)!=2 or any(not q['valid']or q['native_length']<128 for q in samples):raise ValueError('Two native platforms of at least 128 metres required')
    lines=[LineString([(p[0],p[2])for p in q['points']])for q in samples]
    if any(abs(p[1]-BASE)>1e-8 for q in samples for p in q['points']):raise ValueError('Station track is not flat at the declared datum')
    aa=np.asarray(samples[0]['points'])[:,[0,2]];bb=np.asarray(samples[1]['points'])[:,[0,2]]
    if aa.shape!=bb.shape:raise ValueError('Matched parallel samples required')
    middle=LineString((aa+bb)/2);u=np.asarray(middle.coords[-1])-middle.coords[0];u/=np.linalg.norm(u);n=np.asarray([-u[1],u[0]])
    centre=np.asarray(middle.interpolate(middle.length/2).coords[0]);start=middle.length/2+10;end=start-64
    def at(distance,offset=0):return np.asarray(middle.interpolate(distance).coords[0])+n*offset
    def offset_line(begin,finish,offset=0):return LineString([at(v,offset)for v in np.linspace(begin,finish,max(2,math.ceil(abs(finish-begin)*8)))])
    envelopes=[rigid_envelope(q)for q in lines];sweep=unary_union(envelopes)
    rail_masks=[]
    for line,envelope in zip(lines,envelopes):
        railcols=[];bed=line.buffer(2.5,cap_style=2)
        for px,pz in points(envelope.buffer(.8)):
            cube=box(px,pz,px+1,pz+1)
            if not cube.intersects(envelope):continue
            railcols.append((px,pz))
            # A carriage can overhang the end of a platform, but that does not
            # authorize extending its physical bed into an unbuilt river link.
            if bed.covers(Point(px+.5,pz+.5)):
                put(px,BASE-2,pz,'minecraft:stone');put(px,BASE-1,pz,'minecraft:gravel')
            for py in range(BASE,BASE+6):put(px,py,pz,'minecraft:air')
        rail_masks.append(railcols)
    platform=[]
    for px,pz in points(middle.buffer(5.7,cap_style=2)):
        if box(px,pz,px+1,pz+1).intersects(sweep):continue
        column(px,pz,BASE*2);platform.append((px,pz))
        d=min(box(px,pz,px+1,pz+1).distance(q)for q in envelopes)
        if d<1.1:put(px,BASE,pz,'projectseele:station_tactile_warning')
    # Long half-slab slopes have 0.5-block rises every four horizontal blocks.
    # This is a no-jump Minecraft route, not a claim of real wheelchair access.
    ramps=[]
    for offset,label in ((0,'island no-jump slope'),(19,'south approach no-jump slope')):
        line=offset_line(end,start,offset);cols=[]
        for px,pz in points(line.buffer(1.8,cap_style=2)):
            d=line.project(Point(px+.5,pz+.5));g2=BASE*2+max(0,16-math.ceil(d/4))
            column(px,pz,g2);cols.append([px,pz,g2])
        ramps.append(dict(kind=label,columns=cols,metres=line.length,rise=8,maximum_surface_step=.5,continuous_wheelchair_ramp_claimed=False))
        # Continuous solid guard cheeks outside the three-wide usable slope.
        for px,pz in points(line.buffer(2.65,cap_style=2).difference(line.buffer(1.8,cap_style=2))):
            if offset==0 and (px,pz)not in platform:continue
            d=line.project(Point(px+.5,pz+.5));g2=BASE*2+max(0,16-math.ceil(d/4));py=(g2+1)//2
            if d>line.length-4:continue
            column(px,pz,g2,declare=False);put(px,py+1,pz,'minecraft:light_gray_stained_glass')
    # One bridge crosses the southern running track. No pedestrian crossing
    # exists at rail level; load-bearing piers stay outside both car envelopes.
    top=at(end);deck=rect(top+n*12.5,u,n,2.8,14.2)
    floor(deck,(BASE+8)*2,False)
    for px,pz in points(deck):put(px,BASE+7,pz,'minecraft:gray_concrete')
    for along in(-2,2):
        for offset in(0,13,24):
            p=top+u*along+n*offset;px,pz=int(p[0]),int(p[1])
            if box(px,pz,px+1,pz+1).intersects(sweep):raise ValueError('Bridge support in swept train envelope')
            for py in range(BASE-1,BASE+8):put(px,py,pz,'minecraft:gray_concrete')
    # Short conventional stair plus the separate long no-jump slope on the
    # land side, connected to the same common bridge and station hall.
    stairs=offset_line(end,end+19,24);staircols=[]
    for px,pz in points(stairs.buffer(1.65,cap_style=2)):
        d=stairs.project(Point(px+.5,pz+.5));g2=BASE*2+max(0,16-max(0,math.ceil(d-3)))
        column(px,pz,g2);staircols.append([px,pz,g2])
    floor(deck,(BASE+8)*2,False)
    lowlink=offset_line(end+19,middle.length/2-8,24)
    floor(lowlink.buffer(1.65,cap_style=2),BASE*2)
    # Station hall uses the reviewed south-side location, retaining the road.
    plan=site_plan;hc=np.asarray(plan['hall_centre_xz']);hall=rect(hc,u,n,9,7)
    floor(hall,BASE*2)
    for px,pz in points(hall):
        v=np.asarray([px+.5,pz+.5])-hc;du,dn=float(v@u),float(v@n)
        wall=abs(du)>7.8 or abs(dn)>5.8
        door=(dn>5.8 and abs(du)<2.7)or(dn<-5.8 and abs(du-4)<2.7)or(abs(du)>7.8 and -5<dn<1)
        if wall and not door:
            for py in range(BASE+1,BASE+6):put(px,py,pz,'minecraft:light_gray_stained_glass'if BASE+2<=py<=BASE+3 else'minecraft:light_gray_concrete')
        put(px,BASE+6,pz,'minecraft:gray_concrete')
        if wall:put(px,BASE+7,pz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    # Clear hall-side bridges to the lower slope entrance and stair footway.
    connectors=[LineString([at(start,19),hc+u*10-n*2,hc+u*7-n*2]),LineString([at(middle.length/2-8,24),hc-u*7-n*2])]
    for line in connectors:floor(line.buffer(1.65,cap_style=2),BASE*2)
    forecourt=rect(hc+n*7.5,u,n,5,1.3);floor(forecourt,BASE*2)
    route=plan['access_corridor']['centreline_xz'];columns={}
    for i,(px,pz)in enumerate(route):
        # Preserve the measured -79.5 sidewalk slab endpoint; spread the 1.5
        # block descent over the long approach without changing old columns.
        g2=BASE*2-max(0,min(3,(i-8)//7))
        for dx in(-1,0,1):
            for dz in(-1,0,1):columns[px+dx,pz+dz]=g2
    for(px,pz),g2 in columns.items():column(px,pz,g2)
    # A low concourse plus a high supported platform canopy leave the bridge
    # overhead clear while retaining the longer street-facing building scale.
    canopy=middle.buffer(5.6,cap_style=2)
    for px,pz in points(canopy):put(px,BASE+13,pz,'minecraft:light_gray_concrete')
    for distance in np.linspace(8,middle.length-8,8):
        for offset in(-2.5,2.5):
            q=at(distance,offset);px,pz=int(q[0]),int(q[1])
            if (px,pz)not in platform or box(px,pz,px+1,pz+1).intersects(sweep):continue
            for py in range(BASE+1,BASE+13):put(px,py,pz,'minecraft:gray_concrete')
            put(px,BASE+12,pz,'minecraft:sea_lantern')
    for px,pz in points(deck.boundary.buffer(.5)):
        if not deck.covers(Point(px+.5,pz+.5)):continue
        # Leave all four slope/stair entrances open at the ends of the bridge.
        if min(Point(px+.5,pz+.5).distance(offset_line(end-2,end+3,v))for v in(0,19,24))<2.2:continue
        put(px,BASE+9,pz,'minecraft:light_gray_stained_glass')
    # Exact sign tags are included, but native registry work is intentionally
    # left to the primary agent's serial publish path.
    sign_locations=[(round(hc[0]),BASE+4,round(hc[1]+7),'south',['鴨宮駅','KAMONOMIYA','東海道本線','改札 / 站台']),
        (int(top[0]),BASE+11,int(top[1]+10),'south',['鴨宮駅','1 / 2 番線','跨線橋','Platform bridge']),
        (int(centre[0]),BASE+11,int(centre[1]),'south',['鴨宮','KAMONOMIYA','小田原 ← → 国府津','1 / 2'])]
    for index,(px,py,pz,facing,words) in enumerate(sign_locations):
        # Wall signs must have a real backing cube on the opposite face.
        put(px,py,pz-1,'minecraft:gray_concrete')
        if index==0:put(px,BASE+5,pz-1,'minecraft:chain[axis=y,waterlogged=false]')
        if index==1:
            for y in range(BASE+9,py):put(px,y,pz-1,'minecraft:gray_concrete')
        if index==2:put(px,BASE+12,pz-1,'minecraft:chain[axis=y,waterlogged=false]')
        s.sign(px,py,pz,words,facing)
    # Exclude intentional walls, ramp supports, posts and furnishings from
    # passenger nodes; keep every remaining advertised floor for connectivity.
    allpublic=sorted(public);public=[]
    for px,pz,g2 in allpublic:
        py=(g2+1)//2;st=e.state(px,py,pz)
        if st.split('[')[0]in OPEN or ('type=bottom'in st)!=(g2%2!=0):continue
        if any(e.state(px,y,pz).split('[')[0]not in OPEN for y in(py+1,py+2)):continue
        public.append([px,pz,g2])
    regions=e.save();e.regions.clear()
    changes=[]
    for d in s.devices:
        tag=d['After'];p=tuple(int(tag[k])for k in('x','y','z'));changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(p)),'After':tag}))
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(a.out/'block-entities.dat',gzipped=True)
    for f in (a.samples,a.native_input):shutil.copy2(f,a.out/f.name)
    station_min=[min(v[0]for v in owned)-1,BASE-4,min(v[2]for v in owned)-1];station_max=[max(v[0]for v in owned)+1,BASE+17,max(v[2]for v in owned)+1]
    rails=[dict(q,mode='TRAIN',kind='platform',platform_name=str(i+1))for i,q in enumerate(raw['segments'])]
    native=dict(rails=rails,stations=[dict(id='kamonomiya',name='鴨宮駅',min=station_min,max=station_max,color=0xD38829)],lines=[])
    dump(a.out/'native-station-plan.json',native)
    goals={}
    def nearest(label,q,desired_g2=BASE*2):
        candidates=[r for r in public if abs(r[2]-desired_g2)<=1]
        if not candidates:raise ValueError('No goal-level walking surfaces')
        v=min(candidates,key=lambda r:math.hypot(r[0]+.5-q[0],r[1]+.5-q[1]));goals[label]=[v[0],v[2]/2+1,v[1]]
    for i in(0,1):
        for distance,label in((6,'west'),(middle.length/2,'centre'),(middle.length-6,'east')):nearest(f'platform_{i+1}_{label}',at(distance,-4.5 if i==0 else 4.5))
    nearest('hall',hc);nearest('forecourt',hc+n*10);nearest('bridge',top+n*10,(BASE+8)*2);nearest('island_ramp_foot',at(start,0));nearest('south_ramp_foot',at(start,19))
    anchor=plan['access_corridor']['target']['xyz'];nearest('street',np.asarray([anchor[0],anchor[2]]),int(plan['access_corridor']['target']['floor_grade2']))
    partbounds=[min(v[0]for v in owned),min(v[1]for v in owned),min(v[2]for v in owned),max(v[0]for v in owned),max(v[1]for v in owned),max(v[2]for v in owned)]
    ground_access=unary_union([hall,forecourt,LineString(route).buffer(2)])
    ground_access_columns=[r for r in public if r[2]<=BASE*2 and ground_access.covers(Point(r[0]+.5,r[1]+.5))]
    design=dict(station='鴨宮駅',parts=[dict(kind='dual-track station, ramps and bridge',bounds=partbounds)],public_columns=public,goals=goals,retained_street_anchor=goals['street'],ramps=ramps,stairs=staircols,
        ground_access_columns=ground_access_columns,ground_access_format=['x','z','grade2'],station_multi_level_nodes=[[px,g2,pz]for px,pz,g2 in public],station_multi_level_node_format=['x','grade2','z'],network_single_grade2_update_scope='ground_access_columns only; retain all other station surfaces in the multi-level overlay',
        expected_signs=[dict(pos=[px,py,pz],title=words[0])for px,py,pz,facing,words in sign_locations],
        rail_lengths=[q['native_length']for q in samples],planned_maximum_consist_length=120,rigid_carriage_length=20,swept_width_with_margin=2.5,swept_height_blocks=6,curve_samples_interval=.125,rigid_sweep_interval=.25,
        envelope_geometry=mapping(sweep),platform_columns=platform,rail_columns=rail_masks,no_at_grade_passenger_crossing=True,native_registry_pending=True,through_service_complete=False,
        world_written=False,physical_scope_complete=False,source_authority=str(a.authority),native_math_samples=a.samples.name,street_anchor_was_preserved=True,step_free_claim='No jumping required for Minecraft half-block slope. Real wheelchair compliance is not claimed.')
    dump(a.out/'station-design.json',design)
    manifest=dict(world=cap['world'],kind='measured-double-track-station',bounds_xz=bounds,regions=regions,cells=sum(r['cells']for r in regions),station_design='station-design.json',native_station_pending=True,world_written=False)
    dump(a.out/'manifest.json',manifest)
    print('Prepared candidate:',manifest['cells'],'cells;',len(public),'public surfaces; native registration pending',flush=True)
    verify(a.out,a.authority)

def verify(candidate,authority):
    e=Editor(candidate);d=json.loads((candidate/'station-design.json').read_text('utf8'));m=json.loads((candidate/'manifest.json').read_text('utf8'))
    with np.load(authority/'network.npz')as f:ax,az,aX,aZ=map(int,f['bounds']);oldwalk=f['walk']
    errors=[];counts=collections.Counter();bad=[];declared=d['parts'][0]['bounds']
    existing_devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    for file in (candidate/'source').glob('*.npz'):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        for(cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            for iy,iz,ix in np.argwhere(before!=after):
                px,py,pz=int(cx)*16+int(ix),int(iy)-128,int(cz)*16+int(iz);b=r['names'][int(before[iy,iz,ix])];counts['cells']+=1
                if b.split('[')[0]not in ALLOWED:bad.append([px,py,pz,b]);counts['protected_cells_changed']+=1
                if oldwalk[pz-az,px-ax]:counts['old_public_cells_changed']+=1
                if(px,py,pz)in existing_devices:counts['old_devices_changed']+=1
                if not(declared[0]<=px<=declared[3]and declared[1]<=py<=declared[4]and declared[2]<=pz<=declared[5]):counts['outside_declared_volume']+=1
        e.regions.clear()
    if counts['cells']!=m['cells']:errors.append('cell count mismatch')
    if bad:errors.append('protected original block changed')
    if counts['old_public_cells_changed']:errors.append('existing public column changed')
    if counts['old_devices_changed']:errors.append('existing device changed')
    if counts['outside_declared_volume']:errors.append('change outside declared station volume')
    from verify_hakone_network_candidate import PAVEMENT
    floors=PAVEMENT|{'projectseele:station_tactile_warning'}
    nodes={};heads=[];floor_errors=[]
    for px,pz,g2 in d['public_columns']:
        py=(g2+1)//2
        floor=e.state(px,py,pz)
        if floor.split('[')[0]not in floors or ('type=bottom'in floor)!=(g2%2!=0):floor_errors.append([px,py,pz,floor]);continue
        if any(e.state(px,y,pz).split('[')[0]not in OPEN for y in(py+1,py+2)):heads.append([px,py,pz]);continue
        nodes[px,g2+2,pz]=1
    anchor=d['retained_street_anchor'];start=(anchor[0],round(anchor[1]*2),anchor[2]);parent={start:None}if start in nodes else{};queue=collections.deque(parent)
    while queue:
        px,g,pz=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dy in(-1,0,1):
                q=px+dx,g+dy,pz+dz
                if q in nodes and q not in parent:parent[q]=(px,g,pz);queue.append(q)
    unreachable=[list(q)for q in nodes if q not in parent]
    goalproof=[]
    for label,q in d['goals'].items():
        goal=q[0],round(q[1]*2),q[2];route=[];p=goal
        if goal in parent:
            while p is not None:route.append([p[0]+.5,p[1]/2,p[2]+.5]);p=parent[p]
            route.reverse()
        else:errors.append('unreachable goal '+label)
        goalproof.append(dict(name=label,reachable=bool(route),route=route))
    obstacles=[]
    sample_rows=json.loads((candidate/d.get('native_math_samples','native-straight-samples.json')).read_text('utf8'))
    derived_groups=[]
    for row in sample_rows:
        curve=LineString([(p[0],p[2])for p in row['points']]);envelope=rigid_envelope(curve);l,b,r,t=envelope.bounds;group=[]
        for pz in range(math.floor(b)-1,math.ceil(t)+1):
            for px in range(math.floor(l)-1,math.ceil(r)+1):
                if box(px,pz,px+1,pz+1).intersects(envelope):group.append((px,pz))
        derived_groups.append(group)
    if [set(g)for g in derived_groups]!=[set(map(tuple,g))for g in d['rail_columns']]:errors.append('declared swept vehicle columns differ from native samples')
    for group in derived_groups:
        for px,pz in group:
            for py in range(BASE,BASE+6):
                state=e.state(px,py,pz)
                if state.split('[')[0]not in OPEN:obstacles.append([px,py,pz,state])
    if obstacles:errors.append('rigid vehicle envelope obstructed')
    if floor_errors:errors.append('public bearing or floor height changed')
    if heads:errors.append('public headroom blocked')
    if unreachable:errors.append('public surfaces disconnected')
    # Every new solid cell must connect to measured ground through an actual
    # six-neighbour solid component, including hanging sign backings.
    from scipy.ndimage import label
    b=d['parts'][0]['bounds'];bounds=[b[0]-1,BASE-6,b[2]-1,b[3]+1,b[4]+1,b[5]+1]
    data,palette=voxel_box(e,bounds);solid=np.asarray([q.split('[')[0]not in OPEN for q in palette])[data]
    labels,components=label(solid);roots=set(map(int,np.unique(labels[0])));floating=[]
    for f in (candidate/'delta').glob('*.npz'):
        with np.load(f)as q:
            p=list(map(str,q['palette']));coords=q['coordinates'];ranges=q['ranges'];indices=q['indices'];after=q['after']
            for i,(cx,cz)in enumerate(coords):
                for j in range(int(ranges[i]),int(ranges[i+1])):
                    if p[int(after[j])].split('[')[0]in OPEN:continue
                    at=int(indices[j]);py=at//256-128;pz=int(cz)*16+(at%256)//16;px=int(cx)*16+at%16
                    if not(bounds[0]<=px<=bounds[3]and bounds[1]<=py<=bounds[4]and bounds[2]<=pz<=bounds[5]):continue
                    k=int(labels[py-bounds[1],pz-bounds[2],px-bounds[0]])
                    if k not in roots:floating.append([px,py,pz])
    if floating:errors.append('new solid component has no measured ground support')
    sign_changes=list(nbtlib.load(candidate/'block-entities.dat')['Changes']);sign_errors=[]
    if len(sign_changes)!=3:sign_errors.append('expected three complete sign payloads')
    for row in sign_changes:
        tag=row.get('After')
        if tag is None:sign_errors.append('missing After sign payload');continue
        px,py,pz=(int(tag[k])for k in('x','y','z'));state=e.state(px,py,pz)
        if(px,py,pz)in existing_devices or 'Before'in row:sign_errors.append('original device payload must remain untouched')
        if 'wall_sign'not in state or 'facing=south'not in state:sign_errors.append('sign state mismatch')
        if e.state(px,py,pz-1).split('[')[0]in OPEN:sign_errors.append('sign backing missing')
        if '鴨宮'not in str(tag):sign_errors.append('station title missing from sign')
    if sign_errors:errors.append('sign payload/backing verification failed')
    proof=dict(errors=errors,cells=counts['cells'],protected_original_changes=counts['protected_cells_changed'],old_public_changes=counts['old_public_cells_changed'],nodes=len(nodes),reachable_nodes=len(parent),unreachable=unreachable[:80],floor_failures=floor_errors[:30],headroom_failures=heads[:30],rigid_vehicle_envelope_obstacles=obstacles[:40],floating_new_solids=floating[:40],sign_errors=sign_errors,goals=goalproof,native_registry_pending=True,all_line_vehicle_sweep_complete=False,world_written=False)
    dump(candidate/'offline-verification.json',proof)
    print('Offline checks:',len(errors),'errors;',len(parent),'/',len(nodes),'reachable;',len(obstacles),'vehicle envelope obstacles',flush=True)
    if errors:raise ValueError(errors)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','authority','site','native-input','samples','out'):p.add_argument('--'+key,type=Path,required=True)
    author(p.parse_args())
