"""Build the Tozan corridor, public station approaches and measured village frontages."""
import argparse,json,gzip,math,copy
from pathlib import Path
from collections import deque,Counter
import numpy as np
import nbtlib
from PIL import Image,ImageFilter
from shapely.geometry import LineString,Point
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station,AIR,PAVE,STONE,GLASS
from author_hakone_district_blocks import Frontage
from prepare_hakone_main_districts import route,line
from plan_ashi_landscape_r54 import NATURAL
from plan_hakone_main_districts import ROAD_MATERIALS
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world


def make_building(s,site,label,station=False):
    c=Frontage(site);hx,hz=site['half'];levels=site['floors'];variant=site['variant']
    wall=['minecraft:white_terracotta','minecraft:bricks','minecraft:smooth_sandstone','minecraft:light_gray_concrete'][variant%4]
    accent=['minecraft:dark_oak_planks','minecraft:gray_terracotta','minecraft:polished_andesite'][variant%3]
    # Each frontage has its own entrance, room programme, eaves, shopfront and
    # rear stair. Sites follow surveyed streets and density, not a square grid.
    c.fill(-hx-1,-2,-hz-1,hx+1,-1,hz+2,STONE);c.fill(-hx-1,1,-hz-1,hx+1,levels*5+7,hz+2,AIR)
    for lev in range(levels):
        y=lev*5;c.fill(-hx,y,-hz,hx,y,hz,PAVE)
        for z in(-hz,hz):c.fill(-hx,y+1,z,hx,y+4,z,wall)
        for x in(-hx,hx):c.fill(x,y+1,-hz,x,y+4,hz,wall)
        for x in range(-hx+2,hx-1,4):
            for z in(-hz,hz):c.fill(x,y+2,z,min(x+1,hx-1),y+3,z,GLASS)
        for z in range(-hz+2,hz-1,5):
            for x in(-hx,hx):c.fill(x,y+2,z,x,y+3,z+1,GLASS)
        c.fill(-hx,y+4,hz,hx,y+4,hz,accent)
        c.put(0,y+4,0,'minecraft:sea_lantern')
        c.fill(2,y+1,-hz+2,max(2,hx-2),y+1,-hz+2,'minecraft:bookshelf'if lev else'minecraft:smooth_quartz')
        for x in range(2,hx-1,3):
            c.put(x,y+1,1,'minecraft:oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
            c.put(x,y+2,1,'minecraft:oak_pressure_plate[powered=false]')
            c.put(x,y+1,2,'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    # A full-height two-leaf entrance has the correct lower/upper halves.
    c.fill(-1,1,hz,0,3,hz,AIR)
    for x,hinge in[(-1,'left'),(0,'right')]:
        for y,half in[(1,'lower'),(2,'upper')]:c.put(x,y,hz,f'minecraft:dark_oak_door[facing=south,half={half},hinge={hinge},open=false,powered=false]')
    c.fill(-2,0,hz+1,2,0,hz+3,PAVE)
    c.fill(-hx-1,4,hz+1,hx+1,4,hz+2,'minecraft:red_terracotta'if variant%2 else'minecraft:green_terracotta')
    for lev in range(levels-1):
        y=lev*5;c.fill(-hx+1,y+5,-hz+1,-hx+3,y+5,-hz+6,AIR)
        for step in range(5):
            c.fill(-hx+1,y+1+step,-hz+1+step,-hx+3,y+1+step,-hz+1+step,'minecraft:oak_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
        c.fill(-hx+1,y+5,-hz+6,-hx+3,y+5,-hz+7,PAVE)
    roof=levels*5;c.fill(-hx-1,roof,-hz-1,hx+1,roof,hz+1,accent)
    if station or variant%3:
        for step in range(min(5,hz)):
            for sign in(-1,1):c.fill(-hx-1,roof+1+step,sign*(hz+1-step),hx+1,roof+1+step,sign*(hz+1-step),'minecraft:dark_oak_planks')
        c.fill(-hx-1,roof+min(5,hz),-max(0,hz-4),hx+1,roof+min(5,hz),max(0,hz-4),'minecraft:dark_oak_planks')
    else:
        for z in(-hz,hz):c.fill(-hx,roof+1,z,hx,roof+1,z,wall)
        c.fill(2,roof+1,-3,4,roof+2,-1,'minecraft:polished_andesite')
    # Side drain and planting strip make narrow plots read as street addresses.
    c.fill(hx+1,0,-hz,hx+1,0,hz,'minecraft:gravel')
    for z in(-hz+1,hz-1):c.put(hx+1,1,z,'minecraft:flowering_azalea')
    for op in c.operations:s.fill(op[:6],op[6])
    facing=['south','west','north','east'][site['rotation']]
    s.sign(*c.point(-3,3,hz+1),[label],facing)
    return dict(label=label,site=site,entrance=c.point(-1,1,hz-1),door=c.point(-1,1,hz),approach=c.point(0,0,hz+3),
                upper=c.point(0,6,0)if levels>1 else None,bounds=[*c.point(-hx-2,-3,-hz-2),*c.point(hx+2,levels*5+8,hz+4)])


def author(a):
    candidate=a.candidate;manifest=json.loads((candidate/'manifest.json').read_text('utf8'));capture=json.loads((candidate/'capture.json').read_text('utf8'))
    if(candidate/'valley-buildings.json').exists():raise ValueError('Use a fresh terrain candidate to revise an authored corridor')
    (candidate/'functional-check.json').write_text(json.dumps(dict(errors=['Corridor authoring incomplete'])),'utf8')
    e=Editor(candidate);s=Station(e);x0,z0,x1,z1=manifest['bounds_xz']
    with np.load(candidate/'valley-surface.npz')as f:d={k:f[k]for k in f.files}
    native=json.loads((a.native/'track_samples.json').read_text('utf8'));plan=json.loads((a.native.parent/'plan.json').read_text('utf8'))
    receipt=json.loads((a.native/'native_transit_receipt.json').read_text('utf8'))
    if not receipt['passed']:raise ValueError('Native dispatch is not ready')
    survey=json.loads((candidate.parent/'tozan-survey.json').read_text('utf8'));structures=[]
    for section in survey['sections']:
        for row in section['structures']:
            if row['structure']!='通常部':structures.append((LineString(row['points']),row['structure']))
    with np.load(candidate.parent/'main-district-candidate/district-surface.npz')as f:
        oldbounds=f['bounds'];oldwalk=f['walk'];oldfloor=f['target']
    def former_street(x,y,z):
        ox,oz,X,Z=oldbounds
        return ox<=x<=X and oz<=z<=Z and oldwalk[z-oz,x-ox] and abs(int(oldfloor[z-oz,x-ox])-y)<=3
    cells={};centres=[];track=np.zeros(d['target'].shape,bool);stats=Counter();original=[]
    for r in native:
        if r['id'].startswith('HC'):continue
        for i,(px,py,pz)in enumerate(r['points']):
            x,y,z=math.floor(px),math.floor(py),math.floor(pz)
            for dx in range(-1,2):
                for dz in range(-1,2):cells[x+dx,z+dz]=min(cells.get((x+dx,z+dz),y),y)
            if i%12==0:centres.append([x,y,z])
    for (x,z),y in cells.items():
        track[z-z0,x-x0]=True;surface=int(d['target'][z-z0,x-x0]);point=Point(x,z)
        kinds=[kind for geometry,kind in structures if geometry.distance(point)<4]
        tunnel='トンネル'in kinds or surface>y+7
        bridge='橋・高架'in kinds or surface<y-4
        stats['tunnel'if tunnel else'bridge'if bridge else'cutting']+=1
        for Y in range(y,y+5):
            old=e.state(x,Y,z,True).split('[')[0]
            if old not in NATURAL and not(old in ROAD_MATERIALS and(former_street(x,Y,z)or(900<=x<=943 and 578<=z<=700))):
                original.append([x,Y,z,old])
        if bridge:
            e.fill(x,y-2,z,x,y-2,z,STONE)
            if(x+z)%16<2 and surface<y-3:e.fill(x,surface,z,x,y-3,z,STONE)
        elif surface<y-1:e.fill(x,max(-127,surface),z,x,y-2,z,'minecraft:stone')
        e.put(x,y-1,z,'minecraft:gravel');e.fill(x,y,z,x,y+4,z,AIR)
        if tunnel:e.put(x,y+5,z,STONE)
    if original:raise ValueError('Railway meets original component: '+str(original[:12]))
    for x,y,z in centres:
        if int(d['target'][z-z0,x-x0])>y+7:e.put(x,y+4,z,'minecraft:sea_lantern')
    occupied=d['held'].copy()|d['walk']|d['wet']|np.asarray(Image.fromarray(track).filter(ImageFilter.MaxFilter(9)),bool)
    buildings=[];stations=[];approaches=[];errors=[];builtmask=np.zeros_like(occupied);roadpixels=np.argwhere(d['walk']&~d['road'])
    def fits(x,z,hx,hz):
        if not(x0+hx+5<x<x1-hx-5 and z0+hz+5<z<z1-hz-5):return False
        return not occupied[z-hz-z0-3:z+hz-z0+4,x-hx-x0-3:x+hx-x0+4].any()
    def reserve(site):
        cx,cz=site['centre'];hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        occupied[cz-hz-z0-3:cz+hz-z0+4,cx-hx-x0-3:cx+hx-x0+4]=True
        builtmask[cz-hz-z0-1:cz+hz-z0+2,cx-hx-x0-1:cx+hx-x0+2]=True
    def connect(row,goal=None):
        sx,y,sz=row['approach'];start=(sx,sz);blocked=d['held']|track|builtmask
        if goal is None:
            order=np.argsort((roadpixels[:,1]+x0-sx)**2+(roadpixels[:,0]+z0-sz)**2)[:2400]
            targets=[(int(roadpixels[i,1]+x0),int(roadpixels[i,0]+z0))for i in order[::12]]
        else:targets=[goal]
        path=None
        for goal in targets:
            if math.dist(start,goal)>100:continue
            gy=int(d['road2'][goal[1]-z0,goal[0]-x0])//2
            proposal=route(start,goal,blocked,[x0,z0,x1,z1],14000)
            if proposal and len(proposal)>=abs(gy-y)+2:path=proposal;break
        if path is None:raise ValueError('No street approach for '+row['label'])
        points=[]
        for i,(x,z)in enumerate(path):
            fy=round(y+(gy-y)*i/max(1,len(path)-1));points.append([x,fy,z])
        s.path(points,3);approaches.append(points);row['road']=points[-1]
        return points
    # Native platform corridors are offset from the running rail. Every station
    # has a continuous public-side platform, ticket room and graded approach.
    for index,station in enumerate(plan['station_geometry']):
        if not station['passenger']or station['id']=='gora':continue
        pa,pb=np.asarray(station['platform_a']),np.asarray(station['platform_b']);direction=np.asarray(station['direction']);normal=np.array([-direction[1],direction[0]])
        middle=(pa+pb)/2;y=station['rail_y'];hx,hz=(12,8)if station['id']=='yumoto'else(7,6)
        picked=None
        for sign in(1,-1):
            for distance in(19,25,32,40,50,60):
                for along in(0,-12,12,-24,24):
                    centre=np.rint(middle+normal*sign*distance+direction*along).astype(int);x,z=map(int,centre)
                    toward=middle-centre;face=('east'if toward[0]>0 else'west')if abs(toward[0])>abs(toward[1])else('south'if toward[1]>0 else'north')
                    rot=['south','west','north','east'].index(face);rx,rz=(hx,hz)if rot%2==0 else(hz,hx)
                    if fits(x,z,rx,rz):picked=(x,z,rot,normal*sign);break
                if picked:break
            if picked:break
        if not picked:raise ValueError('No preserved station envelope '+station['id'])
        x,z,rot,n=picked;site=dict(centre=[x,z],floor=y,half=[hx,hz],rotation=rot,floors=2 if station['id']=='yumoto' else 1,variant=index)
        reserve(site);row=make_building(s,site,station['name'],True);row['kind']='station';row['station_id']=station['id'];buildings.append(row)
        platform=[]
        for t in np.linspace(0,1,max(2,round(np.linalg.norm(pb-pa)))+1):
            p=pa+(pb-pa)*t+n*4;px,pz=map(round,p);platform.append([px,y,pz]);s.path([[px,y,pz]],3)
        landing=platform[len(platform)//2]
        sx,sy,sz=row['approach'];points=[[qx,y,qz]for qx,qz in line((sx,sz),(landing[0],landing[2]))]
        s.path(points,3);approaches.append(points);row['platform']=landing
        for point in(platform[3],platform[-4]):
            px,_,pz=point;back=np.rint(np.array([px,pz])+n*2).astype(int)
            e.fill(int(back[0]),y+1,int(back[1]),int(back[0]),y+3,int(back[1]),'minecraft:dark_oak_log[axis=y]')
        for px,_,pz in platform:e.fill(px-1,y+4,pz-1,px+1,y+4,pz+1,'minecraft:dark_oak_planks')
        connect(row)
        s.sign(x-hx-3,y+3,z,[station['name'],'登山电车 / 公交'])
        stations.append(row)
    # Surveyed building clusters constrain the village density. Sizes and uses
    # are adapted for play; they are not asserted to be surveyed business names.
    features=json.load(gzip.open(candidate.parent/'valley-buildings-detail.world.geojson.gz','rt',encoding='utf8'))['features'];centres=[]
    for f in features:
        if f['properties']['source_layer']!='BldA':continue
        g=f['geometry'];polygons=[g['coordinates']]if g['type']=='Polygon'else g['coordinates']if g['type']=='MultiPolygon'else[]
        for polygon in polygons:
            p=np.asarray(polygon[0]).mean(0)
            if x0+12<p[0]<x1-12 and z0+12<p[1]<z1-12:centres.append(p)
    centres=np.asarray(centres);village_stops=[s for s in plan['station_geometry']if s['passenger']and s['id']!='gora'];counts=Counter();used=set()
    labels=['温泉旅馆','沿街食堂','街角喫茶','土产商店','住居','小商铺','民宿','生活杂货']
    for street in manifest['streets']:
        if not street['width']or street['tunnel']or street['bridge']:continue
        geometry=LineString(street['points'])
        samples=[(geometry.interpolate(max(0,d-2)).coords[0],geometry.interpolate(min(geometry.length,d+2)).coords[0])for d in np.arange(5,geometry.length,12)]
        for p,q in samples:
            p,q=np.asarray(p),np.asarray(q);length=np.linalg.norm(q-p)
            if length<1:continue
            normal=np.array([-(q-p)[1],(q-p)[0]])/length
            for distance in(length/2,):
                curb=p+(q-p)*distance/length
                nearest=min(village_stops,key=lambda s:np.linalg.norm(np.array(s['point'])-curb));v=nearest['id']
                radius=220 if v=='yumoto' else 150 if v!='tonosawa' else 110
                if np.linalg.norm(np.array(nearest['point'])-curb)>radius or counts[v]>=(30 if v=='yumoto' else 18):continue
                for sign,setback in[(sign,setback)for sign in(-1,1)for setback in(18,25,32)]:
                    x,z=map(round,curb+normal*sign*(street['width']/2+setback));key=(x//5,z//5)
                    if key in used:continue
                    used.add(key)
                    if len(centres)and np.linalg.norm(centres-[x,z],axis=1).min()>30:continue
                    hx,hz=5,6;toward=curb-[x,z];face=('east'if toward[0]>0 else'west')if abs(toward[0])>abs(toward[1])else('south'if toward[1]>0 else'north');rot=['south','west','north','east'].index(face)
                    rx,rz=(hx,hz)if rot%2==0 else(hz,hx)
                    if not fits(x,z,rx,rz):continue
                    gx,gz=map(round,curb)
                    if not(x0<=gx<=x1 and z0<=gz<=z1)or not d['walk'][gz-z0,gx-x0]:continue
                    floor=int(d['road2'][gz-z0,gx-x0])//2
                    if abs(int(d['target'][z-z0,x-x0])-floor)>12:continue
                    site=dict(centre=[x,z],floor=floor,half=[hx,hz],rotation=rot,floors=2 if counts[v]%3 else 1,variant=len(buildings))
                    # Use the side pavement as the public goal, not the centre
                    # of a two-way national road.
                    goal=(round(curb[0]+normal[0]*sign*(street['width']/2+1)),round(curb[1]+normal[1]*sign*(street['width']/2+1)))
                    if not d['walk'][goal[1]-z0,goal[0]-x0]:continue
                    approach=Frontage(site).point(0,0,hz+3)
                    proposed_blocked=d['held']|track|builtmask
                    proposed_blocked[z-rz-z0-1:z+rz-z0+2,x-rx-x0-1:x+rx-x0+2]=True
                    path=route((approach[0],approach[2]),goal,proposed_blocked,[x0,z0,x1,z1],14000)
                    goal_y=int(d['road2'][goal[1]-z0,goal[0]-x0])//2
                    if not path or len(path)<abs(goal_y-floor)+2 or len(path)>60:continue
                    reserve(site);row=make_building(s,site,labels[counts[v]%len(labels)]);row['kind']='village';row['village']=v
                    connect(row,goal);buildings.append(row);counts[v]+=1
    # Hillside buildings receive stepped retaining foundations; never float
    # a footprint above the real slope after filling only a shallow slab.
    for row in buildings:
        site=row['site'];cx,cz=site['centre'];hx,hz=site['half'];y=site['floor'];rx,rz=(hx,hz)if site['rotation']%2==0 else(hz,hx)
        for x in range(cx-rx-1,cx+rx+2):
            for z in range(cz-rz-1,cz+rz+2):
                ground=int(d['target'][z-z0,x-x0])
                if ground<y-2:e.fill(x,ground,z,x,y-3,z,STONE)
    for row in s.devices:
        tag=row['After'];p=tuple(int(tag[k])for k in('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['overwritten-sign',p])
    # Check all original device positions once against the final composed
    # arrays, including basement objects; identities and contents never move.
    with stopped_world(Path(capture['world'])):
        for p,tag in iter_block_entities(Path(capture['world']),'projectseele:geofront',(x0,-128,z0),(x1,319,z1)):
            if e.state(*p)!=e.state(*p,original=True):errors.append(['original-device-overwrite',p])
    regions=e.save();manifest.update(regions=regions,cells=sum(r['cells']for r in regions),native_receipt=str(a.native/'native_transit_receipt.json'),railway_structure_cells=dict(stats),new_frontages=len(buildings),pending=['public approach checks','funicular earthworks','cold installation and LOD'])
    (candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (candidate/'valley-buildings.json').write_text(json.dumps(dict(stations=stations,buildings=buildings,approaches=approaches,village_counts=dict(counts)),ensure_ascii=False,indent=2),'utf8')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(candidate/'block-entities.dat',gzipped=True)
    report=dict(errors=errors,stations=len(stations),frontages=len(buildings),villages=dict(counts),native_services=receipt['validation'],visual_verified=False,public_routes_pending=True)
    (candidate/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Corridor composition needs repair')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('candidate','native'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
