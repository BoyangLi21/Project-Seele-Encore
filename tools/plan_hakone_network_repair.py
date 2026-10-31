"""Commission complete street footprints before composing any saved blocks.

This replaces 'whatever pavement survived is the road' with authored centre
lines, complete widths, native rail curves and explicit finite building rooms.
All work is offline; the current save remains the only source of contents.
"""
import argparse, gzip, json, math, struct, heapq
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, distance_transform_edt, label
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from prepare_hakone_main_terrain import sample_grid
from repair_hakone_surface_ownership import load_grid, sampled
from hakone_earthworks import min_slope_envelope
from prepare_hakone_main_districts import line, route
from complete_hakone_transport_surface import station_boxes
from plan_ashi_landscape_r54 import NATURAL
from plan_hakone_main_districts import ROAD_MATERIALS


def raster(bounds, paths, width_key):
    x,z,X,Z=bounds;im=Image.new('L',(X-x+1,Z-z+1));draw=ImageDraw.Draw(im)
    for p in paths:
        width=p[width_key]
        if width:draw.line([(round(a-x),round(b-z))for a,b in p['points']],fill=1,width=width,joint='curve')
    return np.asarray(im,bool)


def surveyed_route(start,goal,blocked,surveyed,bounds):
    """Prefer cached real street corridors when restoring a long missing link."""
    x0,z0,x1,z1=bounds;cost={start:0};parent={};queue=[(0,0,start)]
    while queue:
        _,g,p=heapq.heappop(queue)
        if g!=cost[p]:continue
        if p==goal:
            points=[p]
            while p in parent:p=parent[p];points.append(p)
            return points[::-1]
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz
            if not(x0<=q[0]<=x1 and z0<=q[1]<=z1)or(blocked[q[1]-z0,q[0]-x0]and q!=goal):continue
            ng=g+(1 if surveyed[q[1]-z0,q[0]-x0]else 24)
            if ng<cost.get(q,10**12):
                cost[q]=ng;parent[q]=p;heapq.heappush(queue,(ng+abs(q[0]-goal[0])+abs(q[1]-goal[1]),ng,q))
        if len(cost)>1500000:return None


def live_curves(gis,world):
    live={p.name for p in(world/'mtr/projectseele/geofront/rails').rglob('*')if p.is_file()}
    old=json.loads((gis.parent/'repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))['curves']
    trains=[r for r in old if r['id']in live and r['mode']=='TRAIN'and any(-120<p[1]<310 for p in r['points'])]
    trains+=json.loads((gis/'tozan-native/validated-v7/track_samples.json').read_text('utf8'))
    return dict(trains=trains,ropeway=json.loads((gis/'ropeway-native/validated/track_samples.json').read_text('utf8')))


def network_grade(grade2, walk, city, entrances):
    """Propagate grade along streets, never across a valley between two roads."""
    ids=np.full(walk.shape,-1,np.int32);ids[walk]=np.arange(walk.sum(),dtype=np.int32)
    rows=[];cols=[]
    for left,right in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:,1:],np.s_[:,:-1])]:
        ok=walk[left]&walk[right];a,b=ids[left][ok],ids[right][ok]
        rows.extend((a,b));cols.extend((b,a))
    row=np.concatenate(rows);col=np.concatenate(cols);n=int(walk.sum())
    def envelope(indices,values):
        graph=coo_matrix((np.concatenate((np.ones(len(row),np.float32),values+1000)),
            (np.concatenate((row,np.full(len(indices),n,np.int32))),np.concatenate((col,indices)))),shape=(n+1,n+1)).tocsr()
        return dijkstra(graph,directed=True,indices=n)[:n]-1000
    fixed=(city|np.isfinite(entrances))&walk;values=np.where(city,160,entrances)[fixed]
    upper=envelope(ids[fixed],values);lower=-envelope(ids[fixed],-values)
    bad=lower>upper+.01
    if bad.any():
        z,x=np.nonzero(walk);q=np.flatnonzero(bad)
        raise ValueError(('Conflicting commissioned road/entrance grades',len(q),[(int(x[i]),int(z[i]),float(lower[i]),float(upper[i]))for i in q[:6]]))
    initial=np.clip(grade2[walk],lower,upper)
    result=envelope(np.arange(n),initial)
    out=grade2.copy();out[walk]=np.rint(result);out[city]=160
    return out.astype(np.int16)


def plan(a):
    a.out.mkdir(parents=True,exist_ok=False)
    bounds=[-2112,-1152,2559,1535];x0,z0,x1,z1=bounds
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1];shape=xx.shape
    main=load_grid(a.gis/'main-district-integration-v1/coupled-grading.npz')
    original=load_grid(a.gis/'main-district-integration-v1/district-plan.npz')
    valley=load_grid(a.gis/'valley-integration-v12/grading.npz')
    city=load_grid(a.gis/'city-south-streets-v3/surface.npz')
    catalog=json.loads((a.gis/'street-refinement-20261031/candidate-v1/catalog.json').read_text('utf8'))
    core=sampled(city,'cross',xx,zz).astype(bool)
    cityroad=sampled(city,'carriage',xx,zz).astype(bool)&core
    citypaved=sampled(city,'paved',xx,zz).astype(bool)&core
    layout=json.loads((a.gis/'main-district-integration-v1/district-plan.json').read_text('utf8'))
    paths=[dict(points=s['points'],road=s['width'],walk=s['width']+4 if s['width'] else 3)for s in layout['streets']if not s['tunnel']]
    rawroad=raster(bounds,paths,'road');rawwalk=raster(bounds,paths,'walk')
    mainarea=(xx>=main['bounds'][0])&(xx<=main['bounds'][2])&(zz>=main['bounds'][1])&(zz<=main['bounds'][3])
    valleyarea=(xx>=valley['bounds'][0])&(xx<=valley['bounds'][2])&(zz>=valley['bounds'][1])&(zz<=valley['bounds'][3])
    # Keep whole commissioned vector segments across the former authoring
    # rectangle. Clipping at X=1024 created artificial dead ends in the save.
    road=rawroad.copy();walk=rawwalk.copy()
    road[valleyarea&~mainarea]=sampled(valley,'road',xx,zz)[valleyarea&~mainarea]
    walk[valleyarea&~mainarea]=sampled(valley,'walk',xx,zz)[valleyarea&~mainarea]
    # Preserve the previously commissioned diversions as complete paths.
    detours=json.loads((a.gis/'main-district-integration-v1/road-detours.json').read_text('utf8'))['paths']
    for p in detours:
        local=[dict(points=p['points'],road=p['width'],walk=p['width']+4)]
        road|=raster(bounds,local,'road');walk|=raster(bounds,local,'walk')
    held=np.zeros(shape,bool);moves=[]
    for r in catalog:
        b=r['occupied_bounds'];x,y,z,X,Y,Z=b
        if r['template']=='city'and core[max(0,min(shape[0]-1,z-z0)),max(0,min(shape[1]-1,x-x0))]and y>83:
            moves.append(dict(id=r['id'],before=b,after=[x,81,z,X,Y-y+81,Z],dy=81-y))
            r['occupied_bounds']=[x,81,z,X,Y-y+81,Z]
        held[max(0,z-z0-2):min(shape[0],Z-z0+3),max(0,x-x0-2):min(shape[1],X-x0+3)]=True
    # These are actual operational rooms, not unbounded column exclusions.
    for x,z,X,Z in [(-110,-155,225,15),(-425,690,-285,830),(350,-177,1350,86)]:
        held[z-z0:Z-z0+1,x-x0:X-x0+1]=True
    stations=station_boxes(a.gis)
    for name in('tozan-native/plan.json','ropeway-native/plan.json'):
        stations.extend([s['min']+s['max']for s in json.loads((a.gis/name).read_text('utf8'))['stations']])
    for x,y,z,X,Y,Z in stations:
        held[max(0,z-z0-2):min(shape[0],Z-z0+3),max(0,x-x0-2):min(shape[1],X-x0+3)]=True
    structures=json.loads(a.structures.read_text('utf8'))if a.structures else dict(ceilings=[],obstacles=[])
    for x,y,z in structures['obstacles']:
        if x0<=x<=x1 and z0<=z<=z1:held[z-z0,x-x0]=True
    if a.obstacles:
        bridge_columns={(x,z)for x,y,z in structures['ceilings']+structures.get('pins',[])}
        for row in json.loads(a.obstacles.read_text('utf8'))['errors']:
            if row[0]!='road-object':continue
            _,x,y,z,states=row
            # Actual solid bodies, not reserved empty railway clearance.
            body=[s.split('[')[0]for s in states[1:3]]
            flexible=NATURAL|{'minecraft:light','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:stone_bricks','minecraft:stone_brick_slab','minecraft:stone_brick_stairs','minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}
            if ((x,z)not in bridge_columns and any(s not in flexible for s in body))or states[0].split('[')[0]in {'minecraft:iron_bars','minecraft:chain','projectseele:street_light_head'}:
                if x0<=x<=x1 and z0<=z<=z1:held[z-z0,x-x0]=True
    water=sampled(original,'water',xx,zz).astype(bool)
    # A surveyed road crossing a stream is a bridge, not a reason to erase
    # its complete width at the water mask and leave two disconnected ends.
    road&=~held&~core;walk&=~held&~core
    obstacles=binary_dilation(held,iterations=6)|water
    diversions=[];unresolved=[]
    for p in paths:
        if not p['road']:continue
        points=[]
        for first,last in zip(p['points'],p['points'][1:]):
            for x,z in line(tuple(map(round,first)),tuple(map(round,last))):
                if x0+8<=x<=x1-8 and z0+8<=z<=z1-8:
                    if not points or points[-1]!=(x,z):points.append((x,z))
        flags=[obstacles[z-z0,x-x0]for x,z in points];i=0
        while i<len(points):
            if not flags[i]:i+=1;continue
            start=i
            while i<len(points)and flags[i]:i+=1
            if start==0 or i==len(points):continue
            span=points[start:i]
            if any(core[z-z0,x-x0]or water[z-z0,x-x0]for x,z in span):continue
            begin,end=points[start-1],points[i]
            routepoints=route(begin,end,obstacles|core,bounds,limit=120000)
            if routepoints:
                r=dict(points=routepoints,road=p['road'],walk=p['walk']);diversions.append(r)
            else:unresolved.append([begin,end])
    road|=raster(bounds,diversions,'road');walk|=raster(bounds,diversions,'walk')
    # Every surveyed street reaching the engineered city receives an explicit
    # connection to its retained street mesh, not four hand-picked gateways.
    blocked=binary_dilation(held,iterations=5)
    near=binary_dilation(core,iterations=14)&~core&rawroad&~blocked
    groups,n=label(near,np.ones((3,3),int));_,nearest=distance_transform_edt(~(cityroad&~blocked),return_indices=True)
    ports=[]
    for k in range(1,n+1):
        zs,xs=np.nonzero(groups==k)
        if len(xs)<2:continue
        iz,ix=min(zip(zs,xs),key=lambda p:(p[0]-nearest[0,p[0],p[1]])**2+(p[1]-nearest[1,p[0],p[1]])**2)
        q=(int(ix+x0),int(iz+z0));goal=(int(nearest[1,iz,ix]+x0),int(nearest[0,iz,ix]+z0))
        if math.dist(q,goal)>180:raise ValueError(('No adjacent urban street',q,goal))
        points=route(q,goal,blocked,bounds,limit=80000)
        if not points:raise ValueError(('City port cannot reach retained road',q,goal))
        p=dict(points=points,road=7,walk=11);ports.append(p)
        road|=raster(bounds,[p],'road');walk|=raster(bounds,[p],'walk')
    road[core]=cityroad[core];walk[core]=citypaved[core]
    # Ramp bodies may cross the city edge, but the old urban surface pattern
    # remains authoritative further inside the core.
    for p in ports:
        road|=raster(bounds,[p],'road');walk|=raster(bounds,[p],'walk')
    road&=~held;walk&=~held
    # Close gaps introduced by finite station/parcel exclusions and historical
    # authoring rectangles. Each link joins existing street components only.
    joins=[];disconnected=[];retired_fragments=[];retired_mask=np.zeros(shape,bool);surveyed=None
    for iteration in range(100):
        groups,n=label(road,np.ones((3,3),int));sizes=np.bincount(groups.ravel());sizes[0]=0
        if n<=1:break
        mainlabel=int(sizes.argmax());mainmesh=groups==mainlabel
        distance,nearest=distance_transform_edt(~mainmesh,return_indices=True)
        eligible=road&~mainmesh&(sizes[groups]>=40)
        if not eligible.any():break
        score=np.where(eligible,distance,np.inf);iz,ix=np.unravel_index(score.argmin(),score.shape)
        if score[iz,ix]>800:
            disconnected=[dict(component=int(i),columns=int(sizes[i]),nearest_gap=float(distance[groups==i].min()))for i in range(1,n+1)if i!=mainlabel and sizes[i]>=40]
            break
        start=(int(ix+x0),int(iz+z0));goal=(int(nearest[1,iz,ix]+x0),int(nearest[0,iz,ix]+z0))
        forbidden=binary_dilation(held,iterations=6)|(water&~binary_dilation(rawwalk,iterations=3))
        # Endpoint carriageways already lie beside their retained structures.
        forbidden[road]=False
        if score[iz,ix]>80:
            if surveyed is None:
                features=json.loads(gzip.decompress((a.gis/'features.world.geojson.gz').read_bytes()))['features'];navigation=[]
                for f in features:
                    if f['properties'].get('source_layer')!='RdCL':continue
                    geom=f['geometry'];parts=[geom['coordinates']]if geom['type']=='LineString'else geom['coordinates']if geom['type']=='MultiLineString'else[]
                    for part in parts:navigation.append(dict(points=part,width=9))
                surveyed=raster(bounds,navigation,'width')|road
            points=surveyed_route(start,goal,forbidden,surveyed,bounds)
        else:points=route(start,goal,forbidden,bounds,limit=200000)
        if not points:
            component=groups==groups[iz,ix]
            if sizes[groups[iz,ix]]<1000 and not(core&component).any():
                # Small strokes fully trapped by retained parcels have no
                # street endpoint. Retire the fragment; catalogued door paths
                # are restored separately below with their real destination.
                retired_mask|=component;road[component]=False;walk[component]=False
                retired_fragments.append(dict(columns=int(component.sum()),witness=[start,goal]));continue
            raise ValueError(('Separated existing streets cannot reconnect',start,goal,int(sizes[groups[iz,ix]])))
        p=dict(points=points,road=7,walk=11);joins.append(p)
        road|=raster(bounds,[p],'road')&~held;walk|=raster(bounds,[p],'walk')&~held
    else:raise ValueError('Street component connections did not converge')
    footways=[];entrances=np.full(shape,np.nan,np.float32)
    moved={r['id']:r for r in moves}
    for r in catalog:
        path=r.get('footway',[])
        if not path:continue
        coords=[(int(p[0]),int(p[2]))for p in path]
        walk|=raster(bounds,[dict(points=coords,width=3)],'width')&~held
        ys=[float(p[1])-1 for p in path]
        if r['id']in moved:ys=np.linspace(moved[r['id']]['after'][1],ys[-1],len(path)).tolist()
        for (x,z),y in zip(coords,ys):
            if x0<=x<=x1 and z0<=z<=z1:footways.append((x,z,y))
        for (x,z),y in zip(coords,ys):
            if x0<=x<=x1 and z0<=z<=z1 and walk[z-z0,x-x0]and not held[z-z0,x-x0]:
                entrances[z-z0,x-x0]=y*2;break
    for x,y,z in structures.get('pins',[]):
        if x0<=x<=x1 and z0<=z<=z1 and walk[z-z0,x-x0]and not held[z-z0,x-x0]:entrances[z-z0,x-x0]=y*2
    tunnel=sampled(main,'tunnel',xx,zz).astype(bool)
    road&=~tunnel;walk&=~tunnel
    with gzip.open(a.resource,'rb')as f:
        magic,fx,fz,step,w,h=struct.unpack('>6i',f.read(24))
        heights=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(np.float32)/16
        wet=np.frombuffer(f.read(w*h*2),'>i2').reshape(h,w).astype(np.int16)
    field=dict(x=np.arange(w)*step+fx,z=np.arange(h)*step+fz,height_y=heights,water=wet)
    ground=np.rint(sample_grid(field,'height_y',xx,zz)).astype(np.int16)
    grade2=ground*2
    commissioned=mainarea&sampled(main,'walk',xx,zz).astype(bool)&~sampled(main,'tunnel',xx,zz).astype(bool)
    grade2[commissioned]=sampled(main,'target',xx,zz)[commissioned]*2
    grade2[valleyarea&~mainarea]=sampled(valley,'grade2',xx,zz)[valleyarea&~mainarea]
    for x,z,y in footways:grade2[z-z0,x-x0]=round(y*2)
    curves=live_curves(a.gis,a.world);crossing=np.zeros(shape,bool)
    for r in curves['trains']:
        for px,py,pz in r['points']:
            x,y,z=math.floor(px),math.floor(py),math.floor(pz)
            if not(x0+3<=x<x1-3 and z0+3<=z<z1-3):continue
            area=np.s_[z-z0-2:z-z0+3,x-x0-2:x-x0+3]
            hit=walk[area]&~held[area]&(abs(grade2[area]/2-(y-1))<=4)&~core[area]
            grade2[area][hit]=2*(y-1);crossing[area]|=hit
    for x,y,z in structures['ceilings']:
        if x0<=x<=x1 and z0<=z<=z1 and walk[z-z0,x-x0]and not core[z-z0,x-x0]:
            grade2[z-z0,x-x0]=min(grade2[z-z0,x-x0],y*2)
    grade2[core]=160
    grade2=network_grade(grade2,walk,core,entrances)
    # At a grade-separated crossing the road headroom must finish below the
    # bridge bed. Resolve the complete approach profile before block authoring.
    for iteration in range(8):
        altered=0
        for r in curves['trains']:
            for px,py,pz in r['points']:
                x,y,z=math.floor(px),math.floor(py),math.floor(pz)
                if not(x0+3<=x<x1-3 and z0+3<=z<z1-3):continue
                area=np.s_[z-z0-2:z-z0+3,x-x0-2:x-x0+3]
                h=(grade2[area]+1)//2
                hit=walk[area]&~held[area]&~core[area]&(h>=y-5)&(h<=y-2)&~np.isfinite(entrances[area])
                if hit.any():grade2[area][hit]=2*(y-6);altered+=int(hit.sum())
        if not altered:break
        grade2=network_grade(grade2,walk,core,entrances)
    marking=np.zeros(shape,bool)
    for p in paths+diversions+ports+joins:
        if p['road']<5:continue
        travelled=0;lastpoint=None
        for first,last in zip(p['points'],p['points'][1:]):
            for x,z in line(tuple(map(round,first)),tuple(map(round,last))):
                if (x,z)==lastpoint:continue
                lastpoint=(x,z);travelled+=1
                if x0<=x<=x1 and z0<=z<=z1 and travelled%12<5:marking[z-z0,x-x0]=True
    marking&=road&~core
    # Keep the existing surface design elsewhere. Only road earthworks and
    # the explicitly lowered urban podiums can change this authority.
    pins=walk&~water;values=(grade2//2).astype(np.float32)
    for r in catalog:
        x,y,z,X,Y,Z=r['occupied_bounds'];area=np.s_[z-z0-3:Z-z0+4,x-x0-3:X-x0+4]
        pins[area]=True;values[area]=y
    # Terrain grading is deliberately broader than the road: a 0.75 slope
    # envelope around cuts, with finite retaining walls
    # only where already occupied plots require them.
    upper=min_slope_envelope(np.where(pins,values,np.inf),.75)
    lower=-min_slope_envelope(np.where(pins,-values,np.inf),.75)
    conflict=lower>upper+.01
    fitted=np.clip(ground,np.minimum(lower,upper),np.maximum(lower,upper))
    fitted[conflict]=(lower[conflict]+upper[conflict])/2
    fitted[pins]=values[pins];fitted[core]=80
    fitted=np.rint(fitted).astype(np.int16)
    for m in moves:
        x,y,z,X,Y,Z=m['after'];fitted[z-z0-4:Z-z0+5,x-x0-4:X-x0+5]=80
    # Valid rails are determined from the current native identity files.
    (a.out/'native-curves.json').write_text(json.dumps(curves),'utf8')
    (a.out/'station-volumes.json').write_text(json.dumps(stations),'utf8')
    np.savez_compressed(a.out/'network.npz',bounds=bounds,road=road,walk=walk,core=core,cityroad=cityroad,citypaved=citypaved,retired_fragments=retired_mask,
        held=held,tunnel=tunnel,grade2=grade2,marking=marking,crossing=crossing,old_ground=ground,ground=fitted,conflicting_terrain_constraints=conflict)
    (a.out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False),'utf8')
    (a.out/'building-moves.json').write_text(json.dumps(moves,ensure_ascii=False,indent=2),'utf8')
    (a.out/'city-ports.json').write_text(json.dumps(ports),'utf8')
    (a.out/'diversions.json').write_text(json.dumps(dict(paths=diversions,unresolved=unresolved)),'utf8')
    (a.out/'street-connectivity.json').write_text(json.dumps(dict(joins=joins,remaining=disconnected,retired_fragments=retired_fragments)),'utf8')
    print(json.dumps(dict(walk=int(walk.sum()),road=int(road.sum()),city_ports=len(ports),lowered_podiums=moves,live_train_curves=len(curves['trains']),terrain_conflict_columns=int(conflict.sum())),ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('gis','out','world','resource'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--obstacles',type=Path)
    p.add_argument('--structures',type=Path)
    plan(p.parse_args())
