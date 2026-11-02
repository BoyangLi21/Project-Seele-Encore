"""Compose current-source southern ports, complete public plots and shore woods.

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
from hakone_earthworks import road_blocks

SHELTER_ROOF=106


def author(a):
    folder=a.candidate;manifest=json.loads((folder/'manifest.json').read_text('utf8'))
    if 'shore_ports' in manifest:raise ValueError('Use a fresh prepared candidate')
    with np.load(folder/'valley-surface.npz')as f:d={k:f[k]for k in f.files}
    x0,z0,x1,z1=map(int,d['bounds']);shape=d['target'].shape
    layout_only=getattr(a,'layout_only',False)
    blueprint_path=folder/'regraded-layout.json'
    blueprint=json.loads(blueprint_path.read_text('utf8'))if not layout_only and blueprint_path.exists()else None
    paving_index=0
    public_sites=manifest['current_public_sites']
    class LayoutEditor:
        def fill(self,*args):pass
        def put(self,*args):pass
        def state(self,*args,**kwargs):return STONE
    e=LayoutEditor() if layout_only else Editor(folder)
    s=Station(e);buildings=[];ports=[];paths=[];paving_specs=[];errors=[];supports=[];amenities=[];light_requests=[]
    forecourt_zones=[[520,1988,566,2044],[384,2334,433,2403]]
    occupied=d['held'].copy()|d['walk']|d['wet'];built=np.zeros(shape,bool);body=np.zeros(shape,bool)
    bus_obstacles=np.zeros(shape,bool)
    roadpixels=np.argwhere(d['walk']&~d['road'])
    def reserve(site):
        x,z=site['centre'];hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        occupied[z-hz-z0-4:z+hz-z0+5,x-hx-x0-4:x+hx-x0+5]=True
        built[z-hz-z0-2:z+hz-z0+3,x-hx-x0-2:x+hx-x0+3]=True
        body[z-hz-z0:z+hz-z0+1,x-hx-x0:x+hx-x0+1]=True
    def pave(points,width=3,material=PAVE,role='approach'):
        nonlocal paving_index
        if blueprint:
            spec=blueprint['paving_specs'][paving_index];paving_index+=1
            if (width,material,role)!=(spec['width'],spec['material'],spec['role']):
                raise ValueError('Final paving programme differs from the graded layout')
            points=[[x,int((d['road2'][z-z0,x-x0]+1)//2),z]for x,_,z in spec['points']]
            radius=width//2
            columns={(x+dx,z+dz)for x,_,z in points for dx in range(-radius,radius+1)for dz in range(-radius,radius+1)}
            for x,z in sorted(columns):
                y,slab=map(int,road_blocks(d['road2'][z-z0,x-x0]))
                base='minecraft:black_concrete'if d['road'][z-z0,x-x0]else material
                surface=base
                if slab:
                    surface={'minecraft:black_concrete':'projectseele:road_asphalt_slab',PAVE:'minecraft:smooth_stone_slab',
                        'minecraft:spruce_planks':'minecraft:spruce_slab'}[base]+'[type=bottom,waterlogged=false]'
                e.fill(x,y-2,z,x,y-1,z,STONE);e.put(x,y,z,surface)
                for Y in range(y+1,y+4):
                    if not e.state(x,Y,z).split('[')[0].endswith('_wall_sign'):e.put(x,Y,z,AIR)
            if role=='pier':
                for x,y,z in points[::8]+points[-1:]:
                    bed=int(d['target'][z-z0,x-x0])
                    if bed<y-2:
                        e.fill(x,bed+1,z,x,y-3,z,STONE);supports.append([x,bed,z,y-2])
        else:s.path(points,width,material)
        paths.append(points)
        paving_specs.append(dict(points=points,width=width,material=material,role=role))
        for x,y,z in points:
            radius=width//2
            occupied[z-z0-radius:z-z0+radius+1,x-x0-radius:x-x0+radius+1]=True
        return points
    def connect(row,goal=None,width=3):
        material='minecraft:black_concrete'if width>=5 else PAVE
        role='bus-approach'if width>=5 else'approach'
        if blueprint:
            row['road']=pave([],width,material,role)[-1];return
        sx,y,sz=row['approach'];radius=width//2
        mask=d['held']|body|(bus_obstacles if width>=5 else False)
        blocked=np.asarray(Image.fromarray(mask).filter(ImageFilter.MaxFilter(radius*2+1)),bool)
        # The port deck may project over water; its explicit gangway reaches
        # the public plaza before the terrain-constrained street search.
        if goal is None:
            pixels=np.argwhere(d['road'])if width>=5 else roadpixels
            if width>=5:
                keep=np.ones(len(pixels),bool)
                for left,north,right,south in forecourt_zones:
                    keep&=~((pixels[:,1]+x0>=left)&(pixels[:,1]+x0<=right)&(pixels[:,0]+z0>=north)&(pixels[:,0]+z0<=south))
                pixels=pixels[keep]
            order=np.argsort((pixels[:,1]+x0-sx)**2+(pixels[:,0]+z0-sz)**2)[:1800]
            goals=[(int(pixels[i,1]+x0),int(pixels[i,0]+z0))for i in order[::10]]
        else:goals=[goal]
        found=None
        for gx,gz in goals:
            if math.dist((sx,sz),(gx,gz))>100:continue
            if blocked[gz-z0,gx-x0]:continue
            gy=int((d['road2'][gz-z0,gx-x0]+1)//2)
            proposal=route((sx,sz),(gx,gz),blocked,[x0,z0,x1,z1],15000)
            if proposal and len(proposal)>=abs(gy-y)+2:found=proposal;break
        if found is None:raise ValueError('No public approach '+row['label'])
        points=[[x,round(y+(gy-y)*i/max(1,len(found)-1)),z]for i,(x,z)in enumerate(found)]
        pave(points,width,material,role);row['road']=points[-1]
    def foundation(row):
        site=row['site'];x,z=site['centre'];hx,hz=site['half'];y=site['floor']
        if site['rotation']%2:hx,hz=hz,hx
        for px in range(x-hx-1,x+hx+2):
            for pz in range(z-hz-1,z+hz+2):
                ground=int(d['target'][pz-z0,px-x0])
                if ground<y-2:
                    if d['wet'][pz-z0,px-x0]and((px-(x-hx-1))%6 or(pz-(z-hz-1))%6):continue
                    e.fill(px,ground+1,pz,px,y-3,pz,STONE);supports.append([px,ground,pz,y-2])
    # Passenger terminals sit at the surveyed piers. Their landward entrances
    # lead into the official forecourt programme rather than facing a blank wall.
    for port_index,port in enumerate([dict(id='motohakone',name='元箱根港',centre=[531,2029],rotation=3,
                      quay=[500,100,2029],plaza=[565,100,2029],cafe=[569,1999]),
                 dict(id='hakonemachi',name='箱根町港',centre=[402,2342],rotation=0,
                      quay=[384,100,2310],plaza=[407,100,2366],cafe=[385,2370])]):
        x,z=port['centre'];site=dict(centre=[x,z],floor=100,half=[12,7],rotation=port['rotation'],floors=1,variant=2)
        hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        if d['protected'][z-hz-z0-4:z+hz-z0+5,x-hx-x0-4:x+hx-x0+5].any():raise ValueError('Retained object at '+port['name'])
        reserve(site);row=make_building(s,site,port['name'],True);row.update(kind='station',station_id=port['id'])
        buildings.append(row);foundation(row);c=Frontage(site)
        # A second, open waterside doorway joins ticket room and boarding pier.
        local_hz=site['half'][1]
        for op in [( -2,1,-local_hz,2,3,-local_hz,AIR)]:
            tmp=Frontage(site);tmp.fill(*op)
            for box in tmp.operations:s.fill(box[:6],box[6])
        row['waterside_door']=c.point(0,1,-local_hz)
        rear=c.point(0,0,-local_hz-2);quay=port['quay']
        points=[[px,100,pz]for px,pz in line((rear[0],rear[2]),(quay[0],quay[2]))]
        pave(points,5,'minecraft:spruce_planks','pier');row['platform']=quay
        if port['id']=='motohakone':
            pave([[500,100,zz]for zz in range(2007,2052)],5,'minecraft:spruce_planks','pier')
        else:
            pave([[px,100,pz]for px,pz in line((370,2324),(398,2296))],5,'minecraft:spruce_planks','pier')
        sx,sy,sz=row['approach'];px,py,pz=port['plaza']
        pave([[qx,100,qz]for qx,qz in line((sx,sz),(px,pz))],5,role='forecourt')
        row['approach']=[px,100,pz];connect(row)
        # Layby bays, sheltered waiting and real signs occupy the landward
        # forecourt. A continuous pedestrian aisle remains behind the kerb.
        if port['id']=='motohakone':
            bays=[(545,2000),(545,2017),(545,2034)]
            for bx,bz in bays:
                pave([[bx,100,qz]for qz in range(bz-6,bz+7)],7,'minecraft:black_concrete','bay')
                pave([[bx-5,100,qz]for qz in range(bz-7,bz+8)],3,role='aisle')
                s.fill((bx-7,SHELTER_ROOF,bz-5,bx-4,SHELTER_ROOF,bz+5),'minecraft:dark_oak_planks')
                bus_obstacles[bz-z0-5:bz-z0+6,bx-x0-7:bx-x0-3]=True
                s.sign(bx-5,SHELTER_ROOF,bz-6,['元箱根港','湯本 / 小田原','箱根町 / 桃源台'],'north')
        else:
            bays=[(422,2358),(422,2375),(422,2392)]
            for bx,bz in bays:
                pave([[bx,100,qz]for qz in range(bz-6,bz+7)],7,'minecraft:black_concrete','bay')
                pave([[bx-5,100,qz]for qz in range(bz-7,bz+8)],3,role='aisle')
                s.fill((bx-7,SHELTER_ROOF,bz-5,bx-4,SHELTER_ROOF,bz+5),'minecraft:dark_oak_planks')
                bus_obstacles[bz-z0-5:bz-z0+6,bx-x0-7:bx-x0-3]=True
                s.sign(bx-5,SHELTER_ROOF,bz-6,['箱根町港','元箱根 / 湯本','箱根新道'],'north')
        for bx,bz in bays:
            for pz in (bz-5,bz+5):
                px=bx-7;bed=int(d['target'][pz-z0,px-x0])
                if bed>=SHELTER_ROOF:raise ValueError('Shelter pillar exceeds its roof')
                e.fill(px,bed+1,pz,px,SHELTER_ROOF-1,pz,STONE)
                body[pz-z0,px-x0]=True;occupied[pz-z0,px-x0]=True
                amenities.append(dict(kind='shelter-pillar',column=[px,pz],bed=bed,top=SHELTER_ROOF))
        for bx,bz in bays:
            # Each bay has a level/graded connection, including both ends,
            # instead of stopping a strip of asphalt inside a terrain bank.
            for end in(-6,6):
                temporary=dict(label=port['name']+'公交接入',approach=[bx,100,bz+end]);connect(temporary,width=7)
        csite=dict(public_sites[2+port_index],floors=2,variant=0)
        port['cafe']=csite['centre'];port['bays']=[list(b)for b in bays]
        reserve(csite);cafe=make_building(s,csite,'湖畔茶屋 / 餐厅');cafe['kind']='village';foundation(cafe);connect(cafe);buildings.append(cafe)
        light_requests.extend([(port['plaza'][0]-3,port['plaza'][2]-7),(port['plaza'][0]+3,port['plaza'][2]+7)])
        port['building']=row;ports.append(port)
    # The measured road network and surveyed building clusters determine the
    # populated strips. Narrow, irregular plots have mixed shop/inn/residential
    # rooms, multiple roof forms and ground-retaining foundations.
    fs=json.load(gzip.open(a.gis/'town-detail.world.geojson.gz','rt',encoding='utf8'))['features'];centres=[]
    for f in fs:
        g=f['geometry']
        if f['properties']['source_layer']=='BldA'and g['type']=='Polygon':centres.append(np.asarray(g['coordinates'][0]).mean(0))
    centres=np.asarray(centres);counts=Counter();used=set()
    towns=[('motohakone',[555,1950],230,38),('hakonemachi',[413,2370],160,26)]
    labels=['湖畔商店','温泉旅馆','住居','街角食堂','土产 / 喫茶','民宿','生活杂货']
    if blueprint:
        for planned in blueprint['buildings']:
            if 'village'not in planned:continue
            site=copy.deepcopy(planned['site']);reserve(site)
            row=make_building(s,site,planned['label']);row.update(kind='village',village=planned['village'])
            foundation(row);connect(row);buildings.append(row);counts[row['village']]+=1
        for link in blueprint.get('network_links',[]):
            pave(link['points'],link['width'],link['material'],link['role'])
        if paving_index!=len(blueprint['paving_specs']):raise ValueError('Not all graded paths were composed')
    for street in ([] if blueprint else manifest['streets']):
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
    if layout_only:
        (folder/'valley-buildings.json').write_text(json.dumps(dict(buildings=buildings,approaches=paths,
            paving_specs=paving_specs,ports=ports,village_counts=dict(counts),amenities=amenities,forecourt_zones=forecourt_zones),ensure_ascii=False,indent=2),'utf8')
        print('Prepared layout:',len(buildings),'buildings,',len(paving_specs),'public paths',flush=True)
        return
    for requested_x,requested_z in light_requests:
        options=sorted(((dx,dz)for dx in range(-18,19)for dz in range(-18,19)),key=lambda p:p[0]*p[0]+p[1]*p[1])
        for dx,dz in options:
            px,pz=requested_x+dx,requested_z+dz;iz,ix=pz-z0,px-x0
            if occupied[iz-1:iz+2,ix-1:ix+2].any():continue
            y=int(d['target'][iz,ix])
            if np.ptp(d['target'][iz-1:iz+2,ix-1:ix+2])>2:continue
            s.light(px,y+1,pz);occupied[iz-1:iz+2,ix-1:ix+2]=True
            amenities.append(dict(kind='lamp',column=[px,pz],bed=y,top=y+5));break
        else:raise ValueError('No unobstructed lamp site around the public forecourt')
    # Author planting off the carriageways, buildings and shore-water mask.
    # This is an ecological/visual adaptation, not surveyed individual trees.
    avoid=np.asarray(Image.fromarray(occupied|built|d['river']).filter(ImageFilter.MaxFilter(13)),bool)
    rng=np.random.default_rng(20261030);trees=0
    for z in ([] if manifest.get('defer_planting',False) else range(z0+10,z1-10,13)):
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
    (folder/'valley-buildings.json').write_text(json.dumps(dict(buildings=buildings,approaches=paths,paving_specs=paving_specs,ports=ports,village_counts=dict(counts),supports=supports,amenities=amenities,forecourt_zones=forecourt_zones),ensure_ascii=False,indent=2),'utf8')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(folder/'block-entities.dat',gzipped=True)
    report=dict(errors=errors,public_routes_pending=True,frontages=len(buildings),villages=dict(counts),trees=trees,visual_verified=False)
    (folder/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Lakeshore composition needs repair')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('gis','candidate'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--layout-only',action='store_true')
    author(p.parse_args())
