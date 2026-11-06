"""Select a measured station-access alignment; never authors world edits.

Input is a bounded frozen FULL-chunk source, cached geography, installed rail
plans and measured public authority. Unknown sections are never treated as air.
"""
import argparse,collections,heapq,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Point,LineString,box,shape,mapping
from shapely.ops import unary_union,nearest_points
from author_hakone_lakefront import Editor
from author_station_layout import collision,open_state

def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
def key(p):return tuple(round(float(v),4)for v in p)

def graph_route(features,start,end,bounds,forbidden):
    crop=box(bounds[0]+8,bounds[1]+8,bounds[2]-8,bounds[3]-8)
    roads=[shape(q['geometry']).intersection(crop)for q in features if q['properties']['source_layer']=='RdCL']
    noded=unary_union([q for q in roads if not q.is_empty]);segments=[]
    for q in getattr(noded,'geoms',[noded]):
        if q.geom_type!='LineString':continue
        ps=list(q.coords)
        for a,b in zip(ps,ps[1:]):
            line=LineString([a,b])
            if line.intersects(forbidden):continue
            segments.append(line)
    snaps=[]
    for p in(start,end):
        line=min(segments,key=lambda q:q.distance(Point(p)));at=line.interpolate(line.project(Point(p)));snaps.append((line,at))
    adjacency=collections.defaultdict(list)
    for line in segments:
        pts=[Point(line.coords[0]),Point(line.coords[-1])]+[p for q,p in snaps if q.equals(line)];pts.sort(key=line.project)
        for a,b in zip(pts,pts[1:]):
            ka,kb=key(a.coords[0]),key(b.coords[0]);d=a.distance(b)
            if d>1e-8:adjacency[ka].append((kb,d));adjacency[kb].append((ka,d))
    for p,(_,snap)in zip((start,end),snaps):
        a,b=key(p),key(snap.coords[0]);d=math.dist(a,b)
        adjacency[a].append((b,d));adjacency[b].append((a,d))
    start,end=key(start),key(end);dist={start:0};parent={start:None};queue=[(0,start)]
    while queue:
        cost,p=heapq.heappop(queue)
        if cost!=dist[p]:continue
        if p==end:break
        for q,w in adjacency[p]:
            nd=cost+w
            if nd<dist.get(q,math.inf):dist[q]=nd;parent[q]=p;heapq.heappush(queue,(nd,q))
    if end not in parent:raise ValueError('No cached-road topology route inside measured source')
    ps=[];p=end
    while p is not None:ps.append(p);p=parent[p]
    return list(reversed(ps))

def select(a):
    import nbtlib
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    c=read(a.config);out=a.out;out.mkdir(exist_ok=False);source=Path(c['source']);cap=read(source/'capture.json');bounds=cap['bounds_xz'];l,t,r,b=bounds
    if cap.get('unavailable_chunks')or set(cap['chunk_statuses'])!={'full'}:raise ValueError('Complete FULL source required')
    with np.load(source/'measured.npz')as f:m={k:f[k].copy()for k in f.files}
    features=read(c['features']);editor=Editor(source);devices=nbtlib.load(source/'captured-devices.dat')['Devices'];device_rows=[dict(pos=[int(q[k])for k in('x','y','z')],id=str(q.get('id','')))for q in devices]
    installed=read(c['installed_station_plan']);rails=[dict(**q,line=LineString([[q['from'][0]+.5,q['from'][2]+.5],[q['to'][0]+.5,q['to'][2]+.5]]))for q in installed['rails']]
    forbidden=box(*c['avoid_station_xz']);start=c['street_anchor'][::2];end=c['bridge_west_xz'];west=[];ports=[start]+c.get('western_via_xz',[])+[end]
    for pa,pb in zip(ports,ports[1:]):
        leg=graph_route(features,pa,pb,bounds,forbidden);west.extend(leg if not west else leg[1:])
    proposal=read(c['proposal'])['cached_road_path'];join=min(range(len(proposal)),key=lambda i:math.dist(proposal[i],end));route=west+proposal[join+1:]+[c['station_feet'][::2]];line=LineString(route);simple=line.simplify(c.get('simplify',3),preserve_topology=True)
    sampled=[]
    for d in np.linspace(0,line.length,math.ceil(line.length)+1):
        p=line.interpolate(d);x,z=math.floor(p.x),math.floor(p.y)
        if not(l<=x<=r and t<=z<=b):raise ValueError('Route left frozen source')
        sampled.append(dict(distance=float(d),xz=[p.x,p.y],top=int(m['top'][z-t,x-l]),highest=int(m['highest'][z-t,x-l]),protected=bool(m['protected'][z-t,x-l])))
    crossings=[]
    for q in rails:
        rr=q['line'];a0,a1=np.array(rr.coords[0]),np.array(rr.coords[-1]);u=(a1-a0)/rr.length;future=LineString([a0-u*120,a1+u*120]);cross=line.intersection(future)
        crossings.append(dict(rail_id=q['id'],rail_y=q['from'][1],installed_endpoints=[q['from'],q['to']],installed_line=mapping(rr),tangent_reservation=mapping(future),route_crossing=mapping(cross),installed_track_crossed=line.intersects(rr),future_tangent_length_per_end=120))
    water=[]
    for q in features:
        if q['properties']['source_layer']not in('WA','RvrCL','WStrL'):continue
        g=shape(q['geometry']);inter=line.intersection(g.buffer(3)if g.geom_type!='Polygon'else g.buffer(3))
        if not inter.is_empty:water.append(dict(index=q['index'],layer=q['properties']['source_layer'],source_properties=q['properties'],geometry=q['geometry'],route_intersection=mapping(inter)))
    near_devices=[dict(**q,distance_to_route=line.distance(Point(q['pos'][0]+.5,q['pos'][2]+.5)))for q in device_rows]
    result=dict(source=c['source'],section_source=cap['exact_station_source'],authority=c['authority'],features=c['features'],street_anchor=c['street_anchor'],station_feet=c['station_feet'],horizontal_ports=[list(q)for q in simple.coords],raw_route=[list(q)for q in line.coords],length=line.length,complete_source_full_chunks=cap['chunk_statuses']['full'],source_bounds_xz=bounds,devices=near_devices,rail_crossings=crossings,water_features_crossed=water,profile=sampled,selection_only=True,world_written=False,road_constructed=False,vertical_design_pending=True)
    write(out/'selection.json',result)
    fig,ax=plt.subplots(figsize=(17,9));ax.imshow(m['top'],extent=(l,r+1,b+1,t),cmap='terrain',alpha=.5)
    for q in features:
        layer=q['properties']['source_layer'];g=shape(q['geometry'])
        if layer not in('RdCL','RailCL','WA','RvrCL'):continue
        if layer=='WA':
            for p in getattr(g,'geoms',[g]):
                if p.geom_type=='Polygon':ax.fill(*p.exterior.xy,color='deepskyblue',alpha=.3)
        else:
            for p in getattr(g,'geoms',[g]):
                if p.geom_type=='LineString':ax.plot(*p.xy,color={'RdCL':'sienna','RailCL':'purple','RvrCL':'blue'}[layer],lw=.6)
    for q in rails:ax.plot(*q['line'].xy,color='black',lw=3)
    ax.plot(*line.xy,color='red',lw=2,label='Selected cached road topology');ax.plot(*LineString(proposal).xy,color='orange',ls='--',lw=1,label='Rejected ungraded original')
    ax.scatter(*zip(*[q['pos'][::2]for q in device_rows]),color='magenta',s=12,label='Original devices');ax.set(xlim=(l,r),ylim=(b,t),xlabel='World X',ylabel='World Z');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(out/'selection.png',dpi=150);plt.close(fig)
    print('Selected',round(line.length,2),'m;',len(simple.coords),'controls; crossing installed railway:',[q['installed_track_crossed']for q in crossings]);print('Nearest devices:',sorted([(q['id'],round(q['distance_to_route'],2),q['pos'])for q in near_devices],key=lambda q:q[1])[:5])

def ramp(s,height,length,acceleration=.0025):
    """Finite zero-end-grade parabola/constant-grade/parabola transition."""
    distance=abs(height);peak=(acceleration*length-math.sqrt((acceleration*length)**2-4*acceleration*distance))/2;transition=peak/acceleration
    s=max(0,min(length,s))
    gain=.5*acceleration*s*s if s<transition else distance-.5*acceleration*(length-s)**2 if s>length-transition else .5*acceleration*transition**2+peak*(s-transition)
    grade=acceleration*s if s<transition else acceleration*(length-s)if s>length-transition else peak
    return math.copysign(gain,height),math.copysign(grade,height),peak

def design(a):
    """Check a proposed design against complete frozen cells; do not author it."""
    import nbtlib
    from plan_station_access_corridor import CapturedSurface,rounded_alignment,finite_intervals,SOIL,PLANTS,AIR,PAVEMENT
    from shapely.prepared import prep
    c=read(a.config);a.out.mkdir(exist_ok=False);source=CapturedSurface(c['source']);line,along,points,curves=rounded_alignment(c);features=read(c['selection_features']);natural=SOIL|PLANTS|AIR;errors=[]
    ascent=c.get('west_ascent_length',176);plateau_end=c.get('rail_bridge_plateau_end',300);descent=c.get('descent_length',176)
    def height(s):
        if s<ascent:return -73+ramp(s,9,ascent)[0]
        if s<plateau_end:return -64
        if s<plateau_end+descent:return -64+ramp(s-plateau_end,-9,descent)[0]
        return -73
    heights=np.asarray([height(float(s))for s in along]);grades=np.gradient(heights,along)
    if max(abs(grades))>c['maximum_continuous_grade']+1e-7:errors.append('Grade limit')
    if max(abs(np.gradient(grades,along)))>c['maximum_grade_change_per_m']+1e-7:errors.append('Grade change limit')
    road_scope=line.buffer(c['clear_width']/2+2,cap_style=2);court=c['forecourt'];court_scope=Point(court['center'][::2]).buffer(court['sidewalk_outer_radius']);walk=LineString(c['pedestrian_route_xz']);walk_scope=walk.buffer(1.5,cap_style=2);scope=road_scope.union(court_scope).union(walk_scope)
    l,t,r,b=source.bounds
    if not box(l,t,r+1,b+1).covers(scope):raise ValueError('Exact design left known FULL source')
    devices=[dict(pos=[int(d[k])for k in('x','y','z')],id=str(d['id']))for d in source.devices];foreign=[];blocked=[];wet=[];device_hits=[];test=prep(scope)
    for x in range(math.floor(scope.bounds[0]),math.ceil(scope.bounds[2])):
        for z in range(math.floor(scope.bounds[1]),math.ceil(scope.bounds[3])):
            cell=box(x,z,x+1,z+1)
            if not test.intersects(cell):continue
            p=Point(x+.5,z+.5);s=line.project(p);feet=height(s)if road_scope.intersects(cell)else -73
            ground=source.top(x,z)
            for y in range(min(ground-1,math.floor(feet-1)),max(ground+12,math.ceil(feet+5))):
                state=source.state(x,y,z);bare=state.split('[')[0]
                if bare in('minecraft:water','minecraft:lava'):wet.append(dict(pos=[x,y,z],state=state))
                elif bare not in natural|PAVEMENT:
                    row=dict(pos=[x,y,z],state=state,road_feet=feet);foreign.append(row)
                    if any(y+q[4]>feet-1+1e-7 and y+q[1]<feet+4.5 for q in collision(state)):blocked.append(row)
    for q in devices:
        x,y,z=q['pos'];q['minimum_horizontal_distance_to_works']=scope.distance(Point(x+.5,z+.5));q['minimum_distance_to_road_axis']=line.distance(Point(x+.5,z+.5))
        if scope.intersects(box(x,z,x+1,z+1)):device_hits.append(q)
    if blocked:errors.append('Existing exact structure intersects proposed deck/vehicle/guards')
    if device_hits:errors.append('Original device in works footprint')
    water=unary_union([shape(q['geometry'])for q in features if q['properties']['source_layer']in('WA','RvrCL','WStrL')]);hydro_buffer=water.buffer(3)
    if court_scope.intersects(hydro_buffer):errors.append('Forecourt covers future water reservation')
    if walk_scope.intersects(hydro_buffer):errors.append('Footpath covers future water reservation')
    road_geo=unary_union([shape(q['geometry'])for q in features if q['properties']['source_layer']=='RdCL']);departure=max(road_geo.distance(Point(p))for p in points)
    if departure>18:errors.append('Road exceeds 18m cached corridor adaptation')
    installed=read(c['installed_station_plan']);fixed=[];reserved=[]
    for rr in installed['rails']:
        a0=np.asarray(rr['from'],float)[[0,2]]+.5;a1=np.asarray(rr['to'],float)[[0,2]]+.5;u=(a1-a0)/np.linalg.norm(a1-a0);fixed.append(LineString([a0,a1]));reserved.append(LineString([a0-u*120,a1]))
    real_rail=unary_union([shape(q['geometry'])for q in features if q['properties']['source_layer']=='RailCL'and q['properties'].get('vt_rtcode')=='JR以外']);rail_reserved=real_rail.buffer(12).union(unary_union(reserved).buffer(12));intervals=finite_intervals(line,rail_reserved.buffer(c['clear_width']/2+2));top=max(read(Path(c['model_source'])/(ident+'.json'))['visible_motion_bounds'][1][1]for ident in c['models']);required=-70+top+.03+.5+c['major_bridge']['deck_depth']
    for row in intervals:
        ss=np.linspace(*row['along'],max(2,math.ceil(row['length']/.25)+1));row['minimum_feet_y']=min(height(float(v))for v in ss);row['required_minimum_feet_y']=required;row['clearance_over_future_upper_model']=row['minimum_feet_y']-1-(-70+top+.03)
        if row['minimum_feet_y']<required:errors.append('Rail reserve vehicle clearance')
    if road_scope.intersects(unary_union(fixed).buffer(2)):errors.append('Existing station rail footprint crossed')
    c['rail_crossings']=[dict(name='Kayama north geographic running corridor',rail_y=-71,future_rail_y_range=[-72,-70],model_visible_bounds_source=c['model_source'],model_top_relative_to_rail=top,model_margin=.03,minimum_model_clearance=.5,required_road_feet_y=required,road_intervals=intervals,pier_exclusion_geometry=mapping(rail_reserved),bounds_xyz=[rail_reserved.bounds[0],-73,rail_reserved.bounds[1],rail_reserved.bounds[2],-65,rail_reserved.bounds[3]],structure='Road over railway. Above-deck steel side trusses and cross beams, no below-deck girder in the reserved train envelope.',future_native_rail_curve_registration_pending=True)]
    c['vertical_controls']=[dict(along=0,feet_y=-73,grade=0),dict(along=ascent,feet_y=-64,grade=0),dict(along=plateau_end,feet_y=-64,grade=0),dict(along=plateau_end+descent,feet_y=-73,grade=0),dict(along=line.length,feet_y=-73,grade=0)];c['vertical_profile_method']='Symmetric parabolic grade transitions at maximum change 0.0025/m, constant grade between transitions; rise 9m over '+str(ascent)+'m and fall over '+str(descent)+'m';c['source_device_reservations']=devices
    report=dict(errors=errors,source=c['source'],full_chunks=source.capture['chunk_statuses']['full'],source_devices=len(devices),actors=len(source.capture['actors']),length=line.length,curvature=curves,maximum_continuous_grade=float(max(abs(grades))),maximum_grade_change=float(max(abs(np.gradient(grades,along)))),maximum_GIS_road_departure=departure,foreign_source_cells=foreign,proposed_deck_vehicle_guard_collisions=blocked,device_intrusions=device_hits,actual_water_cells=wet,road_rail_intervals=intervals,station_rails_not_crossed=True,forecourt_water_clearance=court_scope.distance(water),pedestrian_water_clearance=walk_scope.distance(water),profile=[dict(along=float(s),xz=list(p),feet_y=float(h),grade=float(g))for s,p,h,g in zip(along,points,heights,grades)],world_written=False,selected_geometry_only=True,authoring_and_exact_road_bus_sweeps_pending=True)
    write(a.out/'design-input.json',c);write(a.out/'design-check.json',report);write(a.out/'alignment.geojson',dict(type='FeatureCollection',features=[dict(type='Feature',properties={'role':'proposed access, not authored'},geometry=mapping(line)),dict(type='Feature',properties={'role':'clear forecourt'},geometry=mapping(court_scope)),dict(type='Feature',properties={'role':'3m independent station footpath'},geometry=mapping(walk))]));print('Design',len(errors),'errors;',line.length,'m;',len(devices),'devices;',len(blocked),'existing-structure hits;',len(foreign),'foreign cells; grade',max(abs(grades)));print(errors)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--mode',choices=('select','design'),default='select');p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();globals()[a.mode](a)
