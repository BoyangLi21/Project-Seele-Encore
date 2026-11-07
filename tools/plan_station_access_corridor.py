"""Offline, source-measured station access road design and bounded compilation.

Cached GIS lines locate future civil interfaces; they never establish that a
road, bridge, channel or water level exists in the captured world.
"""
import argparse
from collections import Counter
import gzip
import json
import math
import os
import shutil
from pathlib import Path

import nbtlib
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box, shape, mapping
from shapely.ops import unary_union

from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')


class CapturedSurface:
    def __init__(self, source, partial=False):
        self.source=Path(source);self.capture=read(self.source/'capture.json')
        if not partial and(self.capture['unavailable_chunks'] or set(self.capture['chunk_statuses'])!={'full'}):
            raise ValueError('Corridor needs complete FULL source')
        with np.load(self.source/'measured.npz') as data:
            self.measured={k:data[k] for k in data.files}
        self.bounds=list(map(int,self.measured['bounds']));self.editor=Editor(self.source)
        self.devices=list(nbtlib.load(self.source/'captured-devices.dat')['Devices'])

    def state(self,x,y,z):
        a,b,A,B=self.bounds
        if not(a<=x<=A and b<=z<=B and -128<=y<=319):
            raise ValueError(('Outside captured extent',x,y,z))
        if not self.measured['full'][z-b,x-a]:raise ValueError(('Unknown source column',x,z))
        return self.editor.state(x,y,z,True)

    def top(self,x,z):
        a,b,_,_=self.bounds
        self.state(x,-128,z)
        return int(self.measured['top'][z-b,x-a])


def smooth_horizontal(points, passes=2):
    """Bounded corner cutting retains both surveyed terminal points."""
    result=np.asarray(points,float)
    for _ in range(passes):
        result=np.vstack([result[0],np.stack([.75*result[:-1]+.25*result[1:],
            .25*result[:-1]+.75*result[1:]],axis=1).reshape(-1,2),result[-1]])
    return result


def sample_line(points, spacing=.5):
    line=LineString(points);stations=np.linspace(0,line.length,math.ceil(line.length/spacing)+1)
    return line,stations,np.asarray([line.interpolate(float(s)).coords[0] for s in stations])


def rounded_alignment(spec):
    """Tangent circular fillets remove short GIS digitizing zigzags."""
    raw=LineString(spec['horizontal_ports'])
    points=np.asarray(raw.simplify(spec['simplification_tolerance']).coords)
    lengths=np.linalg.norm(np.diff(points,axis=0),axis=1);dense=[points[0]];curves=[]
    for i in range(1,len(points)-1):
        u=(points[i]-points[i-1])/lengths[i-1];v=(points[i+1]-points[i])/lengths[i]
        angle=math.acos(np.clip(np.dot(u,v),-1,1))
        if angle<1e-6:continue
        d=min(spec['preferred_curve_radius']*math.tan(angle/2),.48*lengths[i-1],.48*lengths[i])
        radius=d/math.tan(angle/2)
        if radius<spec['minimum_curve_radius']:raise ValueError(('Horizontal curve too tight',i,radius))
        start=points[i]-u*d;end=points[i]+v*d;sign=1 if u[0]*v[1]-u[1]*v[0]>0 else -1
        center=start+np.array([-u[1],u[0]])*sign*radius
        a=math.atan2(start[1]-center[1],start[0]-center[0])
        arc=[center+radius*np.array([math.cos(t),math.sin(t)]) for t in np.linspace(a,a+sign*angle,max(3,math.ceil(radius*angle/.2)+1))]
        dense.append(start);dense.extend(arc[1:]);curves.append(dict(vertex=i,radius=radius,angle=angle,start=start.tolist(),end=end.tolist()))
    dense.append(points[-1])
    line,along,samples=sample_line(dense,.25)
    maximum=max(raw.distance(Point(p)) for p in samples)
    if maximum>spec['maximum_alignment_departure']:raise ValueError(('Departure from cached route',maximum))
    return line,along,samples,dict(curves=curves,minimum_radius=min(c['radius'] for c in curves),
        maximum_departure_from_ports=maximum,simplification_tolerance=spec['simplification_tolerance'])


def nearby_features(path,bounds):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf8') as stream:data=json.load(stream)
    clip=box(*bounds);result=[]
    rows=data['features'] if isinstance(data,dict) else data
    for index,feature in enumerate(rows):
        geometry=shape(feature['geometry'])
        if geometry.intersects(clip):result.append({**feature,'index':index})
    return result


def water_geometry(features,spec):
    """Polygons as drawn; mapped centrelines and streams widened to a channel."""
    layers=spec.get('water_layers',['WA','RvrCL'])
    return unary_union([shape(f['geometry']) if f['properties']['source_layer']=='WA' else shape(f['geometry']).buffer(1)
        for f in features if f['properties']['source_layer'] in layers])


def finite_intervals(line,geometry):
    result=[]
    intersection=line.intersection(geometry)
    for part in getattr(intersection,'geoms',[intersection]):
        if part.geom_type!='LineString' or part.is_empty:continue
        distance=sorted([line.project(Point(part.coords[0])),line.project(Point(part.coords[-1]))])
        result.append(dict(along=distance,length=distance[1]-distance[0],coordinates=list(part.coords)))
    return sorted(result,key=lambda r:r['along'])


def survey(config, out):
    spec=read(config);source=CapturedSurface(spec['source']);out=Path(out);out.mkdir(exist_ok=True)
    if spec.get('alignment_kind')=='tangent_circular_fillets':
        line,stations,points,curvature=rounded_alignment(spec)
    else:
        line,stations,points=sample_line(smooth_horizontal(spec['horizontal_ports'],spec.get('smoothing_passes',2)));curvature=None
    scope=line.buffer(spec['clear_width']/2+2,cap_style=2)
    future=nearby_features(spec['features'],scope.buffer(35).bounds)
    write(out/'route-context.geojson',dict(type='FeatureCollection',features=future))
    water=unary_union([shape(f['geometry']) for f in future if f['properties']['source_layer']=='WA'])
    waterways=water_geometry([f for f in future if f['properties']['source_layer']!='WA'],spec)
    existing_devices=[dict(pos=[int(t[k]) for k in ('x','y','z')],id=str(t['id'])) for t in source.devices]
    natural=SOIL|PLANTS|AIR
    cross_sections=[];foreign={};wet={};profile=[]
    for i,(s,p) in enumerate(zip(stations,points)):
        left=points[max(0,i-1)];right=points[min(len(points)-1,i+1)]
        tangent=(right-left)/np.linalg.norm(right-left);normal=np.array([-tangent[1],tangent[0]])
        samples=[]
        for offset in np.arange(-spec['clear_width']/2-1,spec['clear_width']/2+1.001,1):
            x,z=np.floor(p+offset*normal).astype(int);ground=source.top(int(x),int(z))
            samples.append(dict(offset=float(offset),pos=[int(x),ground,int(z)],state=source.state(int(x),ground,int(z))))
            for y in range(ground-3,max(ground+9,int(spec['maximum_design_feet_y'])+8)):
                state=source.state(int(x),y,int(z));bare=state.split('[')[0]
                if bare in ('minecraft:water','minecraft:lava'):wet[int(x),y,int(z)]=state
                elif bare not in natural|PAVEMENT:foreign[int(x),y,int(z)]=state
        ground=source.top(*map(int,np.floor(p)));profile.append(dict(along=float(s),xz=p.tolist(),ground_y=ground))
        if i%20==0 or i==len(points)-1:cross_sections.append(dict(along=float(s),samples=samples))
    device_intrusions=[d for d in existing_devices if scope.intersects(Point(d['pos'][0],d['pos'][2]))]
    bridge_features=[f for f in future if f['properties']['source_layer']=='RdCL'
        and int(f['properties'].get('vt_code',0)) in (2703,2713,2721,2731)
        and shape(f['geometry']).intersects(scope)]
    nodes=np.asarray(spec['horizontal_ports'])
    result=dict(schema='station-access-source-survey-v1',source=spec['source'],fixed_start=spec['street_anchor'],
        fixed_station_feet=spec['station_feet'],carriage_width=spec['carriage_width'],sidewalk_width_each=spec['sidewalk_width'],
        clear_width=spec['clear_width'],alignment_length=float(line.length),smoothed_points=points.tolist(),curvature=curvature,
        samples_spacing_max=float(np.diff(stations).max()),source_full_chunks=source.capture['chunk_statuses']['full'],
        source_devices=len(source.devices),source_actors=len(source.capture['actors']),unknown_source_cells=0,
        measured_terrain_range=[min(p['ground_y'] for p in profile),max(p['ground_y'] for p in profile)],
        actual_water_cells_in_survey=len(wet),actual_water_states=[dict(pos=list(p),state=s) for p,s in wet.items()],
        finite_foreign_source_cells=[dict(pos=list(p),state=s) for p,s in sorted(foreign.items())],device_intrusions=device_intrusions,
        cached_bridge_features=bridge_features,future_water_interfaces=finite_intervals(line,water),
        future_stream_interfaces=finite_intervals(line,waterways),profile=profile,cross_sections=cross_sections,
        measured_water_level=None if not wet else [min(p[1] for p in wet),max(p[1] for p in wet)],
        candidate_authored=False,world_opened=False,world_written=False,native_opened=False,
        existing_bridge_or_road_inferred_from_GIS=False)
    write(out/'source-survey.json',result)
    write(out/'alignment.geojson',dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(role='proposed road, not installed'),geometry=mapping(line))]))
    render_design(spec,result,future,out)
    print(json.dumps({k:result[k] for k in ('alignment_length','source_full_chunks','source_devices','actual_water_cells_in_survey','measured_terrain_range')},ensure_ascii=False))
    print('Finite foreign cells:',len(foreign),'Device intersections:',len(device_intrusions))
    return result


def render_design(spec,report,features,out):
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    line=LineString(report['smoothed_points']);x,z,X,Z=line.buffer(22).bounds
    scale=min(1750/(X-x),1100/(Z-z));width=math.ceil((X-x)*scale)+80;height=math.ceil((Z-z)*scale)+170
    im=Image.new('RGB',(width,height),'#ecf0e4');draw=ImageDraw.Draw(im)
    def pixel(p):return (40+(p[0]-x)*scale,95+(p[1]-z)*scale)
    def paint(g,color,line_width=1,fill=False):
        if g.is_empty:return
        if g.geom_type=='Polygon':
            draw.polygon([pixel(p) for p in g.exterior.coords],fill=color if fill else None,outline=color)
            for ring in g.interiors:draw.polygon([pixel(p) for p in ring.coords],fill='#ecf0e4')
        elif g.geom_type=='LineString':draw.line([pixel(p) for p in g.coords],fill=color,width=line_width)
        elif hasattr(g,'geoms'):
            for part in g.geoms:paint(part,color,line_width,fill)
    clip=box(x,z,X,Z)
    for f in features:
        layer=f['properties']['source_layer'];g=shape(f['geometry']).intersection(clip)
        if layer=='WA':paint(g,'#9dbfce',fill=True)
        elif layer=='RvrCL':paint(g,'#78a9c0',2)
        elif layer=='BldA':paint(g,'#d8d6cc',fill=True)
        elif layer=='RdCL':paint(g,'#bbbbad',2)
        elif layer=='RailCL':paint(g,'#595b66',3)
    paint(line.buffer(spec['clear_width']/2),'#e1b558',fill=True);paint(line,'#ad571d',3)
    for row in report['finite_foreign_source_cells']:
        px,pz=pixel((row['pos'][0],row['pos'][2]));draw.rectangle((px-1,pz-1,px+1,pz+1),fill='#b22428')
    for i,p in enumerate([spec['street_anchor'][::2],spec['station_feet'][::2]]):
        a,b=pixel(p);draw.ellipse((a-6,b-6,a+6,b+6),fill='#243f2f');draw.text((a+8,b+3),('既有街口','站前入口')[i],font=small,fill='#20352a')
    draw.text((25,15),spec['label']+'接街：真实源 + 拟建走廊（尚未施工）',font=font,fill='#20352a')
    draw.text((25,48),'金色=拟建道路；蓝色=GIS未来水系；浅灰=GIS参考建筑；红色=实测非自然构筑物冲突',font=small,fill='#303a38')
    draw.text((25,height-50),f"实测无水块 / 原街口脚 -77 → 站入口脚 -75 / 路线 {line.length:.1f} m / 不迁设备或建筑",font=small,fill='#303a38')
    im.save(out/'route-plan.png')


def longitudinal_design(config,out):
    """Fit a conservative continuous grade around finite future water openings."""
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    spec=read(config);out=Path(out);survey=read(out/'source-survey.json');source=CapturedSurface(spec['source'])
    points=np.asarray(survey['smoothed_points']);line=LineString(points)
    along=np.asarray([r['along'] for r in survey['profile']]);ground=np.asarray([r['ground_y'] for r in survey['profile']],float)
    features=read(out/'route-context.geojson')['features']
    wet=water_geometry(features,spec)
    intervals=finite_intervals(line,wet.buffer(spec['clear_width']/2+1))
    raw=[]
    for row in intervals:
        a,b=row['along'];raw.append([max(0,a-2),min(line.length,b+2)])
    merged=[]
    for a,b in raw:
        if merged and a-merged[-1][1]<6:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    lower=ground+.5;upper=ground+5;target=ground+1;crossings=[]
    major=spec['major_bridge'];major_a,major_b=sorted(line.project(Point(p)) for p in major['bank_ports_xz'])
    # Complete bridge footprint includes both banks, not just the GIS wet pixels.
    separated=[]
    for a,b in merged:
        if b<major_a or a>major_b:separated.append([a,b])
        else:
            if a<major_a:separated.append([a,major_a])
            if b>major_b:separated.append([major_b,b])
    merged=separated+[[major_a,major_b]]
    merged.sort()
    for i,(a,b) in enumerate(merged):
        use=(along>=a)&(along<=b)
        if not use.any():continue
        main=abs(a-major_a)<1e-6 and abs(b-major_b)<1e-6
        center_min=float(ground[use].min());high_water=major['design_high_water_surface'] if main else center_min-1
        for override in spec.get('water_level_interface_overrides',[]):
            if not main and override['along'][0]<=a and b<=override['along'][1]:
                high_water=override['design_high_water_surface']
        clearance=major['minimum_clearance'] if main else spec['minor_channel_clearance']
        depth=major.get('deck_depth',2) if main else 1
        required_feet=high_water+clearance+depth
        lower[use]=np.maximum(lower[use],required_feet);target[use]=np.maximum(target[use],required_feet)
        crossings.append(dict(id=major['id'] if main else 'future-water-crossing-'+str(i),along=[a,b],
            role='main_river_clear_span' if main else 'future_drainage_opening',length=b-a,
            design_high_water_surface=high_water,design_bed_y=high_water-(3 if main else 2),
            minimum_clearance=clearance,deck_depth=depth,minimum_feet_y=required_feet,
            measured_water_present=False,navigation_verified=False,stage3_interface_constraint=True,
            permanent_piers_inside_opening=False,source_ground_range=[center_min,float(ground[use].max())]))
    crossing=spec.get('level_crossing')
    if crossing:
        # The track stays level out of the platform, so the road climbs to rail height.
        flat=(points[:,0]>=crossing['road_x'][0])&(points[:,0]<=crossing['road_x'][1])
        lower[flat]=upper[flat]=target[flat]=crossing['rail_y']
    n=len(along);matrix=lil_matrix((6*n-6,2*n));rhs=np.zeros(6*n-6)
    for i in range(n-1):
        ds=along[i+1]-along[i]
        matrix[2*i,i+1]=1;matrix[2*i,i]=-1;rhs[2*i]=ds*spec['maximum_continuous_grade']
        matrix[2*i+1,i]=1;matrix[2*i+1,i+1]=-1;rhs[2*i+1]=ds*spec['maximum_continuous_grade']
    for i in range(n):
        j=2*n-2+2*i;matrix[j,i]=1;matrix[j,n+i]=-1;rhs[j]=target[i]
        matrix[j+1,i]=-1;matrix[j+1,n+i]=-1;rhs[j+1]=-target[i]
    for i in range(1,n-1):
        previous=along[i]-along[i-1];following=along[i+1]-along[i]
        row=4*n-2+2*(i-1)
        for sign,offset in ((1,0),(-1,1)):
            matrix[row+offset,i-1]=sign/previous
            matrix[row+offset,i]=-sign*(1/previous+1/following)
            matrix[row+offset,i+1]=sign/following
            rhs[row+offset]=spec.get('maximum_grade_change_per_m',1)*(.5*(previous+following))
    lower[0]=upper[0]=spec['street_anchor'][1];lower[-1]=upper[-1]=spec['station_feet'][1]
    endpoint=lil_matrix((2,2*n));endpoint[0,0]=-1;endpoint[0,1]=1;endpoint[1,n-2]=-1;endpoint[1,n-1]=1
    result=linprog(np.r_[np.zeros(n),np.ones(n)],A_ub=matrix.tocsr(),b_ub=rhs,A_eq=endpoint.tocsr(),b_eq=[0,0],
        bounds=list(zip(lower,upper))+[(0,None)]*n,method='highs')
    if not result.success:
        proof=dict(status='PROFILE_REQUIRES_REVIEW',reason=result.message,crossings=crossings,
                   endpoint_minimum_required=max(lower[i]-spec['maximum_continuous_grade']*along[i] for i in range(n)),
                   source_endpoint=spec['street_anchor'][1],world_written=False)
        write(out/'profile-design.json',proof);raise ValueError(proof)
    feet=result.x[:n]
    for crossing in crossings:
        a,b=crossing['along'];use=(along>=a)&(along<=b)
        crossing['deck_underside_min']=float(feet[use].min()-crossing['deck_depth'])
        crossing['actual_designed_clearance']=crossing['deck_underside_min']-crossing['design_high_water_surface']
        foundations=[]
        for station in (max(0,a-2),min(line.length,b+2)):
            p=line.interpolate(station);x,z=map(int,np.floor(p.coords[0]));g=source.top(x,z)
            foundations.append(dict(along=station,xz=[x,z],ground_y=g,
                bearing_checks=[dict(pos=[x,y,z],state=source.state(x,y,z)) for y in range(g-5,g-2)]))
        crossing['measured_bank_foundation_columns']=foundations
    prior_profile=spec.get('prior_water_profile');matches=[]
    if prior_profile:
        with np.load(prior_profile) as data:
            bx,bz,bX,bZ=map(int,data['bounds']);mask=data['wet']
            matches=[i for i,p in enumerate(points) if bx<=p[0]<=bX and bz<=p[1]<=bZ and mask[int(p[1])-bz,int(p[0])-bx]]
    proof=dict(label=spec['label'],status='PROPOSED_SOURCE_MEASURED_PROFILE',errors=[],alignment_length=float(line.length),
        continuous_grade_max=float((abs(np.diff(feet))/np.diff(along)).max()),
        maximum_grade_change_per_m=float((abs(np.diff(np.diff(feet)/np.diff(along)))/(.5*(np.diff(along)[1:]+np.diff(along)[:-1]))).max()),
        endpoint_grades=[float((feet[1]-feet[0])/(along[1]-along[0])),float((feet[-1]-feet[-2])/(along[-1]-along[-2]))],
        feet_range=[float(feet.min()),float(feet.max())],
        source_ground_range=[float(ground.min()),float(ground.max())],horizontal_points=points.tolist(),along=along.tolist(),
        feet=feet.tolist(),ground=ground.tolist(),crossings=crossings,prior_water_profile=prior_profile,
        prior_water_profile_route_columns=len(matches),existing_water_level_reused=False,
        future_channel_levels_are_explicit_design_constraints=True,water_system_flow_acceptance_pending=True,
        fixed_street_feet=spec['street_anchor'],fixed_station_feet=spec['station_feet'],
        vehicle_and_walking_widths=dict(carriage=spec['carriage_width'],sidewalk_each=spec['sidewalk_width']),
        world_opened=False,world_written=False,ready_for_authoring_review=True)
    write(out/'profile-design.json',proof);render_profile(proof,out)
    print('Profile',proof['feet_range'],'grade',proof['continuous_grade_max'],'openings',len(crossings))


def render_profile(proof,out):
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    width,height=1800,570;im=Image.new('RGB',(width,height),'#f6f5ef');draw=ImageDraw.Draw(im)
    lo=min(min(proof['ground'])-6,-86);hi=max(proof['feet'])+3
    def pt(s,y):return (70+s/proof['alignment_length']*1670,460-(y-lo)/(hi-lo)*350)
    for y in range(math.floor(lo),math.ceil(hi)+1,2):
        a,b=pt(0,y);draw.line((a,b,width-45,b),fill='#d9ddd6');draw.text((20,b-9),str(y),font=small,fill='#42544b')
    for crossing in proof['crossings']:
        a,b=crossing['along'];level=crossing['design_high_water_surface'];x,y=pt(a,level);X,_=pt(b,level)
        draw.line((x,y,X,y),fill='#3a8cba',width=5)
        draw.line((*pt(a,level),*pt(a,level+crossing['minimum_clearance'])),fill='#3a8cba',width=2)
    draw.line([pt(s,y+1) for s,y in zip(proof['along'],proof['ground'])],fill='#8c987c',width=3)
    draw.line([pt(s,y) for s,y in zip(proof['along'],proof['feet'])],fill='#b27125',width=4)
    draw.text((35,18),proof.get('label','')+'接街纵断面：拟建脚位与真实地面（垂向放大）',font=font,fill='#243d32')
    draw.text((35,52),'橙=拟建路面脚位；绿=实测地面顶；蓝=未来水系设计高水面，当前没有实水',font=small,fill='#3b4c42')
    for s in range(0,math.ceil(proof['alignment_length']),100):
        x,_=pt(s,lo);draw.text((x-8,475),str(s)+' m',font=small,fill='#33483e')
    draw.text((35,515),f"连续坡度 ≤ {proof['continuous_grade_max']*100:.1f}% / 7m车道 + 2×2m人行 / {len(proof['crossings'])}处有限跨水接口 / 无河内墩",font=small,fill='#243d32')
    im.save(Path(out)/'longitudinal-profile.png')


def level_crossing_band(spec,xx):
    band=spec.get('level_crossing',{}).get('road_x')
    return (xx>=band[0])&(xx<=band[1]) if band else np.zeros(xx.shape,bool)


def bus_rectangle(center,tangent,length,width):
    normal=np.array([-tangent[1],tangent[0]])
    return Polygon([center+a*tangent+b*normal for a,b in
        ((length/2,width/2),(length/2,-width/2),(-length/2,-width/2),(-length/2,width/2))])


def civil_constraints(config,out):
    """Bounded bus envelopes, complete bank footings and future channel voids."""
    spec=read(config);out=Path(out);profile=read(out/'profile-design.json');source=CapturedSurface(spec['source'])
    points=np.asarray(profile['horizontal_points']);along=np.asarray(profile['along']);line=LineString(points)
    bus=spec['reference_bus'];base=line.buffer(spec['carriage_width']/2)
    poses=[];swept=[];baseline_failures=[]
    for i,center in enumerate(points):
        tangent=points[min(i+1,len(points)-1)]-points[max(0,i-1)];tangent/=np.linalg.norm(tangent)
        normal=np.array([-tangent[1],tangent[0]])
        for lane in (-bus['lane_offset'],bus['lane_offset']):
            body=bus_rectangle(center+normal*lane,tangent,bus['length'],bus['width'])
            swept.append(body)
            excess=body.difference(base).area
            if excess>1e-7:baseline_failures.append(dict(along=float(along[i]),lane=lane,area=excess))
            poses.append(dict(along=float(along[i]),lane=lane,center=(center+normal*lane).tolist(),tangent=tangent.tolist()))
    # The small extra envelope is a declared local curve widening. The later
    # voxel verifier independently checks the rasterized road and headroom.
    road=unary_union([base,unary_union(swept).buffer(.5)])
    junction=[];junction_proof=[]
    if spec.get('street_vehicle_interface'):
        port=spec['street_vehicle_interface'];j=int(np.argmin(abs(along-port['join_along'])))
        tangent=points[j+1]-points[j-1];tangent/=np.linalg.norm(tangent);normal=np.array([-tangent[1],tangent[0]])
        for lane in (-bus['lane_offset'],bus['lane_offset']):
            p0=np.asarray(port['center_xz']);p3=points[j]+normal*lane;best=None
            for first in np.arange(4,14.1,1):
                for last in np.arange(4,14.1,1):
                    p1=p0+np.asarray(port['heading_xz'])*first;p2=p3-tangent*last
                    values=[];minimum=1e9
                    for u in np.linspace(0,1,161):
                        q=(1-u)**3*p0+3*u*(1-u)**2*p1+3*u*u*(1-u)*p2+u**3*p3
                        v=3*(1-u)**2*(p1-p0)+6*u*(1-u)*(p2-p1)+3*u*u*(p3-p2)
                        acceleration=6*(1-u)*(p2-2*p1+p0)+6*u*(p3-2*p2+p1)
                        determinant=v[0]*acceleration[1]-v[1]*acceleration[0]
                        radius=np.linalg.norm(v)**3/max(abs(determinant),1e-12);minimum=min(minimum,radius)
                        v/=np.linalg.norm(v);values.append(dict(center=q.tolist(),tangent=v.tolist(),junction_lane=lane))
                    if best is None or minimum>best[0]:best=(minimum,[p0.tolist(),p1.tolist(),p2.tolist(),p3.tolist()],values)
            if best[0]<port['minimum_radius']:raise ValueError('Original vehicle street junction has inadequate turning radius')
            junction+=best[2];junction_proof.append(dict(lane=lane,minimum_radius=best[0],controls=best[1],poses=len(best[2])))
        finite_junction=Point(spec['street_anchor'][0],spec['street_anchor'][2]).buffer(14)
        road=road.union(unary_union([bus_rectangle(np.asarray(p['center']),np.asarray(p['tangent']),bus['length'],bus['width'])for p in junction]).buffer(.5).intersection(finite_junction))
    fore=spec['forecourt'];radius=fore['bus_centerline_radius'];exit_radius=radius-2*bus['lane_offset']
    if exit_radius<fore['minimum_exit_radius']:raise ValueError('Terminal exit curvature is too tight')
    approach=points[-1]-points[-2];approach/=np.linalg.norm(approach);normal=np.array([-approach[1],approach[0]])
    terminal_start=points[-1]+normal*bus['lane_offset']
    terminal_center=terminal_start-normal*radius
    pad=Point(*terminal_center).buffer(fore['carriage_outer_radius'],quad_segs=96)
    terminal=[];terminal_bodies=[]
    # 270 degree clockwise return plus a reverse-curvature exit connects to
    # the same two-way approach without reversing the reference bus.
    for center,initial,angle,turn_radius in ((np.array([0,radius]),-math.pi/2,-1.5*math.pi,radius),
                                 (np.array([radius+exit_radius,radius]),math.pi,math.pi/2,exit_radius)):
        for t in np.linspace(initial,initial+angle,math.ceil(abs(angle)*turn_radius/.25)+1):
            local=center+turn_radius*np.array([math.cos(t),math.sin(t)])
            direction=np.sign(angle)*np.array([-math.sin(t),math.cos(t)])
            pos=terminal_start-approach*local[0]-normal*local[1]
            tangent=-approach*direction[0]-normal*direction[1]
            terminal.append(dict(center=pos.tolist(),tangent=tangent.tolist()))
            terminal_bodies.append(bus_rectangle(pos,tangent,bus['length'],bus['width']))
    terminal_road=unary_union([pad,unary_union(terminal_bodies).buffer(.5)])
    road=road.union(terminal_road)
    if 'pedestrian_route_xz' in spec:
        pedestrian=LineString(spec['pedestrian_route_xz']).buffer(fore['pedestrian_width']/2,cap_style=2,join_style=2)
    else:
        pedestrian_left=fore['pedestrian_entry_x']-fore['pedestrian_width']//2
        pedestrian=box(pedestrian_left,fore['pedestrian_z'][0],
                       pedestrian_left+fore['pedestrian_width'],fore['pedestrian_z'][1]+1)
    walk=road.buffer(spec['sidewalk_width']).union(pedestrian)
    features=read(out/'route-context.geojson')['features']
    future_no_pier=water_geometry(features,spec).buffer(2)
    foundations=[];unresolved=[]
    def try_support(station):
        j=int(np.argmin(abs(along-station)));p=points[j]
        tangent=points[min(j+1,len(points)-1)]-points[max(0,j-1)];tangent/=np.linalg.norm(tangent)
        normal=np.array([-tangent[1],tangent[0]]);footprints=[]
        for sign in (-1,1):
            found=None
            for offset in (4.5,6.5,8.5):
                center=np.rint(p+normal*sign*offset).astype(int)
                footprint=box(center[0]-1,center[1]-1,center[0]+2,center[1]+2)
                if footprint.intersects(future_no_pier):continue
                ground=[source.top(x,z) for x in range(center[0]-1,center[0]+2) for z in range(center[1]-1,center[1]+2)]
                bearing=min(ground)-3
                while bearing>=-110:
                    states=[source.state(x,bearing,z) for x in range(center[0]-1,center[0]+2) for z in range(center[1]-1,center[1]+2)]
                    if all(s=='minecraft:stone' for s in states):break
                    bearing-=1
                if bearing<-110:raise ValueError('No complete measured stone footing')
                found=dict(center_xz=center.tolist(),normal_offset=sign*offset,
                    bounds_xz=list(map(int,[center[0]-1,center[1]-1,center[0]+1,center[1]+1])),
                    bearing_y=bearing,bearing_states=[dict(pos=[x,bearing,z],state=source.state(x,bearing,z))
                        for x in range(center[0]-1,center[0]+2) for z in range(center[1]-1,center[1]+2)],
                    surface_ground_range=[min(ground),max(ground)],future_water_intersection=False)
                break
            if found is None:return None
            footprints.append(found)
        return footprints
    for crossing in profile['crossings']:
        a,b=crossing['along']
        # Intermediate supports may use measured dry islands only; the main
        # river remains one clear span throughout its declared opening.
        stations=[max(0,a-3),min(line.length,b+3)]
        if crossing['role']!='main_river_clear_span':stations+=list(np.arange(a+14,b-4,14))
        accepted=[]
        for s in sorted(stations):
            alternatives=[s]
            if s==stations[0]:alternatives += [max(0,s-d) for d in range(1,13)]+[min(line.length,s+d) for d in range(1,7)]
            if s==stations[1]:alternatives += [min(line.length,s+d) for d in range(1,13)]+[max(0,s-d) for d in range(1,7)]
            choice=None
            for actual in alternatives:
                footprints=try_support(actual)
                if footprints is not None:choice=(actual,footprints);break
            if choice:
                actual,footprints=choice;accepted.append(actual)
                foundations.append(dict(crossing=crossing['id'],along=actual,original_station=s,footings=footprints))
            elif s in stations[:2]:
                unresolved.append(dict(crossing=crossing['id'],proposed_along=s,reason='Bank footing touches future water exclusion; move bounded support, never occupy the channel.'))
        crossing['accepted_support_stations']=accepted
        crossing['largest_proposed_support_interval']=max(np.diff(accepted),default=b-a)
    bounds=np.array(walk.bounds);a,b,A,B=map(int,[math.floor(bounds[0])-2,math.floor(bounds[1])-2,math.ceil(bounds[2])+2,math.ceil(bounds[3])+2])
    ca,cb,cA,cB=source.bounds
    if not(ca<=a<=A<=cA and cb<=b<=B<=cB):raise ValueError('Final road/forecourt exceeds measured source')
    widths=[]
    for i in range(1,len(points)-1,4):
        tangent=points[i+1]-points[i-1];tangent/=np.linalg.norm(tangent);normal=np.array([-tangent[1],tangent[0]])
        cross=LineString([points[i]-normal*20,points[i]+normal*20]);widths.append(float(cross.intersection(road).length))
    report=dict(schema='station-access-civil-constraints-v1',reference_bus=bus,
        reference_bus_is_actual_asset=False,mainline_pose_count=len(poses),travel_directions=[-1,1],
        sample_spacing_max=float(np.diff(along).max()),interval_motion_padding=.5,
        initial_7m_carriageway_rejected_poses=len(baseline_failures),initial_failures=baseline_failures,
        final_plan_bus_intrusions=sum(not road.covers(g) for g in swept+terminal_bodies),
        normal_carriage_width=spec['carriage_width'],maximum_carriage_cross_section_including_terminal=max(widths),
        sidewalk_width=spec['sidewalk_width'],road_area=road.area,walk_area=walk.area,
        forecourt=dict(fore,actual_turn_center_xz=terminal_center.tolist(),exit_curve_radius=exit_radius,
            entry_feet_xz=terminal[0]['center'],exit_feet_xz=terminal[-1]['center'],
            return_path_length=1.5*math.pi*radius+.5*math.pi*exit_radius),
        forecourt_return_poses=terminal,original_vehicle_street_junction=junction_proof,full_bank_footings=foundations,
        hydraulic_crossings=profile['crossings'],unresolved_bank_supports=unresolved,
        hydraulic_constraints_are_future_interfaces=True,water_flow_physics_claim=False,
        source_water_blocks_changed=0,un_footprint_moved=False,device_changes=0,world_written=False,
        errors=['Some bank supports need bounded relocation'] if unresolved else [])
    write(out/'civil-constraints.json',report)
    write(out/'civil-footprints.geojson',dict(type='FeatureCollection',features=[
        dict(type='Feature',properties=dict(role=role),geometry=mapping(g))for role,g in
        [('carriageway',road),('pedestrian_and_road_surface',walk),('pedestrian_station_link',pedestrian),
         ('future_water_no_pier',future_no_pier.intersection(walk.buffer(10))),('terminal_apron',terminal_road)]]))
    write(out/'bus-poses.json',dict(mainline=poses,terminal=terminal,junction=junction,reference=bus))
    print('Bus plan intrusions',report['final_plan_bus_intrusions'],'footings',len(foundations),'support issues',len(unresolved))
    return report


def author(config, design, out):
    """Write a standard exact-delta candidate; never open the actual world."""
    import shapely
    from scipy.spatial import cKDTree
    from scipy.ndimage import distance_transform_edt, binary_dilation
    from hakone_earthworks import road_blocks
    spec=read(config);design=Path(design);out=Path(out)
    civil=read(design/'civil-constraints.json');profile=read(design/'profile-design.json')
    if civil['errors'] or civil['final_plan_bus_intrusions']:raise ValueError('Civil design is not ready')
    source=CapturedSurface(spec['source']);out.mkdir(exist_ok=False)
    for name in ('source','delta','earthworks'):(out/name).mkdir()
    for path in (source.source/'source').glob('*.npz'):os.link(path,out/'source'/path.name)
    for name in ('capture.json','captured-devices.dat','measured.npz'):shutil.copy2(source.source/name,out/name)
    shutil.copy2(config,out/'access-design-input.json')
    for name in ('source-survey.json','profile-design.json','civil-constraints.json','civil-footprints.geojson','bus-poses.json'):
        shutil.copy2(design/name,out/name)
    geometry={f['properties']['role']:shape(f['geometry']) for f in read(design/'civil-footprints.geojson')['features']}
    a,b,A,B=geometry['pedestrian_and_road_surface'].buffer(12).bounds
    bx,bz,bX,bZ=map(int,(math.floor(a),math.floor(b),math.ceil(A),math.ceil(B)))
    sx,sz,sX,sZ=source.bounds
    gx,gz,gX,gZ=geometry['pedestrian_and_road_surface'].bounds
    if not(sx<=gx<gX<=sX and sz<=gz<gZ<=sZ):raise ValueError('Actual civil footprint exceeds FULL capture')
    bx,bz,bX,bZ=max(bx,sx),max(bz,sz),min(bX,sX),min(bZ,sZ)
    zz,xx=np.mgrid[bz:bZ+1,bx:bX+1];cells=shapely.box(xx,zz,xx+1,zz+1)
    def raster(g):
        shapely.prepare(g)
        return shapely.intersects(g,cells)
    road=raster(geometry['carriageway'])
    with np.load(Path(spec['authority'])/'network.npz')as base:
        ax,az,_,_=map(int,base['bounds']);oldroad=base['road'][bz-az:bZ-az+1,bx-ax:bX-ax+1]
    # Joining a road must never repaint retained carriageway as a footway.
    raster_road=unary_union(cells[road])
    walk=raster(raster_road.buffer(spec['sidewalk_width']))
    road|=oldroad&walk
    link=raster(geometry['pedestrian_station_link'].buffer(-1e-6))
    walk|=link;road[link]=False
    points=np.asarray(profile['horizontal_points']);along=np.asarray(profile['along']);height=np.asarray(profile['feet'])
    distance,nearest=cKDTree(points).query(np.c_[xx.ravel()+.5,zz.ravel()+.5])
    distance=distance.reshape(xx.shape);nearest=nearest.reshape(xx.shape);chainage=along[nearest]
    feet=np.ceil((height[nearest]-1e-9)*2)/2
    terminal=raster(geometry['terminal_apron'].buffer(spec['sidewalk_width']))
    centre=np.zeros(walk.shape,bool);stroke=np.floor(points).astype(int)
    inside=(stroke[:,0]>=bx)&(stroke[:,0]<=bX)&(stroke[:,1]>=bz)&(stroke[:,1]<=bZ)
    centre[stroke[inside,1]-bz,stroke[inside,0]-bx]=True
    feet[terminal|link]=spec['station_feet'][1]
    grade2=np.rint(2*(feet-1)).astype(np.int16);floor,slab=road_blocks(grade2)
    original=source.measured['top'][bz-sz:bZ-sz+1,bx-sx:bX-sx+1].copy()
    water=raster(geometry['future_water_no_pier'])
    span=water&walk
    for crossing in civil['hydraulic_crossings']:
        stations=crossing['accepted_support_stations'];a,b=crossing['along']
        if stations:a=min(a,min(stations));b=max(b,max(stations))
        span|=walk&(chainage>=a)&(chainage<=b)
    # The surface is mechanically connected through its real deck and bank
    # footings. Future channels never receive road embankment columns.
    d,near=distance_transform_edt(~(walk&~span),return_indices=True)
    base=(floor-1)[tuple(near)]
    target=np.rint(np.clip(original,base-d*.5,base+d*.5)).astype(np.int16)
    target[water|span]=original[water|span]
    active=(target!=original)&(d<=10)
    if any(np.any(edge)for edge in (active[0],active[-1],active[:,0],active[:,-1])):
        raise ValueError('Daylight earthworks touch the review boundary')
    authority=Path(spec['authority']);catalog=read(authority/'catalog.json')
    protected=[r['occupied_bounds'] for r in catalog if r['occupied_bounds'][0]<=bX and r['occupied_bounds'][3]>=bx
               and r['occupied_bounds'][2]<=bZ and r['occupied_bounds'][5]>=bz]
    protected=[[x,y-3,z,X,Y,Z] for x,y,z,X,Y,Z in protected]
    protected += [r for r in read(authority/'station-volumes.json') if r[0]<=bX and r[3]>=bx and r[2]<=bZ and r[5]>=bz]
    # Existing buildings remain fixed grading boundaries. Road works are
    # rejected if they enter them; exterior soil grading stops at their edge.
    retained_footprint=np.zeros(walk.shape,bool)
    for x,y,z,X,Y,Z in protected:retained_footprint|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
    if np.any(retained_footprint&walk):raise ValueError('Public corridor enters retained structure footprint')
    active[retained_footprint]=False;target[retained_footprint]=original[retained_footprint]
    devices={tuple(int(t[k])for k in ('x','y','z')) for t in source.devices}
    writes={};purposes={};editor=Editor(out);allowed=SOIL|PLANTS|AIR
    def put(x,y,z,state,purpose):
        x,y,z=int(x),int(y),int(z);pos=(x,y,z);before=source.state(x,y,z)
        if before==state and pos not in writes:return
        if pos in devices or any(a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in protected):
            raise ValueError(('Finite retained structure/device',pos,before,purpose))
        old=before.split('[')[0]
        street_port=math.hypot(x-spec['street_anchor'][0],z-spec['street_anchor'][2])<=16
        if old not in allowed and not(old in PAVEMENT and street_port):
            raise ValueError(('Unowned source material',pos,before,purpose))
        writes[pos]=state;purposes[pos]=purpose
    for iz,ix in np.argwhere(active&~walk):
        x,z=int(xx[iz,ix]),int(zz[iz,ix]);old=int(original[iz,ix]);new=int(target[iz,ix])
        for y in range(min(old,new)-2,max(old,new)+1):
            material='minecraft:air' if y>new else 'minecraft:grass_block[snowy=false]' if y==new else 'minecraft:dirt' if y>=new-2 else 'minecraft:stone'
            put(x,y,z,material,'finite daylight earthworks')
    for iz,ix in np.argwhere(walk):
        x,z,y=int(xx[iz,ix]),int(zz[iz,ix]),int(floor[iz,ix])
        if not span[iz,ix]:
            for yy in range(min(int(original[iz,ix])-1,y-1),y):put(x,yy,z,'minecraft:stone','continuous roadway bearing')
        elif slab[iz,ix]:put(x,y-1,z,'minecraft:stone','half-slab deck attachment')
        for yy in range(y+1,max(y+6,int(original[iz,ix])+2)):
            put(x,yy,z,'minecraft:air','full vehicle and pedestrian headroom')
        marking=road[iz,ix] and centre[iz,ix] and int(chainage[iz,ix]//6)%2==0 and not terminal[iz,ix]
        if slab[iz,ix]:
            state=('projectseele:road_marking_slab' if marking else 'projectseele:road_asphalt_slab' if road[iz,ix] else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]'
        else:state='minecraft:white_concrete' if marking else 'minecraft:black_concrete' if road[iz,ix] else 'minecraft:smooth_stone'
        original_state=source.state(x,y,z)
        if oldroad[iz,ix] and original_state.split('[')[0]in PAVEMENT:state=original_state
        put(x,y,z,state,'carriageway' if road[iz,ix] else 'public footway')
    def index(x,z):return int(z)-bz,int(x)-bx
    def sampled_feet(x,z):
        iz,ix=index(x,z)
        if not(0<=iz<feet.shape[0] and 0<=ix<feet.shape[1]):raise ValueError('Civil structure exceeds finite review extent')
        return float(feet[iz,ix])
    def beam(points3,purpose):
        previous=None
        for a,b in zip(points3,points3[1:]):
            for p in np.linspace(a,b,max(2,math.ceil(np.linalg.norm(np.asarray(b)-a)*4)+1)):
                q=tuple(map(int,np.floor(p)))
                if previous is None:previous=q
                current=list(previous)
                for axis in range(3):
                    while current[axis]!=q[axis]:
                        current[axis]+=1 if q[axis]>current[axis] else -1
                        pos=tuple(current);iz,ix=index(pos[0],pos[2])
                        public=0<=iz<walk.shape[0] and 0<=ix<walk.shape[1] and walk[iz,ix]
                        if public and pos[1]==int(floor[iz,ix]):continue
                        if public and pos[1]>floor[iz,ix] and pos[1]<feet[iz,ix]+5:
                            raise ValueError(('Bridge beam occupies public clearance',pos,purpose))
                        put(*pos,'minecraft:iron_block',purpose)
                previous=q
    for support in civil['full_bank_footings']:
        tops=[]
        for footing in support['footings']:
            x,z=footing['center_xz'];a,b,A,B=footing['bounds_xz'];cap=math.ceil(sampled_feet(x,z))-1
            for X in range(a,A+1):
                for Z in range(b,B+1):
                    for y in range(footing['bearing_y']+1,cap+1):
                        iz,ix=index(X,Z)
                        if walk[iz,ix] and y>=int(floor[iz,ix]):continue
                        put(X,y,Z,'minecraft:stone_bricks','measured stone-bearing pier')
            tops.append([x,cap,z])
        beam(tops,'bank crosshead at deck level')
    # Every elevated sidewalk edge has a separate beam/parapet outside the
    # clear pedestrian cells. No fence consumes the two-metre footway.
    guard=binary_dilation(span,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))&~walk
    # A level crossing keeps its whole width open for the future train body.
    crossing_band=level_crossing_band(spec,xx)
    guard&=~crossing_band
    trusses=spec['truss_crossings'];plate=np.zeros(walk.shape,bool)
    for crossing in civil['hydraulic_crossings']:
        stations=crossing['accepted_support_stations']
        if max(stations)-min(stations)>=18:
            plate|=(chainage>=min(stations))&(chainage<=max(stations))
    for a,b in trusses.values():plate&=~((chainage>=a)&(chainage<=b))
    for iz,ix in np.argwhere(guard):
        x,z=int(xx[iz,ix]),int(zz[iz,ix]);h=math.ceil(sampled_feet(x,z))
        put(x,h-1,z,'minecraft:stone_bricks','outer deck edge beam')
        state='minecraft:iron_bars[east=true,north=true,south=true,waterlogged=false,west=true]'
        put(x,h,z,state,'outside-footway parapet')
        if plate[iz,ix]:
            put(x,h-1,z,'minecraft:iron_block','side plate girder')
            put(x,h,z,'minecraft:iron_block','side plate girder')
    actual_walk=unary_union(cells[walk]);shapely.prepare(actual_walk)
    for crossing in civil['hydraulic_crossings']:
        # Declared chainage keeps the truss on the straight; a truss bay
        # on a bend voxelizes into a tangle of diagonals.
        if crossing['id'] not in trusses:continue
        start,end=trusses[crossing['id']]
        truss_rows=[]
        for s in np.linspace(start,end,math.ceil((end-start)/6)+1):
            j=int(np.argmin(abs(along-s)));p=points[j];t=points[min(j+1,len(points)-1)]-points[max(0,j-1)];t/=np.linalg.norm(t)
            normal=np.array([-t[1],t[0]]);side=[]
            for sign in (-1,1):
                offset=7.
                while actual_walk.intersects(Point(*(p+normal*sign*offset)).buffer(1.5)):offset+=.5
                q=p+normal*sign*offset;h=math.ceil(sampled_feet(*map(int,q)))
                side.append(([q[0],h-1,q[1]],[q[0],h+6,q[1]]))
                beam([side[-1][0],side[-1][1]],'above-deck side truss post')
            beam([side[0][0],side[1][0]],'transverse deck tie at wearing-plate level')
            beam([side[0][1],side[1][1]],'high transverse truss frame')
            truss_rows.append(side)
        for a,b in zip(truss_rows,truss_rows[1:]):
            for i in (0,1):
                beam([a[i][0],b[i][0]],'side truss lower chord')
                beam([a[i][1],b[i][1]],'side truss upper chord')
                beam([a[i][0],b[i][1]],'side truss diagonal')
    # A pair of bollards separates the fixed station pedestrian link from
    # the bus apron; the whole three-column portal remains open.
    portal=spec['station_pedestrian_interface'];link_mid=(portal['x'][0]+portal['x'][1])//2
    for x in (link_mid-2,link_mid+2) if 'pedestrian_z' in spec['forecourt'] else ():
        z=spec['forecourt']['pedestrian_z'][1];y=math.floor(spec['station_feet'][1])
        if not walk[index(x,z)]:
            put(x,y-1,z,'minecraft:stone_bricks','pedestrian portal footing')
            put(x,y,z,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]','pedestrian-only portal bollard')
    rows=[]
    for pos,state in sorted(writes.items()):
        before=source.state(*pos)
        if before==state:continue
        editor.put(*pos,state);rows.append(dict(pos=list(pos),before=before,after=state,purpose=purposes[pos]))
    regions=editor.save()
    for region in regions:
        path=out/region['path']
        with np.load(path) as data:payload={k:data[k] for k in data.files}
        np.savez_compressed(path,**payload,y_origin=-128,height=448)
        region.update(y_origin=-128,height=448)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(out/'block-entities.dat',gzipped=True)
    write(out/'exact-edits.json',rows)
    write(out/'forward-patch.json',dict(edits=rows,requires_exact_before=True))
    write(out/'inverse-patch.json',dict(edits=[dict(pos=r['pos'],before=r['after'],after=r['before']) for r in rows],requires_exact_before=True))
    write(out/'manifest.json',dict(schema='bounded-station-access-corridor-v1',world=source.capture['world'],
        source=str(source.source),section_source=spec['section_source'],cells=len(rows),regions=regions,
        vertical_extent=[-128,319],device_changes=0,native_changes=[],native_additions=[],actor_changes=[],
        streets=[dict(id=spec['id'],status='prepared',walk_columns=int(walk.sum()))],
        preserve_native_members=True,world_written=False))
    np.savez_compressed(out/'earthworks'/ (spec['id']+'.npz'),bounds=[bx,bz,bX,bZ],old=original,target=target,active=active,
        walk=walk,road=road,grade2=grade2,bridge_span=span,deck_depth=0,clearance=5,guard=guard,
        future_water_no_fill=water,terminal=terminal,station_link=link)
    write(out/'authored-design.json',dict(world=source.capture['world'],streets=[dict(id=spec['id'],
        points=np.column_stack((points[:,0],height,points[:,1])).tolist(),bounds=[bx,bz,bX,bZ],
        carriage_width=spec['carriage_width'],sidewalk_width=spec['sidewalk_width'],linear_grade=True,
        maximum_grade=spec['maximum_continuous_grade'],maximum_crossfall=.5,clearance=5,
        explicit_bridge_deck_scope='Wearing plate plus half-slab attachments; actual foundation/truss proof is separate.')]))
    write(out/'author-report.json',dict(errors=[],changed_cells=len(rows),public_columns=int(walk.sum()),road_columns=int(road.sum()),
        side_footway_columns=int((walk&~road).sum()),bridge_columns=int(span.sum()),guard_columns=int(guard.sum()),
        preserved_devices=len(devices),actor_changes=0,native_changes=0,source_water_changed=0,
        purposes=dict(Counter(r['purpose'] for r in rows)),world_opened=False,world_written=False,whole_station_complete=False))
    print('Authored',len(rows),'cells;',int(walk.sum()),'public columns')


def verify(config,out):
    """Independent measurements of emitted voxels, including destructive controls.

    Vehicle proof is an architectural cuboid and road-grade envelope. Wheels,
    suspension, navigation and production runtime remain separately pending.
    """
    import shapely
    from collections import deque
    from scipy.ndimage import label
    from scipy.spatial import cKDTree
    from hakone_earthworks import road_blocks
    from map_pipeline.delta_geometry import checked_indices
    from map_pipeline.corridors import publish_plan
    from map_pipeline.native_rails import load_rails,near_points
    from map_pipeline.verify_corridors import main as common_verify
    from types import SimpleNamespace
    spec=read(config);out=Path(out);source=CapturedSurface(spec['source']);e=Editor(out)
    civil=read(out/'civil-constraints.json');profile=read(out/'profile-design.json');rows=read(out/'exact-edits.json')
    manifest=read(out/'manifest.json');errors=[];negative=[]
    with np.load(out/'earthworks'/(spec['id']+'.npz')) as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);walk=d['walk'];road=d['road'];floor,slab=road_blocks(d['grade2'])
    feet=floor+np.where(slab,.5,1);zz,xx=np.mgrid[z:Z+1,x:X+1]
    def idx(px,pz):
        if not(x<=px<=X and z<=pz<=Z):raise ValueError('Outside declared review extent')
        return pz-z,px-x
    def solid(state):return state.split('[')[0] not in AIR|PLANTS|{'minecraft:light'}
    exact={tuple(r['pos']):r for r in rows};delta={}
    for path in sorted((out/'delta').glob('*.npz')):
        with np.load(path) as f:
            bottom,height,indices=checked_indices(f)
            for i,(cx,cz) in enumerate(f['coordinates']):
                lo,hi=map(int,f['ranges'][i:i+2])
                for j in range(lo,hi):
                    v=int(indices[j]);pos=(int(cx)*16+v%16,bottom+v//256,int(cz)*16+(v//16)%16)
                    delta[pos]=(str(f['palette'][f['before'][j]]),str(f['palette'][f['after'][j]]))
    if len(rows)!=manifest['cells'] or len(exact)!=len(rows) or set(delta)!=set(exact):errors.append('Manifest / exact / delta target domains differ')
    stale=[]
    for pos,r in exact.items():
        if source.state(*pos)!=r['before'] or delta.get(pos)!=(r['before'],r['after']) or e.state(*pos)!=r['after']:stale.append(pos)
    if stale:errors.append(['Exact source/delta disagreement',stale[:10]])
    if read(out/'forward-patch.json')['edits']!=rows:errors.append('Forward patch differs')
    inverse=read(out/'inverse-patch.json')['edits']
    if any(q['pos']!=r['pos'] or q['before']!=r['after'] or q['after']!=r['before'] for q,r in zip(inverse,rows)) or len(inverse)!=len(rows):errors.append('Inverse patch differs')
    devices_before=nbtlib.load(source.source/'captured-devices.dat')
    devices_after=nbtlib.load(out/'captured-devices.dat')
    device_bad=[tuple(int(t[k])for k in ('x','y','z'))for t in source.devices
                if source.state(*(int(t[k])for k in ('x','y','z')))!=e.state(*(int(t[k])for k in ('x','y','z')))]
    devices_ok=devices_before==devices_after and not device_bad
    actors_ok=source.capture.get('actors',[])==read(out/'capture.json').get('actors',[]) and not manifest['actor_changes']
    if not devices_ok:errors.append(['Original device changed',device_bad])
    if not actors_ok:errors.append('Captured actors changed')
    if list(nbtlib.load(out/'block-entities.dat')['Changes']):errors.append('Unexpected device edits')
    publish_plan(out,Path(spec['authority']))
    try:common_verify(SimpleNamespace(candidate=out,plan=Path(spec['authority'])))
    except ValueError:errors.append('Common full-width corridor verifier failed')
    common=read(out/'independent-check.json')
    def inspect_public_cell(state_at,px,pz):
        ij=idx(px,pz);py=int(floor[ij]);state=state_at(px,py,pz)
        observed=py+(.5 if 'type=bottom' in state else 1)
        surface_ok=state.split('[')[0] in PAVEMENT and observed==feet[ij]
        clear=all(not solid(state_at(px,y,pz))for y in range(py+1,py+6))
        return bool(surface_ok and clear)
    # Discover the actual wearing course, rather than trusting the mask values.
    actual_floor=np.zeros(walk.shape,bool);headroom=np.zeros(walk.shape,bool)
    for iz,ix in np.argwhere(walk):
        px,pz,py=x+int(ix),z+int(iz),int(floor[iz,ix]);state=e.state(px,py,pz)
        observed=py+(.5 if 'type=bottom' in state else 1)
        actual_floor[iz,ix]=state.split('[')[0] in PAVEMENT and observed==feet[iz,ix]
        headroom[iz,ix]=all(not solid(e.state(px,y,pz))for y in range(py+1,py+6))
    actual_road=road&actual_floor&headroom
    with np.load(Path(spec['authority'])/'network.npz')as base:
        ax,az,_,_=map(int,base['bounds']);area=np.s_[z-az:Z-az+1,x-ax:X-ax+1]
        retained=base['road'][area]&~walk;retained_grade=base['grade2'][area]
    feet=feet.copy();oldfloor,oldslab=road_blocks(retained_grade)
    for iz,ix in np.argwhere(retained):
        px,pz,py=x+int(ix),z+int(iz),int(oldfloor[iz,ix]);state=e.state(px,py,pz)
        feet[iz,ix]=py+(.5 if oldslab[iz,ix] else 1)
        actual_road[iz,ix]=state.split('[')[0] in PAVEMENT and all(not solid(e.state(px,y,pz))for y in range(py+1,py+6))
    poses=read(out/'bus-poses.json');bus=poses['reference'];vehicle_fail=[];pose_rows=[]
    geometries=[];motion=[];body_height=float(bus['height']);point_poses=poses['mainline']+poses['terminal']+poses.get('junction',[])
    for i,p in enumerate(point_poses):
        g=bus_rectangle(np.asarray(p['center']),np.asarray(p['tangent']),bus['length'],bus['width'])
        geometries.append(g);a,b,A,B=g.bounds
        qz,qx=np.mgrid[math.floor(b):math.ceil(B),math.floor(a):math.ceil(A)]
        use=shapely.intersection(shapely.box(qx,qz,qx+1,qz+1),g)
        q=np.c_[qx[shapely.area(use)>1e-8],qz[shapely.area(use)>1e-8]]
        indices=[idx(int(px),int(pz))for px,pz in q]
        missing=[list(map(int,q[j]))for j,ij in enumerate(indices)if not actual_road[ij]]
        tops=np.asarray([feet[ij]for ij in indices]);bottom=float(tops.max());top=bottom+body_height
        occupied=[]
        for (px,pz),ij in zip(q,indices):
            for py in range(math.floor(bottom+1e-7),math.ceil(top)):
                state=e.state(int(px),py,int(pz))
                state_top=py+(.5 if 'type=bottom' in state else 1)
                if solid(state) and state_top>bottom+1e-7:occupied.append([int(px),py,int(pz),state])
        if missing or occupied:vehicle_fail.append(dict(pose=i,missing_road=missing[:3],body_collision=occupied[:3]))
        pose_rows.append(dict(pose=i,road_cells=len(q),floor_range=[float(tops.min()),bottom],body_y=[bottom,top],passed=not missing and not occupied))
    # For each ordered lane, bound between-pose translation and rotation by
    # maximum corner displacement, checked against the explicit design pad.
    main_end=len(poses['mainline']);terminal_end=main_end+len(poses['terminal'])
    junction=poses.get('junction',[])
    half=len(junction)//2
    for sequence in (geometries[:main_end:2],geometries[1:main_end:2],geometries[main_end:terminal_end],geometries[terminal_end:terminal_end+half],geometries[terminal_end+half:]):
        for a,b in zip(sequence,sequence[1:]):motion.append(float(np.linalg.norm(np.asarray(a.exterior.coords)[:4]-np.asarray(b.exterior.coords)[:4],axis=1).max()))
    if max(motion)>civil['interval_motion_padding']:errors.append('Vehicle interval motion exceeds plan pad')
    if vehicle_fail:errors.append(['Actual bus body/road sweep failed',vehicle_fail[:10]])
    # The station link is three metres wide and completely outside road cells.
    portal=spec['station_pedestrian_interface'];portal_cells=[]
    for px in range(portal['x'][0],portal['x'][1]+1):
        for pz in range(portal['z'][0],portal['z'][1]+1):
            ij=idx(px,pz);ok=walk[ij] and not road[ij] and actual_floor[ij] and headroom[ij] and feet[ij]==portal['feet_y']
            portal_cells.append(dict(xz=[px,pz],feet=float(feet[ij]),passed=bool(ok)))
    if not all(p['passed']for p in portal_cells):errors.append('Fixed pedestrian station interface failed')
    footway=walk&~road&actual_floor&headroom;foot_labels,nfoot=label(footway)
    entry_label=int(foot_labels[idx(spec['station_feet'][0],spec['station_feet'][2])])
    pedestrian_reach=(foot_labels==entry_label)&footway if entry_label else np.zeros(walk.shape,bool)
    nearstreet=(xx-spec['street_anchor'][0])**2+(zz-spec['street_anchor'][2])**2<=100
    if not np.any(pedestrian_reach&nearstreet):errors.append('Station pedestrian link has no continuous footway to original street')
    band=level_crossing_band(spec,xx);train_body=[]
    for iz,ix in np.argwhere(band&walk):
        px,pz,py=x+int(ix),z+int(iz),int(floor[iz,ix])
        train_body+=[[px,y,pz]for y in range(py+1,py+6)if solid(e.state(px,y,pz))]
    if band.any() and not np.all(feet[band&walk]==spec['level_crossing']['rail_y']):
        errors.append('Level crossing surface is not at rail height')
    if train_body:errors.append(['Solid above a level crossing surface',train_body[:10]])
    # Exact future open-water envelope: existing soil awaits Stage3 excavation;
    # no newly introduced solid may occupy the reserved water/air cross-section.
    points=np.asarray(profile['horizontal_points']);along=np.asarray(profile['along']);tree=cKDTree(points)
    wet=d['future_water_no_fill'];water_fail=[];water_rows=[]
    thresholds=np.full(walk.shape,-999.,float)
    _,nearest=tree.query(np.c_[xx.ravel()+.5,zz.ravel()+.5]);svalues=along[nearest].reshape(walk.shape)
    crossings=civil['hydraulic_crossings']
    for iz,ix in np.argwhere(wet):
        s=svalues[iz,ix];c=min(crossings,key=lambda c:max(c['along'][0]-s,0,s-c['along'][1]))
        thresholds[iz,ix]=c['design_high_water_surface']+c['minimum_clearance']
    for r in rows:
        px,py,pz=r['pos'];ij=idx(px,pz)
        if wet[ij] and solid(r['after']) and py<thresholds[ij]-1e-8:water_fail.append(r)
    if water_fail:errors.append(['New solids occupy future water clearance',water_fail[:10]])
    for c in crossings:
        use=wet&walk&(svalues>=c['along'][0])&(svalues<=c['along'][1])
        underside=floor-np.where(slab,1,0)
        water_rows.append(dict(id=c['id'],reserved_columns=int(use.sum()),minimum_observed_underside=float(underside[use].min())if use.any()else None,
            design_high_water_surface=c['design_high_water_surface'],minimum_required_clearance=c['minimum_clearance'],
            no_actual_water_or_navigation_claim=True,accepted_support_stations=c['accepted_support_stations']))
    footing_fail=[];seeds=set();footing_checks=[]
    nodes={tuple(r['pos'])for r in rows if solid(r['after'])}
    nodes|={(x+int(ix),int(floor[iz,ix]),z+int(iz))for iz,ix in np.argwhere(walk)}
    for support in civil['full_bank_footings']:
        for f in support['footings']:
            bad=[]
            for r in f['bearing_states']:
                px,py,pz=r['pos'];ij=idx(px,pz)
                if source.state(px,py,pz)!='minecraft:stone' or e.state(px,py,pz)!='minecraft:stone' or wet[ij]:bad.append(r['pos'])
                if (px,py+1,pz)in nodes:seeds.add((px,py+1,pz))
            footing_checks.append(dict(crossing=support['crossing'],center=f['center_xz'],bearing_y=f['bearing_y'],measured_bearing_cells=9,passed=not bad))
            footing_fail+=bad
    reached=set(seeds);queue=deque(seeds)
    while queue:
        px,py,pz=queue.popleft()
        for q in ((px+1,py,pz),(px-1,py,pz),(px,py+1,pz),(px,py-1,pz),(px,py,pz+1),(px,py,pz-1)):
            if q in nodes and q not in reached:reached.add(q);queue.append(q)
    bridge_nodes={(x+int(ix),int(floor[iz,ix]),z+int(iz))for iz,ix in np.argwhere(d['bridge_span'])}
    disconnected=bridge_nodes-reached
    if footing_fail or disconnected:errors.append(['Foundation or physical deck connectivity failed',footing_fail[:10],list(disconnected)[:10]])
    # Cached native geometry is checked geometrically, without opening the native DB.
    curves=read(Path(spec['authority'])/'native-curves.json');native_hits=[];native_nearest=[]
    edits=np.asarray([r['pos']for r in rows]);horizontal=cKDTree(edits[:,[0,2]])
    for kind,records in curves.items():
        if not isinstance(records,list):continue
        for r in records:
            p=np.asarray(r['points']);dist,at=horizontal.query(p[:,[0,2]])
            i=int(np.argmin(dist));native_nearest.append(dict(kind=kind,id=r['id'],distance=float(dist[i]),point=p[i].tolist()))
            for j in np.flatnonzero(dist<2.5):
                q=edits[at[j]]
                if p[j,1]-2<=q[1]<=p[j,1]+6:native_hits.append(dict(kind=kind,id=r['id'],native_point=p[j].tolist(),edit=q.tolist()))
    if native_hits:errors.append(['Candidate intersects retained native running envelope',native_hits[:10]])
    # native-curves.json predates the station batches; the snapshot is the installed rail set.
    near_rails=near_points(load_rails(spec['native_snapshot']),edits[:,[0,2]],6)
    if near_rails:errors.append(['Candidate within 6m of an installed rail chord',near_rails[:10]])
    # Negative controls call the same source, footing, floor, occupancy and
    # hydraulic predicates with one changed fact each. No world is modified.
    def expect_rejected(name,baseline,mutation,evidence):
        try:base_ok=bool(baseline())
        except (ValueError,IndexError):base_ok=False
        try:rejected=not bool(mutation())
        except (ValueError,IndexError):rejected=True
        negative.append(dict(name=name,positive_control_passed=base_ok,rejected=base_ok and rejected,evidence=evidence))
    pos=next(iter(exact));good=source.state(*pos);wrong='minecraft:air' if good!='minecraft:air' else 'minecraft:stone'
    def row_matches(row):return source.state(*row['pos'])==row['before'] and delta.get(tuple(row['pos']))==(row['before'],row['after'])
    expect_rejected('stale_before',lambda:row_matches(exact[pos]),lambda:row_matches(dict(exact[pos],before=wrong)),dict(pos=pos,real_before=good,injected_before=wrong))
    def unknown_column():
        sx,sz,_,_=source.bounds;ij=(pos[2]-sz,pos[0]-sx);old=source.measured['full'][ij]
        try:source.measured['full'][ij]=False;return bool(source.state(*pos))
        finally:source.measured['full'][ij]=old
    expect_rejected('unknown_source_column',lambda:bool(source.state(*pos)),unknown_column,dict(pos=pos,injected_full=False))
    expect_rejected('outside_vertical_extent',lambda:bool(source.state(*pos)),lambda:bool(source.state(pos[0],320,pos[2])),dict(valid_y=[-128,319],injected_y=320))
    at=np.argwhere(actual_road)[len(np.argwhere(actual_road))//2];iy,ix=map(int,at);px,pz=x+ix,z+iy;py=int(floor[iy,ix])
    def changed_state(at,state):return lambda a,b,c:state if (a,b,c)==at else e.state(a,b,c)
    expect_rejected('missing_road_wearing_course',lambda:inspect_public_cell(e.state,px,pz),
        lambda:inspect_public_cell(changed_state((px,py,pz),'minecraft:air'),px,pz),dict(pos=[px,py,pz],injected='minecraft:air'))
    expect_rejected('vehicle_headroom_wall',lambda:inspect_public_cell(e.state,px,pz),
        lambda:inspect_public_cell(changed_state((px,py+2,pz),'minecraft:stone'),px,pz),dict(pos=[px,py+2,pz],injected='minecraft:stone'))
    f=civil['full_bank_footings'][0]['footings'][0];at=tuple(f['bearing_states'][4]['pos'])
    def bearing_matches(state_at):return all(state_at(*q['pos'])=='minecraft:stone' for q in f['bearing_states'])
    expect_rejected('foundation_not_original_stone',lambda:bearing_matches(e.state),lambda:bearing_matches(changed_state(at,'minecraft:dirt')),dict(pos=at,injected='minecraft:dirt',complete_footprint_cells=9))
    wetpos=np.argwhere(wet&walk)[0];iy,ix=map(int,wetpos);at=(x+ix,math.floor(thresholds[iy,ix])-1,z+iy)
    def hydraulic_rows_ok(changes):
        return all(not(solid(q['after']) and wet[idx(q['pos'][0],q['pos'][2])] and q['pos'][1]<thresholds[idx(q['pos'][0],q['pos'][2])])for q in changes)
    injected=dict(pos=list(at),before=e.state(*at),after='minecraft:stone')
    expect_rejected('solid_inside_future_channel',lambda:hydraulic_rows_ok(rows),lambda:hydraulic_rows_ok(rows+[injected]),dict(injected=injected,required_underside=float(thresholds[iy,ix])))
    px,pz=spec['station_feet'][0],spec['station_feet'][2];py=int(floor[idx(px,pz)])
    expect_rejected('wrong_station_feet',lambda:inspect_public_cell(e.state,px,pz),
        lambda:inspect_public_cell(changed_state((px,py,pz),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'),px,pz),dict(pos=[px,py,pz],injected_lower_half_slab=True))
    if not all(q['rejected']for q in negative):errors.append('A negative control was not rejected')
    report=dict(schema='bounded-station-access-independent-v1',errors=errors,source_devices_preserved=bool(devices_ok),source_actors_preserved=bool(actors_ok),
        vehicle_sweep_passed=not vehicle_fail and max(motion)<=civil['interval_motion_padding'],full_width_walk_passed=not common['errors'] and all(p['passed']for p in portal_cells),
        future_water_clearance_passed=not water_fail,supports_grounded=not footing_fail and not disconnected,negative_cases=negative,
        exact_cells=len(rows),full_source_checked_cells=len(rows),manifest_delta_source_exact=not stale,
        reference_vehicle=dict(**bus,actual_asset=False,pose_count=len(point_poses),directions=[-1,1],maximum_pose_corner_motion=max(motion),motion_padding=civil['interval_motion_padding'],
            maximum_floor_height_range=max(r['floor_range'][1]-r['floor_range'][0]for r in pose_rows),body_bottom_rule='Conservative highest wearing-course surface under full footprint; no wheel/suspension simulation'),
        vehicle_failures=vehicle_fail,pedestrian_interface=portal_cells,continuous_sidewalk_cells=int(pedestrian_reach.sum()),sidewalk_components=int(nfoot),
        ground_bearing_checks=footing_checks,bridge_surface_cells=len(bridge_nodes),bridge_cells_connected_to_measured_stone=len(bridge_nodes&reached),
        water_crossings=water_rows,future_channel_new_solid_violations=water_fail,native_geometry_intersections=native_hits,
        nearest_cached_native_curve=sorted(native_nearest,key=lambda q:q['distance'])[:3],captured_devices=len(source.devices),
        production_replay_passed=False,runtime_driving_passed=False,world_opened=False,world_written=False,whole_station_complete=False)
    write(out/'vehicle-pose-checks.json',pose_rows);write(out/'access-independent-check.json',report)
    write(out/'functional-check.json',dict(errors=errors,scope='finite offline road and pedestrian geometry',whole_map_completion=False,production_replay_pending=True))
    manifest['streets']=[dict(id=spec['id'],status='prepared',walk_columns=int(walk.sum()))];write(out/'manifest.json',manifest)
    print(json.dumps(dict(errors=errors,exact_cells=len(rows),bus_poses=len(point_poses),footings=len(footing_checks),bridge_unconnected=len(disconnected)),ensure_ascii=False))
    if errors:raise ValueError('Independent access verification failed')


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('mode',choices=('survey','profile','civil','author','verify'))
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--design',type=Path)
    args=parser.parse_args()
    if args.mode=='author':
        if args.design is None:parser.error('author requires --design')
        author(args.config,args.design,args.out)
    elif args.mode=='verify':verify(args.config,args.out)
    else:dict(survey=survey,profile=longitudinal_design,civil=civil_constraints)[args.mode](args.config,args.out)


if __name__=='__main__':main()
