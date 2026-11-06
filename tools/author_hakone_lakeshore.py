"""Compose the two southern Lake Ashi ports, measured town streets and shore woods.

GSI fixes terrain, shoreline, roads and settlement clusters. Official port plans
fix the public programme; rooms and boarding structures use playable dimensions.
This edits a fresh candidate only. Existing lake water and world identities stay.
"""
import argparse,copy,gzip,json,math
from pathlib import Path
from collections import Counter
import nbtlib
import numpy as np
from PIL import Image,ImageFilter
from shapely.geometry import LineString,Point
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station,AIR,PAVE,STONE,GLASS
from author_hakone_valley_corridor import make_building
from author_hakone_district_blocks import Frontage
from prepare_hakone_main_districts import route,line
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world


def author(a):
    folder=a.candidate;manifest=json.loads((folder/'manifest.json').read_text('utf8'))
    if 'shore_ports' in manifest:raise ValueError('Use a fresh prepared candidate')
    with np.load(folder/'valley-surface.npz')as f:d={k:f[k]for k in f.files}
    x0,z0,x1,z1=map(int,d['bounds']);shape=d['target'].shape
    e=Editor(folder);s=Station(e);buildings=[];ports=[];paths=[];errors=[]
    occupied=d['held'].copy()|d['walk']|d['wet'];built=np.zeros(shape,bool)
    roadpixels=np.argwhere(d['walk']&~d['road'])
    def reserve(site):
        x,z=site['centre'];hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        occupied[z-hz-z0-4:z+hz-z0+5,x-hx-x0-4:x+hx-x0+5]=True
        built[z-hz-z0-2:z+hz-z0+3,x-hx-x0-2:x+hx-x0+3]=True
    def pave(points,width=3,material=PAVE):
        s.path(points,width,material);paths.append(points)
        for x,y,z in points:
            radius=width//2
            occupied[z-z0-radius:z-z0+radius+1,x-x0-radius:x-x0+radius+1]=True
    def connect(row,goal=None):
        sx,y,sz=row['approach'];blocked=d['held']|built
        # The port deck may project over water; its explicit gangway reaches
        # the public plaza before the terrain-constrained street search.
        if goal is None:
            order=np.argsort((roadpixels[:,1]+x0-sx)**2+(roadpixels[:,0]+z0-sz)**2)[:1800]
            goals=[(int(roadpixels[i,1]+x0),int(roadpixels[i,0]+z0))for i in order[::10]]
        else:goals=[goal]
        found=None
        for gx,gz in goals:
            if math.dist((sx,sz),(gx,gz))>100:continue
            gy=int((d['road2'][gz-z0,gx-x0]+1)//2)
            proposal=route((sx,sz),(gx,gz),blocked,[x0,z0,x1,z1],15000)
            if proposal and len(proposal)>=abs(gy-y)+2:found=proposal;break
        if found is None:raise ValueError('No public approach '+row['label'])
        points=[[x,round(y+(gy-y)*i/max(1,len(found)-1)),z]for i,(x,z)in enumerate(found)]
        pave(points);row['road']=points[-1]
    def foundation(row):
        site=row['site'];x,z=site['centre'];hx,hz=site['half'];y=site['floor']
        if site['rotation']%2:hx,hz=hz,hx
        for px in range(x-hx-1,x+hx+2):
            for pz in range(z-hz-1,z+hz+2):
                ground=int(d['target'][pz-z0,px-x0])
                if ground<y-2:e.fill(px,ground,pz,px,y-3,pz,STONE)
    # Passenger terminals sit at the surveyed piers. Their landward entrances
    # lead into the official forecourt programme rather than facing a blank wall.
    for port in [dict(id='motohakone',name='元箱根港',centre=[531,2029],rotation=3,
                      quay=[500,100,2029],plaza=[565,100,2029],cafe=[569,1999]),
                 dict(id='hakonemachi',name='箱根町港',centre=[402,2342],rotation=0,
                      quay=[384,100,2310],plaza=[407,100,2366],cafe=[385,2370])]:
        x,z=port['centre'];site=dict(centre=[x,z],floor=100,half=[12,7],rotation=port['rotation'],floors=1,variant=2)
        hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        if d['protected'][z-hz-z0-4:z+hz-z0+5,x-hx-x0-4:x+hx-x0+5].any():raise ValueError('Retained object at '+port['name'])
        reserve(site);row=make_building(s,site,port['name'],True);row.update(kind='station',station_id=port['id'])
        buildings.append(row);foundation(row);c=Frontage(site)
        # A second, open waterside doorway joins ticket room and boarding pier.
        for op in [( -2,1,-hz,2,3,-hz,AIR)]:
            tmp=Frontage(site);tmp.fill(*op)
            for box in tmp.operations:s.fill(box[:6],box[6])
        rear=c.point(0,0,-hz-2);quay=port['quay']
        points=[[px,100,pz]for px,pz in line((rear[0],rear[2]),(quay[0],quay[2]))]
        pave(points,5,'minecraft:spruce_planks');row['platform']=quay
        if port['id']=='motohakone':
            pave([[500,100,zz]for zz in range(2007,2052)],5,'minecraft:spruce_planks')
        else:
            pave([[px,100,pz]for px,pz in line((370,2324),(398,2296))],5,'minecraft:spruce_planks')
        sx,sy,sz=row['approach'];px,py,pz=port['plaza']
        pave([[qx,100,qz]for qx,qz in line((sx,sz),(px,pz))],5)
        row['approach']=[px,100,pz];connect(row)
        # Layby bays, sheltered waiting and real signs occupy the landward
        # forecourt. A continuous pedestrian aisle remains behind the kerb.
        if port['id']=='motohakone':
            bays=[(561,2014),(561,2031),(561,2048)]
            for bx,bz in bays:
                pave([[bx,100,qz]for qz in range(bz-6,bz+7)],7,'minecraft:black_concrete')
                pave([[bx-5,100,qz]for qz in range(bz-7,bz+8)],3)
                s.fill((bx-6,104,bz-5,bx-4,104,bz+5),'minecraft:dark_oak_planks')
                s.bench(bx-5,101,bz,1);s.sign(bx-5,103,bz-4,['元箱根港','湯本 / 小田原','箱根町 / 桃源台'],'east')
            # Street-facing torii by the national road, not a gate blocking it.
            for bx in (545,551):s.fill((bx,101,2007,bx,107,2007),'minecraft:red_concrete')
            s.fill((543,108,2007,553,108,2007),'minecraft:black_concrete');s.fill((544,106,2007,552,106,2007),'minecraft:red_concrete')
        else:
            bays=[(422,2358),(422,2375),(422,2392)]
            for bx,bz in bays:
                pave([[bx,100,qz]for qz in range(bz-6,bz+7)],7,'minecraft:black_concrete')
                pave([[bx-5,100,qz]for qz in range(bz-7,bz+8)],3)
                s.fill((bx-6,104,bz-5,bx-4,104,bz+5),'minecraft:dark_oak_planks')
                s.sign(bx-5,103,bz-4,['箱根町港','元箱根 / 湯本','箱根新道'],'east')
        for bx,bz in bays:
            # Each bay has a level/graded connection, including both ends,
            # instead of stopping a strip of asphalt inside a terrain bank.
            for end in(-6,6):
                temporary=dict(label=port['name']+'公交接入',approach=[bx,100,bz+end]);connect(temporary)
        cx,cz=port['cafe'];csite=dict(centre=[cx,cz],floor=101,half=[7,8],rotation=port['rotation'],floors=2,variant=0)
        reserve(csite);cafe=make_building(s,csite,'湖畔茶屋 / 餐厅');cafe['kind']='village';foundation(cafe);connect(cafe);buildings.append(cafe)
        for xx,zz in[(px-3,pz-7),(px+3,pz+7)]:s.light(xx,101,zz)
        port['building']=row;ports.append(port)
    # The measured road network and surveyed building clusters determine the
    # populated strips. Narrow, irregular plots have mixed shop/inn/residential
    # rooms, multiple roof forms and ground-retaining foundations.
    fs=json.load(gzip.open(a.gis/'town-detail.world.geojson.gz','rt',encoding='utf8'))['features'];centres=[]
    for f in fs:
        g=f['geometry']
        if f['properties']['source_layer']=='BldA'and g['type']=='Polygon':centres.append(np.asarray(g['coordinates'][0]).mean(0))
    centres=np.asarray(centres);counts=Counter();used=set()
    towns=[('motohakone',[555,1950],230,38),('hakonemachi',[413,2370],160,26),('togendai',[-285,1000],220,16)]
    labels=['湖畔商店','温泉旅馆','住居','街角食堂','土产 / 喫茶','民宿','生活杂货']
    for street in manifest['streets']:
        if not street['width']or street['tunnel']or street['bridge']:continue
        geometry=LineString(street['points'])
        for distance in np.arange(5,geometry.length,12):
            p=np.asarray(geometry.interpolate(max(0,distance-2)).coords[0]);q=np.asarray(geometry.interpolate(min(geometry.length,distance+2)).coords[0]);length=np.linalg.norm(q-p)
            if length<1:continue
            curb=(p+q)/2;normal=np.array([-(q-p)[1],(q-p)[0]])/length
            town=min(towns,key=lambda t:np.linalg.norm(np.array(t[1])-curb));key,centre,radius,limit=town
            if math.dist(centre,curb)>radius or counts[key]>=limit:continue
            for sign,setback in [(sign,setback)for sign in(-1,1)for setback in(17,24,31)]:
                x,z=map(round,curb+normal*sign*(street['width']/2+setback));cell=x//5,z//5
                if cell in used:continue
                used.add(cell)
                if not(x0+20<x<x1-20 and z0+20<z<z1-20)or np.linalg.norm(centres-[x,z],axis=1).min()>30:continue
                toward=curb-[x,z];face=('east'if toward[0]>0 else'west')if abs(toward[0])>abs(toward[1])else('south'if toward[1]>0 else'north');rot=['south','west','north','east'].index(face)
                hx,hz=5,6;rx,rz=(hx,hz)if rot%2==0 else(hz,hx)
                if occupied[z-rz-z0-4:z+rz-z0+5,x-rx-x0-4:x+rx-x0+5].any():continue
                gx,gz=map(round,curb+normal*sign*(street['width']/2+1))
                if not d['walk'][gz-z0,gx-x0]:continue
                y=int((d['road2'][gz-z0,gx-x0]+1)//2)
                if abs(int(d['target'][z-z0,x-x0])-y)>12:continue
                site=dict(centre=[x,z],floor=y,half=[hx,hz],rotation=rot,floors=1 if counts[key]%4==0 else 2,variant=len(buildings))
                approach=Frontage(site).point(0,0,hz+3);blocked=d['held']|built
                blocked[z-rz-z0-2:z+rz-z0+3,x-rx-x0-2:x+rx-x0+3]=True
                trial=route((approach[0],approach[2]),(gx,gz),blocked,[x0,z0,x1,z1],14000)
                if not trial or len(trial)>60:continue
                reserve(site);row=make_building(s,site,labels[counts[key]%len(labels)]);row.update(kind='village',village=key)
                foundation(row);connect(row,(gx,gz));buildings.append(row);counts[key]+=1
    # Author planting off the carriageways, buildings and shore-water mask.
    # This is an ecological/visual adaptation, not surveyed individual trees.
    avoid=np.asarray(Image.fromarray(occupied|built|d['river']).filter(ImageFilter.MaxFilter(13)),bool)
    rng=np.random.default_rng(20261030);trees=0
    for z in range(z0+10,z1-10,13):
        for x in range(x0+10,x1-10,13):
            px=x+int(rng.integers(-4,5));pz=z+int(rng.integers(-4,5));iz,ix=pz-z0,px-x0;y=int(d['target'][iz,ix])
            if avoid[iz,ix]or y<100 or y>280 or np.ptp(d['target'][iz-2:iz+3,ix-2:ix+3])>7:continue
            if e.state(px,y,pz).split('[')[0]not in('minecraft:grass_block','minecraft:dirt'):continue
            if any(e.state(px,yy,pz)!=AIR for yy in range(y+1,y+10)):continue
            conifer=bool(rng.random()<.55);height=int(rng.integers(7,11)if conifer else rng.integers(5,8));species='spruce'if conifer else'oak'
            for dy in range(3,height+1):
                radius=max(1,min(3,(height-dy)//2+1))if conifer else(2 if dy==height else 3)
                for dx in range(-radius,radius+1):
                    for dz in range(-radius,radius+1):
                        if abs(dx)+abs(dz)>radius+1:continue
                        if e.state(px+dx,y+dy,pz+dz)==AIR:e.put(px+dx,y+dy,pz+dz,f'minecraft:{species}_leaves[distance=1,persistent=true,waterlogged=false]')
            e.fill(px,y+1,pz,px,y+height-1,pz,f'minecraft:{species}_log[axis=y]');trees+=1
    # Final original device preservation is checked once for this composed
    # candidate; no checks or waits are added to the game simulation.
    with stopped_world(Path(manifest['world'])):
        for p,tag in iter_block_entities(Path(manifest['world']),'projectseele:geofront',(x0,-128,z0),(x1,319,z1)):
            if e.state(*p)!=e.state(*p,original=True):errors.append(['original-device',p])
    for row in s.devices:
        tag=row['After'];p=tuple(int(tag[k])for k in('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['sign',p])
    regions=e.save();manifest.update(regions=regions,cells=sum(r['cells']for r in regions),shore_ports=ports,new_frontages=len(buildings),planted_trees=trees,
        source_programmes=['https://www.hakonenavi.jp/transportation/station/motohakone/','https://www.hakonenavi.jp/transportation/station/hakonemachiko/'],pending=['public approach check','native lake service','cold installation and distant terrain'])
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (folder/'valley-buildings.json').write_text(json.dumps(dict(buildings=buildings,approaches=paths,ports=ports,village_counts=dict(counts)),ensure_ascii=False,indent=2),'utf8')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(folder/'block-entities.dat',gzipped=True)
    report=dict(errors=errors,public_routes_pending=True,frontages=len(buildings),villages=dict(counts),trees=trees,visual_verified=False)
    (folder/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Lakeshore composition needs repair')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('gis','candidate'):p.add_argument('--'+n,type=Path,required=True)
    author(p.parse_args())
