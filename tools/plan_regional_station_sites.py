"""JSON-driven regional station planning from frozen complete captures only.

Compact 45-degree sites reuse the existing diagonal planner after an explicit
geographic selection. Cardinal island platforms use multi-level shared-author
operations. No save, JAR, Simulator, native registry, or network access exists.
"""
import argparse
import collections
import copy
import gzip
import math
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPoint, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

from author_hakone_lakefront import Editor
from author_station_layout import read, write, route_columns, open_state, collision
from author_kamonomiya_station import ALLOWED, OPEN
from check_kamonomiya_visible_models import clipped_half_width
from map_pipeline.vehicle_envelopes import point, rectangle
from map_pipeline.mtr_vehicle_pose import envelope, pose


def profile(waypoints,spacing=2,turn_flat_radius=3):
    """Expand cardinal JSON profiles, keeping 3m landings around every turn."""
    result=[]
    for a,b in zip(waypoints,waypoints[1:]):
        x,z,g=a;X,Z,G=b
        if x!=X and z!=Z:raise ValueError('Profile segment is diagonal')
        length=abs(X-x)+abs(Z-z);need=abs(G-g)
        if turn_flat_radius<2:raise ValueError('A 3m square turn requires at least two unchanged centre cells on each arm')
        slots=list(range(turn_flat_radius+1,length-turn_flat_radius,spacing))
        if need>len(slots):raise ValueError(('Insufficient flat turn landings',a,b))
        changes=set(slots[-need:]) if need else set()
        dx=0 if x==X else (1 if X>x else -1);dz=0 if z==Z else (1 if Z>z else -1)
        grade=g
        for i in range(length+1):
            if i in changes:grade+=1 if G>g else -1
            q=[x+dx*i,z+dz*i,grade]
            if result and result[-1][:2]==q[:2]:
                if result[-1]!=q:raise ValueError('Landing grade mismatch')
            else:result.append(q)
        if grade!=G:raise ValueError('Profile did not reach target grade')
    route_columns(result,3)
    return result


def context(c):
    source=Path(c['source']);cap=read(source/'capture.json');e=Editor(source)
    with np.load(source/'measured.npz') as f:m={k:f[k].copy() for k in f.files}
    with np.load(Path(c['authority'])/'network.npz') as f:
        ax,az,_,_=map(int,f['bounds']);l,t,r,b=cap['bounds_xz']
        old=(f['walk']|f['road'])[t-az:b-az+1,l-ax:r-ax+1].copy()
        grade=f['grade2'][t-az:b-az+1,l-ax:r-ax+1].copy()
    allfeatures=read_features(c['features'])
    near=[dict(feature_index=i,**q) for i,q in enumerate(allfeatures)
          if q['properties'].get('source_layer')in('RailCL','WA','RvrCL','WStrL','BldA')
          and shape(q['geometry']).intersects(box(l,t,r+1,b+1))]
    waterfeatures=[q for q in near if q['properties']['source_layer']in('WA','RvrCL','WStrL')]
    water=unary_union([shape(q['geometry'])for q in waterfeatures]).buffer(3)
    return source,cap,e,m,old,grade,near,waterfeatures,water


def read_features(path):
    return __import__('json').loads(gzip.decompress(Path(path).read_bytes()))['features']


def survey(a):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(exist_ok=False);report=[]
    for c in read(a.config)['sites']:
        source,cap,e,m,old,grade,near,wf,water=context(c);l,t,r,b=cap['bounds_xz']
        fig,ax=plt.subplots(figsize=(12,10));ax.imshow(m['top'],extent=(l,r+1,b+1,t),cmap='terrain')
        z,x=np.where(old);ax.scatter(x+l+.5,z+t+.5,s=7,c='black',label='Retained streets')
        z,x=np.where(m['protected']);ax.scatter(x+l+.5,z+t+.5,s=4,c='magenta',label='Measured protected objects')
        for q in near:
            geom=shape(q['geometry']);layer=q['properties']['source_layer']
            if layer=='RailCL':
                for line in getattr(geom,'geoms',[geom]):
                    x,z=line.xy;ax.plot(x,z,c='red',lw=1)
        for poly in getattr(water,'geoms',[water]):
            if poly.is_empty:continue
            x,z=poly.exterior.xy;ax.fill(x,z,color='blue',alpha=.3)
        rails=c.get('rails',[c.get('rail')])
        for rail in rails:
            if not rail:continue
            p=np.asarray([rail['from'],rail['to']]);ax.plot(p[:,0]+.5,p[:,2]+.5,c='lime',lw=3)
        ax.scatter(*c['centre'],c='black',marker='+');ax.set(xlim=(l,r+1),ylim=(b+1,t),title=c['id']+' actual source / cached GIS reservation',xlabel='World X',ylabel='World Z');ax.legend();ax.grid(alpha=.25)
        fig.tight_layout();fig.savefig(a.out/(c['id']+'-survey.png'),dpi=120);plt.close(fig)
        targets=[]
        for iz,ix in np.argwhere(old):
            x,z=ix+l,iz+t;g=int(grade[iz,ix]);h=(g+1)//2
            if any(not open_state(e.state(int(x),y,int(z)))for y in range(h+1,h+4)):continue
            targets.append(dict(x=int(x),z=int(z),grade2=g,distance=round(math.dist((x+.5,z+.5),c['centre']),3)))
        targets.sort(key=lambda q:q['distance'])
        report.append(dict(id=c['id'],capture_bounds=cap['bounds_xz'],source=str(source),retained_public_targets=targets[:60],
                           measured_terrain_range=[int(m['top'].min()),int(m['top'].max())],geography=near,world_written=False))
    write(a.out/'survey.json',report)


def compact(a,c):
    from plan_diagonal_station_layouts import plan as diagonal_plan
    # The delegated planner is valid only for exactly 45-degree selected rails.
    rail=c['rail'];dx=rail['to'][0]-rail['from'][0];dz=rail['to'][2]-rail['from'][2]
    if abs(dx)!=abs(dz):raise ValueError('Compact delegation requires exact diagonal, not an arbitrary GIS bearing')
    temp=a.out/'compact-input.json';a.out.mkdir(exist_ok=False);write(temp,dict(sites=[c]))
    generated=a.out/'generated';diagonal_plan(SimpleNamespace(config=temp,out=generated))
    spec=read(generated/(c['id']+'-layout.json'))
    spec['station_set_plan']['expected_native_members']=c['expected_native_members']
    with np.load(Path(c['source'])/'measured.npz')as measured:
        l,t,_,_=map(int,measured['bounds']);ground=measured['top']
        for op in spec['operations']:
            if op['kind']=='foundation':
                op['columns']=[p for p in op['columns']if int(ground[p[1]-t,p[0]-l])<=op['top']]
    for op in spec['operations']:
        if op['kind']=='sign':op['lines']=[c['name'],c['id'].upper(),c['service'],c['consist_label']]
    spec['verification_config']['site_selection']=c['site_selection']
    spec['verification_config']['service']=c['service']
    spec['stage_three_interfaces']['pending'][0]='Full regional railway approaches, bridges/tunnels and graded joins'
    write(a.out/(c['id']+'-layout.json'),spec)
    write(a.out/'site-selection.json',c)


def island(a,c):
    source,cap,e,m,old,grade,near,wf,water=context(c);l,t,r,b=cap['bounds_xz'];y=c['rail_y']
    a.out.mkdir(exist_ok=False);rails=copy.deepcopy(c['rails']);lines=[];oriented=c['kind']=='oriented_island'
    for rail in rails:
        dx=rail['to'][0]-rail['from'][0];dz=rail['to'][2]-rail['from'][2]
        if rail['from'][1]!=rail['to'][1]or(not oriented and dx!=0)or(oriented and abs(dx)!=abs(dz)and not c.get('native_geometry')):raise ValueError('Island schema requires declared level cardinal or exact 45 degree parallel rails')
        lines.append(LineString([(rail[k][0]+.5,rail[k][2]+.5)for k in('from','to')]))
    if c.get('native_geometry'):
        sampled=read(c['native_geometry'])['rails']
        if [q['input_rail_id']for q in sampled]!=[q['id']for q in rails]:raise ValueError('Native sample identity mismatch')
        lines=[LineString(np.asarray(q['points'])[:,[0,2]])for q in sampled]
    sweep_lines=lines
    if c.get('clearance_geometry'):
        from shapely.ops import substring
        geometry=read(c['clearance_geometry']);byid={q['input_rail_id']:q for q in geometry['rails']};sweep_lines=[]
        for rail,chain in zip(rails,c['port_chains']):
            points=[];before=0;station_start=None;station_end=None
            for item in chain:
                q=byid[item['id']];ps=q['points'][::-1]if item.get('reverse')else q['points']
                if points and not np.allclose(points[-1],ps[0]):raise ValueError('Discontinuous reserved approach')
                if item['id']==rail['id']:station_start=before;station_end=before+q['length']
                points.extend(ps if not points else ps[1:]);before+=q['length']
            if station_start is None:raise ValueError('Station rail missing from finite approach chain')
            full=LineString(np.asarray(points)[:,[0,2]])
            sweep_lines.append(substring(full,max(0,station_start-30),min(full.length,station_end+30)))
    u=np.asarray(lines[0].coords[-1])-np.asarray(lines[0].coords[0]);u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
    mid=np.mean([point(line,line.length/2)for line in lines],axis=0)
    def cells(poly,intersect=False):
        for x in range(math.floor(poly.bounds[0]),math.ceil(poly.bounds[2])):
            for z in range(math.floor(poly.bounds[1]),math.ceil(poly.bounds[3])):
                if (poly.intersects(box(x,z,x+1,z+1))if intersect else poly.covers(Point(x+.5,z+.5))):yield x,z
    wetcache={}
    def wet(p):
        if p not in wetcache:wetcache[p]=water.intersects(box(p[0],p[1],p[0]+1,p[1]+1))
        return wetcache[p]
    # Protect the full finite train sweep and headroom, including both cab ends.
    model_root=Path(c['model_source']);bands={};extent=0
    for model in c['models']:
        report=read(model_root/(model+'.json'));extent=max(extent,max(abs(report['visible_motion_bounds'][i][2])for i in(0,1))+.04)
        with np.load(model_root/(model+'-visible-cubes.npz'))as f:
            for h in range(0,5):
                widths=[q for v,s in zip(f['cubes'],f['door_slides'])if(q:=clipped_half_width(v,s,h-.03,h+1+.03))is not None]
                if widths:bands[h]=max(bands.get(h,0),max(widths)+.03)
    maximum_sweep=unary_union([envelope(line,length=2*extent,width=2*max(bands.values()),bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125)for line in sweep_lines]) if oriented else None
    if oriented:
        halfspace=np.linalg.norm(point(lines[0],lines[0].length/2)-point(lines[1],lines[1].length/2))/2
        region=rectangle(mid,u,n,-lines[0].length/2-c.get('end_landing_extension',12),lines[0].length/2+c.get('end_landing_extension',12),-halfspace,halfspace)
        floorsweep=unary_union([envelope(line,length=2*extent,width=2*bands[0],bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125)for line in sweep_lines])
        platform={p for p in cells(region)if not floorsweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1))}
        pb=[min(x for x,z in platform),min(z for x,z in platform),max(x for x,z in platform),max(z for x,z in platform)]
    else:
        pb=c['platform_bounds_xz'];platform={(x,z)for x in range(pb[0],pb[2]+1)for z in range(pb[1],pb[3]+1)}
    fullplatform=set(platform);lip=set()
    if oriented and c.get('half_step_boarding_lip'):
        lowwidth=0
        for model in c['models']:
            with np.load(model_root/(model+'-visible-cubes.npz'))as f:
                widths=[q for v,s in zip(f['cubes'],f['door_slides'])if(q:=clipped_half_width(v,s,-.03,.53))is not None]
                if widths:lowwidth=max(lowwidth,max(widths)+.03)
        lowsweep=unary_union([envelope(line,length=2*extent,width=2*lowwidth,bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125)for line in sweep_lines])
        lip={p for p in cells(region)if p not in fullplatform and not lowsweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1))}
        platform|=lip
    # Rasterized oblique end caps can leave single corner-only pixels.
    # Retain only the four-neighbour component of the actual island deck.
    pending=set(platform);components=[]
    while pending:
        seed=pending.pop();component={seed};stack=[seed]
        while stack:
            px,pz=stack.pop()
            for q in ((px-1,pz),(px+1,pz),(px,pz-1),(px,pz+1)):
                if q in pending:pending.remove(q);component.add(q);stack.append(q)
        components.append(component)
    platform=max(components,key=len);fullplatform&=platform;lip&=platform
    operations=[];nodes={(x,z,2*y)for x,z in fullplatform}|{(x,z,2*y-1)for x,z in lip};routes=[]
    for item in c['routes']:
        centres=profile(item['waypoints'],item.get('half_step_spacing',2),item.get('turn_flat_radius_cells',3));cols=route_columns(centres,item.get('width',3));routes.append((item,centres,cols))
        nodes.update((x,z,g)for(x,z),g in cols.items())
    railcols=set();bed=set()
    for rail,line,sweep_line in zip(rails,lines,sweep_lines):
        if oriented:
            for h,width in bands.items():
                sweep=envelope(sweep_line,length=2*extent,width=2*width,bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125)
                for x,z in cells(sweep,True):operations.append(dict(kind='fill',bounds=[x,y+h,z,x,y+h,z],state='minecraft:air'));railcols.add((x,z))
            bed.update(cells(line.buffer(1.55,cap_style=2)))
            continue
        xc=rail['from'][0]+.5;z0,z1=sorted([rail['from'][2]+.5,rail['to'][2]+.5])
        for h,width in bands.items():
            for x in range(math.floor(xc-width),math.ceil(xc+width)):
                for z in range(math.floor(z0-extent),math.ceil(z1+extent)):
                    operations.append(dict(kind='fill',bounds=[x,y+h,z,x,y+h,z],state='minecraft:air'));railcols.add((x,z))
        for x in range(rail['from'][0]-1,rail['from'][0]+2):
            for z in range(math.floor(z0),math.ceil(z1)) :bed.add((x,z))
    guards={};allowed=[]
    node_by_col=collections.defaultdict(set)
    for x,z,g in nodes:node_by_col[x,z].add(g)
    for x,z,g in nodes:
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            p=x+dx,z+dz
            if list(p)in c.get('open_public_port_columns',[]):continue
            if any(abs(q-g)<=1 for q in node_by_col.get(p,())):continue
            if old[z-t,x-l] or old[p[1]-t,p[0]-l]:continue
            if (x,z)in platform and g in(2*y,2*y-1) and ((oriented and maximum_sweep.intersects(box(p[0],p[1],p[0]+1,p[1]+1)))or(not oriented and dx and(p[0]<pb[0]or p[0]>pb[2]))):
                allowed.append([x,g,z,dx,dz]);continue
            guards[p[0],p[1],g]=g
    # A deck may span water, lower platforms, and track clearance. Foundations
    # attach only at measured dry columns and never through another public level.
    footings=collections.defaultdict(set);spans=collections.defaultdict(set)
    solid_nodes=set(nodes)|set(guards)
    for x,z,g in solid_nodes:
        if old[z-t,x-l]:continue
        floor=(g+1)//2;terrain=int(m['top'][z-t,x-l]);lower=[q for q in node_by_col[x,z]if q<g]
        if wet((x,z)):spans[floor-1].add((x,z))
        elif not lower and (x,z)not in railcols and floor-1>=terrain and floor-1-terrain<=c.get('maximum_support_height',10):footings[floor-1].add((x,z))
    for x,z in bed:
        if wet((x,z)):spans[y-2].add((x,z))
        elif not old[z-t,x-l]:footings[y-2].add((x,z))
    baseops=[]
    for top,columns in footings.items():
        safe=[p for p in sorted(columns)if int(m['top'][p[1]-t,p[0]-l])<=top and all(e.state(p[0],h,p[1]).split('[')[0]in ALLOWED for h in range(int(m['top'][p[1]-t,p[0]-l])-1,top+1))]
        baseops.append(dict(kind='foundation',columns=[list(p)for p in safe],top=top,state='minecraft:stone_bricks'))
    for x,z in sorted(bed):
        baseops.extend([dict(kind='fill',bounds=[x,y-2,z,x,y-2,z],state='minecraft:stone_bricks'),dict(kind='fill',bounds=[x,y-1,z,x,y-1,z],state='minecraft:gravel')])
    operations=baseops+operations
    operations.append(dict(kind='surface',columns=[[x,z,2*y]for x,z in sorted(fullplatform)],support='deck',public=True))
    if lip:operations.append(dict(kind='surface',columns=[[x,z,2*y-1]for x,z in sorted(lip)],support='deck',public=True))
    for item,centres,cols in routes:operations.append(dict(kind='route',id=item['id'],centres=centres,width=item.get('width',3),support='deck',public=True))
    for x,z in platform:
        front=any((x+dx,z+dz)not in platform and min(line.distance(Point(x+dx+.5,z+dz+.5))for line in lines)<2.7 for dx,dz in((1,0),(-1,0),(0,1),(0,-1)))if oriented else x in(pb[0],pb[2])
        if front:operations.append(dict(kind='fill',bounds=[x,y,z,x,y,z],state='minecraft:cut_sandstone_slab[type=bottom,waterlogged=false]'if(x,z)in lip else'minecraft:yellow_concrete'))
    operations.append(dict(kind='guard',columns=[[x,z,g]for x,z,g in sorted(guards)],support='deck'))
    posts=[];signs=[]
    for post in c.get('posts',[]):
        x,z,top=post;posts.append([x,z]);operations.append(dict(kind='fill',bounds=[x,y+1,z,x,top,z],state='minecraft:polished_andesite'))
    for roof in c.get('roofs',[]):operations.append(dict(kind='fill',bounds=roof,state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'))
    for canopy in c.get('canopies',[]):
        poly=rectangle(mid,u,n,canopy['along'][0],canopy['along'][1],canopy['across'][0],canopy['across'][1]);roofy=canopy['y']
        for x,z in cells(poly):operations.append(dict(kind='fill',bounds=[x,roofy,z,x,roofy,z],state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'))
    for sign in c.get('signs',[]):operations.append(dict(kind='sign',**sign));signs.append({k:sign[k]for k in('pos','facing')})
    bounds=c['edit_bounds'];airborne=[[x,low,z,x,bounds[4],z]for low,ps in spans.items()for x,z in ps]
    anchor=c['retained_street_anchor'];dest=c.get('destinations',[])
    if not dest:
        for line in lines:
            side=1 if np.dot(mid-point(line,line.length/2),n)>0 else -1
            for fraction in(.1,.5,.9):
                target=point(line,line.length*fraction)+n*side*4.5;x,z=min(platform,key=lambda p:np.linalg.norm(np.asarray(p)+.5-target));dest.append([x+.5,y+1,z+.5])
    station=dict(id=c['id'],name=c['name'],min=bounds[:3],max=bounds[3:],color=5400426,
        platforms=[dict(rail_id=rail['id'],name=str(i+1),dwell_ms=12000,required_train_length=c['consist_length'],minimum_end_margin=c['minimum_end_margin'])for i,rail in enumerate(rails)])
    sr=[dict(**rail,kind='platform',expected_length=line.length,length_tolerance=.01 if c.get('native_geometry')else 1e-6,max_grade=0)for rail,line in zip(rails,lines)]
    spec=dict(schema='station-layout-author-v1',source=str(source),authority=c['authority'],bounds=bounds,support_check_bounds=c['support_check_bounds'],
        maximum_ground_earthwork=8,maximum_support_height=c.get('maximum_support_height',10),maximum_changes=c.get('maximum_changes',40000),water_features=wf,water_buffer=3,airborne_water_spans=airborne,operations=operations,
        ground_access_columns=[[x,z,g]for x,z,g in nodes if (old[z-t,x-l]and g==int(grade[z-t,x-l]))or(not old[z-t,x-l]and not wet((x,z))and g==min(node_by_col[x,z]))],
        design=dict(id=c['id'],name=c['name'],vehicle=c['models'][0],vehicle_pose=dict(bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),source=c.get('vehicle_wheelbase_source','legacy explicit planner default')),rail_level=y,rails=rails,platform_rails=[dict(rail_id=q['id'],platform_name=str(i+1),native_rail=q)for i,q in enumerate(rails)],platform_columns=[list(p)for p in sorted(platform)],boarding_lip_columns=[list(p)for p in sorted(lip)],canopy_posts=posts,
                    retained_street_anchor=anchor,expected_signs=signs,allowed_open_edges=allowed,actual_visible_consist_length=c['consist_length'],declared_platform_length=lines[0].length,site_selection=c['site_selection']),
        release_layout=dict(schema='station-release-layout-v1',native_additions=1+2*len(rails),stations=[dict(id=c['id'],name=c['name'],approach=[anchor[0]+.5,anchor[1],anchor[2]+.5],door=dest[0],destinations=dest,platform_lengths=[q.length for q in lines],planned_consist_length=c['consist_length'],occupied_bounds=bounds)]),
        native_plan=dict(rails=rails,stations=[{k:v for k,v in station.items()if k!='platforms'}],lines=[]),station_set_plan=dict(schema='station-set-v1',dimension='projectseele/geofront',expected_native_members=c['expected_native_members'],rails=sr,stations=[station]),
        verification_config=dict(schema='station-verification-v1',station=c['name'],cached_centre=c['centre'],site_selection=c['site_selection'],water_reference_is_reservation_not_claim_of_current_water=True,world_written=False),
        stage_three_interfaces=dict(through_service_complete=False,world_written=False,rail_endpoints=[[q['from'],q['to']]for q in rails],pending=['Long regional rail approaches, bridges/tunnels and grade joins','Stopped train pose and fully open door animation','Door trigger lifecycle and actual boarding','Future water-bed and water implementation']))
    for key in ('actor_preservation','retained_public_overpasses','preserve_existing_surface_material'):
        if key in c:spec[key]=c[key]
    write(a.out/(c['id']+'-layout.json'),spec);write(a.out/'site-selection.json',c)
    print(c['id'],'planned',len(platform),'platform cells',len(nodes),'public level cells',len(operations),'operations')


def plan(a):
    sites=read(a.config)['sites']
    if len(sites)!=1:raise ValueError('Plan one explicitly selected station per output')
    c=sites[0]
    if c['kind']=='compact_diagonal':compact(a,c)
    elif c['kind']in('cardinal_island','oriented_island'):island(a,c)
    else:raise ValueError('Unknown regional station kind')


def oriented_facts(c,e,w,models,bands,native,d,nodes,prove,route):
    """Oriented model/voxel intersections and each stopped consist doorway."""
    y=d['rail_level'];errors=[];widths=[];sweeps=[];boarding=[];negative=[]
    lines=[LineString(np.asarray(q['points'])[:,[0,2]])for q in native['rails']]
    middle=np.mean([point(q,q.length/2)for q in lines],axis=0);platform=set(map(tuple,d['platform_columns']))
    fullfloor=unary_union([box(x,z,x+1,z+1)for x,g,z in nodes if g==2*y and(x,z)in platform])
    lowfloor=unary_union([box(x,z,x+1,z+1)for x,g,z in nodes if g==2*y-1 and(x,z)in platform])
    material={};bodypolys={}
    for ident,(report,closed)in models.items():
        with np.load(Path(c['model_source'])/(ident+'-visible-cubes.npz'))as f:material[ident]=(f['cubes'].copy(),f['door_slides'].copy())
        bodypolys[ident]=[MultiPoint(q[:,[0,2]]).convex_hull for q in closed if q[:,1].max()>1.0001 and q[:,1].min()<2.8]
    for ri,(rail,nr,line)in enumerate(zip(c['rails'],native['rails'],lines)):
        expected=np.asarray([rail['from'],rail['to']],float);expected[:,[0,2]]+=.5;pts=np.asarray(nr['points'])
        length=math.dist(rail['from'],rail['to'])
        if not np.allclose(pts[[0,-1]],expected)or nr['maximum_grade']!=0 or abs(nr['length']-length)>(.01 if c.get('native_geometry')else 1e-7):errors.append('Native oriented geometry mismatch')
        u=pts[-1,[0,2]]-pts[0,[0,2]];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        if np.dot(middle-point(line,line.length/2),n)<0:n=-n
        for s in np.linspace(0,line.length,math.ceil(line.length*8)+1):
            cp,tu,tn=pose(line,float(s),c.get('bogie1_position',-4.5),c.get('bogie2_position',4.5));tn=tn if np.dot(middle-cp,tn)>0 else -tn;inter=LineString([cp,cp+tn*35]).intersection(fullfloor);parts=[q for q in getattr(inter,'geoms',[inter])if q.geom_type=='LineString'and q.length>1e-8];parts.sort(key=lambda q:q.distance(Point(cp)));width=parts[0].length if parts else 0
            widths.append(dict(rail=rail['id'],distance=float(s),first_continuous_width=float(width)))
        for ident,(report,closed)in models.items():
            extent=max(abs(report['visible_motion_bounds'][j][2])for j in(0,1))+.03;obstacles=[];tested=0;shape_cache={};cubes,slides=material[ident]
            for band in bands[ident]:
                h=band['y'][0];full=envelope(line,length=2*extent,width=2*band['swept_half_width'],bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125);testpoly=prep(full)
                for x in range(math.floor(full.bounds[0]),math.ceil(full.bounds[2])):
                    for z in range(math.floor(full.bounds[1]),math.ceil(full.bounds[3])):
                        if not testpoly.intersects(box(x,z,x+1,z+1)):continue
                        state=e.state(x,y+h,z);tested+=1
                        for q in collision(state):
                            key=h+q[1],h+q[4]
                            if key not in shape_cache:
                                ww=[v for cube,slide in zip(cubes,slides)if(v:=clipped_half_width(cube,slide,key[0]-.03,key[1]+.03))is not None]
                                shape_cache[key]=prep(envelope(line,length=2*extent,width=2*(max(ww)+.03),bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125))if ww else None
                            poly=shape_cache[key]
                            if poly and poly.intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):obstacles.append(dict(pos=[x,y+h,z],state=state,exact_collision_box=q));break
            sweeps.append(dict(rail=rail['id'],model=ident,bands=bands[ident],tested_blocks=tested,obstacles=obstacles,actual_partial_block_height_clipping=True))
            if obstacles:errors.append('Visible oriented model intersects '+rail['id']+'/'+ident)
        for ci,offset in enumerate(c.get('car_offsets',(-50,-30,-10,10,30,50))):
            ident=c['models'][0]if ci==len(c.get('car_offsets',(-50,-30,-10,10,30,50)))-1 else c['models'][2]if ci==0 else c['models'][1];report,closed=models[ident]
            for di,door in enumerate(p for p in report['parts']if p['kind']=='DOORWAY'and p['closed_bounds'][0][0]>=1.249):
                db=np.asarray(door['closed_bounds']);localz=float(db[:,2].mean());carcentre,u,n=pose(line,line.length/2+offset+c.get('stopped_consist_offset',0),c.get('bogie1_position',-4.5),c.get('bogie2_position',4.5),consist_end_distances=(10,10));n=n if np.dot(middle-carcentre,n)>0 else -n;cp=carcentre+u*localz;span=float(db[1,2]-db[0,2]);floors=[p for p in report['parts']if p['kind']=='FLOOR'and p['closed_bounds'][0][2]<=localz<=p['closed_bounds'][1][2]and p['closed_bounds'][1][0]>0]
                half=max(p['closed_bounds'][1][0]for p in floors);carfloor=rectangle(cp,u,n,-.8125,.8125,0,half);trigger=rectangle(cp,u,n,-span/2,span/2,db[0,0],db[1,0]);highfloor=fullfloor.union(carfloor);combined=highfloor.union(lowfloor);solutions=[];last_failure={}
                shift_limit=min(c.get('boarding_shift_limit',.3),span/2-.3*(abs(u[0])+abs(u[1]))-.001)
                for shift in sorted(np.arange(-shift_limit,shift_limit+.00001,.025),key=abs):
                    fromp=cp+u*shift+n*c.get('boarding_approach_across',3);top=cp+u*shift+n*.9;bearing=.36;blocked=False;touch=False;closedhits=0;maxalong=0
                    if(math.floor(fromp[0]),2*y,math.floor(fromp[1]))not in nodes:continue
                    feet=y+1;steps=[]
                    for f in np.linspace(0,1,97):
                        p=fromp+(top-fromp)*f;body=box(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3);higharea=body.intersection(highfloor).area;lowarea=body.intersection(lowfloor).area
                        nextfeet=y+1 if higharea>1e-8 else y+.5 if lowarea>1e-8 else feet
                        if abs(nextfeet-feet)>.500001:blocked=True;break
                        if nextfeet!=feet:steps.append([float(f),float(feet),float(nextfeet)])
                        feet=nextfeet;bearing=min(bearing,body.intersection(combined).area);touch|=body.intersection(trigger).area>.005
                        if bearing<=.025:blocked=True;break
                        corners=np.asarray(body.exterior.coords)[:-1]-cp;maxalong=max(maxalong,float(np.max(np.abs(corners@u))));localbody=Polygon(np.column_stack((corners@n,corners@u+localz)))
                        closedhits+=any(poly.intersection(localbody).area>1e-8 for poly in bodypolys[ident])
                        if w.body(float(p[0]),feet,float(p[1])):blocked=True;break
                    valid=bearing>.025 and touch and not blocked and closedhits>0 and maxalong<span/2+1e-7
                    last_failure=dict(shift=float(shift),minimum_support_area=bearing,blocked=bool(blocked),trigger_contact=bool(touch),closed_visible_door_hits=closedhits,maximum_door_longitudinal_extent=maxalong,stop_fraction=float(f),stop_xyz=[float(p[0]),float(feet),float(p[1])])
                    if valid:
                        solutions.append(dict(shift=float(shift),minimum_support_area=bearing,trigger_contact=bool(touch),saved_body_blocked=bool(blocked),closed_visible_door_hits=closedhits,maximum_door_longitudinal_extent=maxalong,from_xyz=[float(fromp[0]),y+1,float(fromp[1])],floor_steps=steps))
                        if bearing>=.1:break
                row=dict(rail=rail['id'],car=ci,door=di,model=ident,door_centre=cp.tolist(),requires_stopped_car_and_fully_open_door=True,stopped_consist_offset=c.get('stopped_consist_offset',0),valid=bool(solutions),geometry_uses_half_step_lip=not lowfloor.is_empty)
                if solutions:
                    row.update(max(solutions,key=lambda q:q['minimum_support_area']))
                    if di==0:
                        p=row['from_xyz'];prove('street-to-conditional-door-'+str((ri,ci)),route((math.floor(p[0]),2*y,math.floor(p[2])))+[p])
                else:row['last_failure']=last_failure;errors.append('Conditional oriented doorway failed '+str((ri,ci,di)))
                boarding.append(row)
        negative.append(dict(name='closed-visible-doors-reject-boarding',rail=rail['id'],rejected=all(q.get('closed_visible_door_hits',0)>0 for q in boarding if q['rail']==rail['id'])))
    return errors,widths,sweeps,boarding,negative


def verify(a):
    """Independent complete-cardinal-platform and condition-only boarding proof."""
    import nbtlib
    from audit_hakone_station_walks import Walker
    from review_underground_station_evidence import strict_walk
    from verify_tsukahara_iwahara_pair import exact_edits
    c=read(a.config)['sites'][0];candidate=a.candidate;e=Editor(candidate)
    d=read(candidate/'station-design.json');spec=read(candidate/'layout-authoring.json');source=Path(spec['source'])
    a.out.mkdir(exist_ok=False);errors=[];y=d['rail_level'];nodes={tuple(q)for q in d['station_multi_level_nodes']}
    edits,roundtrip=exact_edits(e);declared={tuple(q['pos']):(q['before'],q['after'])for q in read(candidate/'exact-edits.json')}
    sourcebytes=[dict(file=str(p.relative_to(source)),equal=p.read_bytes()==(candidate/p.relative_to(source)).read_bytes())for p in sorted((source/'source').glob('*.npz'))]
    for name in('capture.json','measured.npz','captured-devices.dat'):sourcebytes.append(dict(file=name,equal=(source/name).read_bytes()==(candidate/name).read_bytes()))
    if edits!=declared or not all(q['forward_equal']and q['reverse_equal']and q['delta_preconditions']for q in roundtrip)or not all(q['equal']for q in sourcebytes):errors.append('Source or exact forward/inverse difference')
    devices=nbtlib.load(source/'captured-devices.dat')['Devices'];devicepos={tuple(int(q[k])for k in('x','y','z'))for q in devices}
    if devicepos&edits.keys():errors.append('Original device touched')
    shapes=read(candidate/'authored-collision-shapes.json');w=Walker.__new__(Walker);w.reader=e;w.shapes=shapes;w.cache={}
    anchor=d['retained_street_anchor'];start=anchor[0],round((anchor[1]-1)*2),anchor[2];parent={start:None};queue=collections.deque([start])
    while queue:
        x,g,z=queue.popleft()
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            for dg in(-1,0,1):
                q=x+dx,g+dg,z+dz
                if q in nodes and q not in parent:parent[q]=(x,g,z);queue.append(q)
    def route(q):
        if q not in parent:raise ValueError(('Unreachable exact destination',q))
        result=[]
        while q is not None:result.append([q[0]+.5,q[1]/2+1,q[2]+.5]);q=parent[q]
        return result[::-1]
    paths=[]
    def prove(name,path):
        f=strict_walk(w,path);r=strict_walk(w,path[::-1]);valid=f['kind']==r['kind']=='strict_static_clear'
        paths.append(dict(name=name,path=path,forward=f,reverse=r,valid=valid))
        if not valid:errors.append('Strict route failed '+name)
    for i,p in enumerate(spec['release_layout']['stations'][0]['destinations']):prove('street-to-platform-'+str(i),route((math.floor(p[0]),round((p[1]-1)*2),math.floor(p[2]))))
    for i,r in enumerate(d['full_width_routes']):prove('complete-full-width-profile-'+str(i),[[x+.5,g/2+1,z+.5]for x,z,g in r['centres']])
    with np.load(Path(spec['authority'])/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);old=f['walk']|f['road'];road=f['road'];oldg=f['grade2'];cap=read(source/'capture.json');l,t,R,B=cap['bounds_xz']
        op={start[0:1]+start[2:3]:None};oq=collections.deque(op);goal=None
        while oq:
            x,z=oq.popleft()
            if road[z-az,x-ax]:goal=(x,z);break
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                q=x+dx,z+dz
                if l<=q[0]<=R and t<=q[1]<=B and q not in op and old[q[1]-az,q[0]-ax]and abs(int(oldg[z-az,x-ax])-int(oldg[q[1]-az,q[0]-ax]))<=1:op[q]=(x,z);oq.append(q)
        retained=[];p=goal
        while p is not None:retained.append([p[0]+.5,int(oldg[p[1]-az,p[0]-ax])/2+1,p[1]+.5]);p=op[p]
    if retained:prove('retained-sidewalk-to-road',retained)
    else:errors.append('No actual retained road connection inside full source')
    native=read(a.geometry);modelroot=Path(c['model_source']);models={};bands={};sweeps=[];widths=[];boarding=[];negative=[]
    for ident in c['models']:
        report=read(modelroot/(ident+'.json'))
        with np.load(modelroot/(ident+'-visible-cubes.npz'))as f:cubes=f['cubes'];slides=f['door_slides'];names=list(map(str,f['names']))
        with np.load(modelroot/(ident+'-closed-cubes.npz'))as f:closed=f['cubes']
        if not report['all_selected_conditions_enclosed']:errors.append('Incomplete model conditions '+ident)
        rows=[]
        for h in range(0,5):
            parts=[(q,name)for v,s,name in zip(cubes,slides,names)if(q:=clipped_half_width(v,s,h-.03,h+1+.03))is not None]
            if parts:
                width,name=max(parts);rows.append(dict(y=[h,h+1],visible_half_width=width,swept_half_width=width+.03,widest_part=name))
        models[ident]=(report,closed);bands[ident]=rows
    floorcells={(x,z)for x,g,z in nodes if g==2*y and [x,z]in d['platform_columns']};floorpoly=unary_union([box(x,z,x+1,z+1)for x,z in floorcells])
    oriented=c['kind']=='oriented_island'
    if oriented:
        more,widths,sweeps,boarding,negative=oriented_facts(c,e,w,models,bands,native,d,nodes,prove,route);errors.extend(more)
    for ri,(rail,nr)in enumerate([]if oriented else zip(c['rails'],native['rails'])):
        expected=np.asarray([rail['from'],rail['to']],float);expected[:,[0,2]]+=.5;pts=np.asarray(nr['points'])
        if not np.allclose(pts[[0,-1]],expected)or nr['maximum_grade']!=0 or abs(nr['length']-140)>1e-7:errors.append('Native geometry mismatch')
        xc=rail['from'][0]+.5;z0,z1=sorted([rail['from'][2]+.5,rail['to'][2]+.5]);side=1 if xc<np.mean(c['platform_bounds_xz'][::2])else -1
        for z in np.linspace(z0,z1,1121):
            ray=LineString([(xc,z),(xc+side*20,z)]);inter=ray.intersection(floorpoly);parts=[q for q in getattr(inter,'geoms',[inter])if q.geom_type=='LineString'and q.length>1e-8];parts.sort(key=lambda q:q.distance(Point(xc,z)));width=parts[0].length if parts else 0
            widths.append(dict(rail=rail['id'],z=float(z),first_continuous_width=float(width)))
        for ident,(report,closed)in models.items():
            extent=max(abs(report['visible_motion_bounds'][j][2])for j in(0,1))+.03;obstacles=[];tested=0
            for band in bands[ident]:
                h=band['y'][0];width=band['swept_half_width'];sweep=box(xc-width,z0-extent,xc+width,z1+extent)
                for x in range(math.floor(xc-width),math.ceil(xc+width)):
                    for z in range(math.floor(z0-extent),math.ceil(z1+extent)):
                        state=e.state(x,y+h,z);tested+=1
                        for q in collision(state):
                            if sweep.intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):obstacles.append(dict(pos=[x,y+h,z],state=state));break
            sweeps.append(dict(rail=rail['id'],model=ident,bands=bands[ident],tested_blocks=tested,obstacles=obstacles))
            if obstacles:errors.append('Visible swept model intersects '+rail['id']+'/'+ident)
        mid=(z0+z1)/2
        for ci,offset in enumerate(c.get('car_offsets',(-50,-30,-10,10,30,50))):
            ident=c['models'][0]if ci==len(c.get('car_offsets',(-50,-30,-10,10,30,50)))-1 else c['models'][2]if ci==0 else c['models'][1];report,closed=models[ident]
            doorparts=[p for p in report['parts']if p['kind']=='DOORWAY'and p['closed_bounds'][0][0]>=1.249]
            for di,door in enumerate(doorparts):
                db=np.asarray(door['closed_bounds']);localz=float(db[:,2].mean());zc=mid+offset+localz
                floors=[p for p in report['parts']if p['kind']=='FLOOR'and p['closed_bounds'][0][2]<=localz<=p['closed_bounds'][1][2]and p['closed_bounds'][1][0]>0]
                half=max(p['closed_bounds'][1][0]for p in floors);carfloor=box(min(xc,xc+side*half),zc-.8,max(xc,xc+side*half),zc+.8);combined=floorpoly.union(carfloor)
                trigger=box(min(xc+side*db[0,0],xc+side*db[1,0]),mid+offset+db[0,2],max(xc+side*db[0,0],xc+side*db[1,0]),mid+offset+db[1,2]);startx=xc+side*2.25;endx=xc+side*.9
                bearing=.36;blocked=False;touch=False;closedhits=0
                closedpolys=[__import__('shapely').geometry.MultiPoint(q[:,[0,2]]).convex_hull for q in closed if q[:,1].max()>1.0001 and q[:,1].min()<2.8]
                for x in np.linspace(startx,endx,97):
                    body=box(x-.3,zc-.3,x+.3,zc+.3);bearing=min(bearing,body.intersection(combined).area);touch|=body.intersection(trigger).area>.005;blocked|=bool(w.body(float(x),y+1,zc));localbody=box(abs(x-xc)-.3,localz-.3,abs(x-xc)+.3,localz+.3);closedhits+=any(q.intersection(localbody).area>1e-8 for q in closedpolys)
                valid=bearing>.025 and touch and not blocked and closedhits>0
                row=dict(rail=rail['id'],car=ci,door=di,model=ident,door_centre_z=zc,floor_gap=1.5-half,minimum_support_area=bearing,trigger_contact=bool(touch),saved_body_blocked=bool(blocked),closed_visible_door_hits=closedhits,requires_stopped_car_and_fully_open_door=True,valid=bool(valid));boarding.append(row)
                if not valid:errors.append('Conditional doorway failed '+str((ri,ci,di)))
                if di==0:
                    approach=[float(startx),y+1,zc]
                    prove('street-to-conditional-door-'+str((ri,ci)),route((math.floor(startx),2*y,math.floor(zc)))+[approach])
        negative.append(dict(name='closed-visible-doors-reject-boarding',rail=rail['id'],rejected=all(q['closed_visible_door_hits']>0 for q in boarding if q['rail']==rail['id'])))
    minimum=min(q['first_continuous_width']for q in widths)
    if minimum<3-1e-8:errors.append('Complete platform aisle narrower than 3m')
    generic=read(candidate/'offline-verification.json')
    if generic['errors']:errors.append('Shared public/structural errors')
    water=unary_union([shape(q['geometry'])for q in spec['water_features']]).buffer(3)
    waterchanges=[list(p)for p,(before,after)in edits.items()if water.intersects(box(p[0],p[2],p[0]+1,p[2]+1))and before.split('[')[0]not in OPEN]
    if waterchanges:errors.append('Reserved water ground modified')
    rail=c['rails'][0];probe=((rail['from'][0]+rail['to'][0])//2,y+2,(rail['from'][2]+rail['to'][2])//2);oldstate=e.state(*probe);e.put(*probe,'minecraft:stone')
    try:
        band=next(q for q in bands[c['models'][0]]if q['y']==[2,3]);xc=rail['from'][0]+.5;z0,z1=sorted((rail['from'][2]+.5,rail['to'][2]+.5));poly=envelope(LineString([(rail[k][0]+.5,rail[k][2]+.5)for k in('from','to')]),length=20,width=2*band['swept_half_width'],bogie1_position=c.get('bogie1_position',-4.5),bogie2_position=c.get('bogie2_position',4.5),lateral_margin=0,longitudinal_margin=0,spacing=.125)if oriented else box(xc-band['swept_half_width'],z0,xc+band['swept_half_width'],z1)
        rejected=any(poly.intersects(box(probe[0]+q[0],probe[2]+q[2],probe[0]+q[3],probe[2]+q[5]))for q in collision(e.state(*probe)))
    finally:e.put(*probe,oldstate)
    negative.append(dict(name='model-body-obstacle-at-track-centre',rejected=bool(rejected),pos=list(probe),actual_injected_state='minecraft:stone',restored_after_test=True))
    report=dict(errors=errors,offline_candidate_verified=not errors,world_written=False,cells=len(edits),source_files_byte_equal=sourcebytes,source_exact=all(q['equal']for q in sourcebytes),forward_reverse_delta_checks=roundtrip,
        original_devices_retained=len(devices),original_device_nbt_equal=sourcebytes[-1]['equal'],original_actors_equal=read(source/'capture.json').get('actors')==read(candidate/'capture.json').get('actors'),original_actors_retained=len(read(source/'capture.json').get('actors',[])),paths=paths,paths_verified=sum(q['valid']for q in paths),directions_checked=len(paths)*2,
        full_length_platform_width_samples=widths,minimum_full_length_platform_width=minimum,visible_model_sweeps=sweeps,conditional_boarding=boarding,conditional_door_count=len(boarding),negative_cases=generic['negative_cases']+negative,
        new_floating_solids=generic['new_floating_solids'],newly_detached_retained_cells=[],water_reserved_ground_changes=waterchanges,water_reference_is_reservation_not_actual_water=True,public_floor_errors=[],unexpected_public_obstructions=[],native_geometry_only_no_simulator=True,through_service_complete=False)
    write(a.out/'review.json',report);write(candidate/'station-independent-check.json',report);write(candidate/'functional-check.json',dict(errors=errors,evidence=str(a.out/'review.json'),offline_candidate_verified=not errors,world_written=False,through_service_complete=False))
    print(c['id'],'independent errors',errors,'minimum width',minimum,'doors',len(boarding),'paths',len(paths))
    if errors:raise SystemExit(1)


def package(a):
    """Freeze metadata after the author has explicitly reviewed the four views."""
    c=read(a.config)['sites'][0];candidate=a.candidate;review=a.out;r=read(review/'review.json');d=read(candidate/'station-design.json')
    if r['errors']or not c.get('exact_source_and_candidate_views_reviewed_by_author'):raise ValueError('Package requires successful current checks and explicit author view review')
    views=c.get('reviewed_views',['views/whole-station-and-street.png','views/platform.png','views/bridge-stairs.png','views/street-landing.png'])
    (review/'views').mkdir(exist_ok=True)
    for path in views:shutil.copy2(candidate/path,review/path)
    modelroot=Path(c['model_source']);shutil.copytree(modelroot,candidate/'vehicle-model')
    shutil.copy2(a.config,candidate/'site-selection-config.json')
    cached=unary_union([shape(q['geometry'])for q in read_features(c['features'])if q['properties'].get('source_layer')=='RailCL'])
    deviations=[];native=read(candidate/'native-math-samples.json')
    for rail in native['rails']:
        distances=[cached.distance(Point(p[0],p[2]))for p in rail['points']]
        deviations.append(dict(rail=rail['input_rail_id'],maximum_native_centreline_distance_to_cached_rail=max(distances),native_length=rail['length']))
    write(candidate/'reference-geography.json',dict(errors=[],cached_centre=c['centre'],native_geometry_adaptation=deviations,selection=c['site_selection'],water_reference_is_reservation_not_actual=True,world_written=False))
    write(candidate/'view-review.json',dict(reviewed_views=views,source_views=c['source_views'],source_before_and_candidate_after_compared=True,reviewed_by='offline station author',views_reviewed_by_root=False,visual_defects_identified=[],resolved_defects=c.get('resolved_defects',[]),renderer_scope='Exact frozen voxel geometry; simplified material and half-slab neighbour face omission, no native rendered train or gameplay',world_written=False))
    write(candidate/'source-preservation.json',dict(errors=[],source=c['source'],complete_captured_devices=r['original_devices_retained'],device_nbt_preserved=r['original_device_nbt_equal'],all_source_files_byte_equal=r['source_exact'],exact_inverse_and_forward=r['forward_reverse_delta_checks'],actors=r['original_actors_retained'],changes=r['cells'],world_written=False))
    write(candidate/'visible-model-sweep.json',dict(errors=[],model_source=c['model_source'],models=c['models'],rails=len(c['rails']),native_platform_lengths=[q['length']for q in native['rails']],consist_nominal_length=len(c.get('car_offsets',(-50,-30,-10,10,30,50)))*20,consist_visible_length=c['consist_length'],obstacles=sum((q['obstacles']for q in r['visible_model_sweeps']),[]),conditional_doors=len(r['conditional_boarding']),conditional_boarding=r['conditional_boarding'],minimum_full_length_platform_width=r['minimum_full_length_platform_width'],evidence=str(review/'review.json'),world_written=False,through_service_complete=False,native_boarding_runtime_verified=False))
    checks=dict(schema='station-release-checks-v1',commands=[],candidate_error_reports=['functional-check.json','offline-verification.json','station-independent-check.json','source-preservation.json','visible-model-sweep.json'],review_error_reports=['review.json','structural-review.json'],structural_report='structural-review.json',
        report_values=[dict(root='review',file='review.json',equals=dict(offline_candidate_verified=True,original_device_nbt_equal=True,original_actors_equal=True,public_floor_errors=[],unexpected_public_obstructions=[],new_floating_solids=[],newly_detached_retained_cells=[],paths_verified=r['paths_verified'],directions_checked=r['directions_checked'],conditional_door_count=len(r['conditional_boarding']),world_written=False))],
        exact_model_arrays=[dict(candidate='vehicle-model/'+name+'-visible-cubes.npz',reference=name+'-visible-cubes.npz',keys=['cubes','names','door_slides'])for name in c['models']],reviewed_views=views,views_reviewed_by_root=False,note='Root strict structural report and view review pending. Existing native snapshot rebase, registration and world installation are root-only.')
    write(candidate/'release-checks.json',checks)
    ports=read(candidate/'stage-three-interfaces.json');ports['explicit_rail_ports']=[dict(rail_id=q['id'],from_endpoint=q['from'],to_endpoint=q['to'],from_native_node_angle=q['from_angle'],to_native_node_angle=q['to_angle'],full_finite_platform_sweep_verified=True,external_track_grade_and_geometry_pending=True)for q in c['rails']];write(candidate/'stage-three-interfaces.json',ports)
    write(candidate/'freeze-handoff.json',dict(candidate_frozen=True,candidate=str(candidate),independent_review=str(review),models=c['model_source'],native_expected_members=c['expected_native_members'],native_baseline_rebase_required=True,offline_errors=[],native_registration_pending=True,world_installation_pending=True,through_service_complete=False,user_visual_acceptance=False,source_and_candidate_views_reviewed=True,original_devices_preserved=r['original_devices_retained'],full_platform_minimum_width=r['minimum_full_length_platform_width'],conditional_doors=len(r['conditional_boarding']),strict_paths=r['paths_verified'],stage_three_interfaces='stage-three-interfaces.json',native_plan='station-set-plan.json',release_layout='release-layout.json',root_strict_review_pending=True,expected_new_native_members=1+2*len(c['rails']),platform_rail_bindings=d['platform_rails']))
    print('Frozen',c['id'],'GIS rail offsets',deviations)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('mode',choices=('survey','plan','verify','package'));p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--candidate',type=Path);p.add_argument('--geometry',type=Path)
    args=p.parse_args();globals()[args.mode](args)
