"""Build surveyed mountain interchanges, with public routes and full interiors.

Station centres come from the cached GSI railway. Official station programmes
inform an adapted block layout; only the measured source arrays are edited.
"""
import argparse,copy,json,shutil
from collections import deque
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station,AIR,STONE,PAVE,GLASS,RAIL
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world


class Builder:
    def __init__(self,s,x,z):self.s=s;self.x=x;self.z=z;self.goals={};self.bounds=None
    def fill(self,x,y,z,X,Y,Z,state):self.s.fill((x+self.x,y,z+self.z,X+self.x,Y,Z+self.z),state)
    def point(self,x,y,z):return(x+self.x,y,z+self.z)
    def sign(self,x,y,z,lines,facing='north'):self.s.sign(*self.point(x,y,z),lines,facing)
    def goal(self,name,x,y,z):self.goals[name]=self.point(x,y,z)
    def room(self,hx,hz,y,wall='minecraft:white_concrete',height=5):
        # Terraced foundations meet measured soil, including raised valley
        # stations; no floor is left floating over the previous DEM surface.
        for x in range(-hx,hx+1):
            for z in range(-hz,hz+1):
                xx,zz=x+self.x,z+self.z;r=self.s.e.region(xx,zz)
                column=r['before'][r['index'][xx//16,zz//16],:,zz%16,xx%16]
                visible=np.asarray([v.split('[')[0]not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')for v in r['names']])
                found=np.flatnonzero(visible[column]);top=int(found[-1])-128 if len(found)else y-2
                if top<y and not getattr(self,'foundation_built',False):self.fill(x,max(-128,top),z,x,y-1,z,STONE)
                self.fill(x,y+1,z,x,max(y+height,top),z,AIR)
        self.fill(-hx,y-2,-hz,hx,y-1,hz,STONE)
        self.fill(-hx,y,-hz,hx,y,hz,PAVE)
        self.fill(-hx,y+1,-hz,hx,y+height,hz,AIR)
        for z in (-hz,hz):self.fill(-hx,y+1,z,hx,y+height-1,z,wall)
        for x in (-hx,hx):self.fill(x,y+1,-hz,x,y+height-1,hz,wall)
        for x in range(-hx+2,hx-2,5):
            for z in (-hz,hz):self.fill(x,y+2,z,x+2,y+height-2,z,GLASS)
        for z in range(-hz+2,hz-2,5):
            for x in (-hx,hx):self.fill(x,y+2,z,x,y+height-2,z+2,GLASS)
        self.fill(-hx-1,y+height,-hz-1,hx+1,y+height,hz+1,'minecraft:light_gray_concrete')
        for x in range(-hx+3,hx,6):
            for z in range(-hz+3,hz,6):self.fill(x,y+height-1,z,x,y+height-1,z,'minecraft:sea_lantern')
        self.foundation_built=True
    def entry(self,x,y,z,X,Z):self.fill(x,y+1,z,X,y+3,Z,AIR)
    def route(self,start,end,width=3):
        n=max(abs(start[0]-end[0]),abs(start[2]-end[2]));points=[tuple(map(int,p))for p in np.rint(np.linspace(start,end,n+1))]
        if any(abs(p[1]-q[1])>1 for p,q in zip(points,points[1:])):raise ValueError('Steep station approach')
        self.s.path(points,width);return points
    def stairs(self,x,z,y0,y1,direction=1):
        # Two blocks per riser, two clear blocks of headroom, with actual stairs.
        points=[]
        for i in range(abs(y1-y0)*2+1):
            y=y0+(1 if y1>y0 else-1)*(i//2);zz=z+direction*i
            self.fill(x-1,min(y0,y)-2,zz,x+1,y-1,zz,STONE)
            self.fill(x-1,y,zz,x+1,y,zz,PAVE)
            self.fill(x-1,y+1,zz,x+1,y+3,zz,AIR)
            points.append(self.point(x,y,zz))
        self.s.paths.append(points);return points
    def counter(self,x,y,z,length,label):
        self.fill(x,y+1,z,x+length-1,y+1,z+1,'minecraft:smooth_quartz')
        self.sign(x+1,y+2,z-1,[label])
    def bench(self,x,y,z,length=3):self.s.bench(*self.point(x,y+1,z),length)


def ubako(s):
    b=Builder(s,-21,823);b.room(13,7,139,'minecraft:light_gray_concrete');b.room(13,7,145,'minecraft:gray_concrete',6)
    b.entry(-3,139,7,3,8);b.counter(-11,139,-3,5,'姥子 · 票务');b.bench(5,139,3)
    # The southwest-to-east ropeway occupies the upper through hall.
    b.entry(-14,145,-2,-12,2);b.entry(12,145,-3,14,1)
    b.fill(-14,145,2,14,145,2,'minecraft:yellow_concrete')
    b.stairs(9,7,139,145,-1)
    b.fill(7,146,-7,11,148,-5,AIR)
    b.sign(-5,142,8,['姥子','UBAKO','索道 / 周边步道'],'south')
    b.route(b.point(0,139,9),(-5,138,842),3)
    b.goal('entrance',0,140,6);b.goal('ticket',0,140,0);b.goal('upper boarding',0,146,0);b.goal('road',16,139,19)
    b.bounds=(-42,135,811,2,154,850)
    return b


def owakudani(s):
    b=Builder(s,272,830);b.room(12,13,179,'minecraft:white_concrete',6);b.room(12,13,185,'minecraft:light_gray_concrete',6)
    b.entry(-3,179,13,3,15);b.counter(-9,179,-8,5,'大涌谷 · 票务');b.counter(4,179,-7,5,'名产 / 黑鸡蛋')
    for x in (-8,4):b.bench(x,179,6,4)
    b.stairs(-8,12,179,185,-1)
    b.entry(-13,185,-6,-11,0);b.entry(11,185,-6,13,0)
    b.fill(-12,185,1,12,185,1,'minecraft:yellow_concrete')
    # South-facing viewing balcony, open from the public lower concourse.
    b.fill(-15,179,14,15,179,21,PAVE)
    b.fill(-15,180,21,15,180,21,'minecraft:glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]')
    b.fill(-2,180,21,2,182,21,AIR)
    b.sign(-5,182,14,['大涌谷','OWAKUDANI','桃源台 ←  → 早云山'],'south')
    b.route(b.point(0,179,22),(280,178,853),3)
    b.goal('entrance',0,180,12);b.goal('concourse',0,180,0);b.goal('upper transfer',0,186,-3);b.goal('terrace',0,180,18);b.goal('road',8,179,23)
    b.bounds=(254,175,813,290,194,857)
    return b


def sounzan(s):
    b=Builder(s,652,767);b.room(18,17,104,'minecraft:light_gray_concrete',6);b.room(18,17,110,'minecraft:white_concrete',6);b.room(18,17,116,'minecraft:white_concrete',6)
    # Cable car enters the lower east side; ropeway arrives from the upper west.
    b.entry(17,104,-9,19,-3);b.entry(-19,116,-8,-17,-2)
    b.fill(0,104,-10,18,104,-10,'minecraft:yellow_concrete')
    b.fill(-18,116,-1,5,116,-1,'minecraft:yellow_concrete')
    b.entry(17,110,7,20,13);b.counter(-13,110,-10,6,'早云山 · 换乘票务')
    b.counter(6,116,6,7,'cu-mo / 土产');b.bench(-10,110,9,6)
    # Separate stair flights avoid carving a single vertical hole through both
    # platforms. Each flight has a horizontal landing at the next concourse.
    b.stairs(-10,12,104,110,-1);b.stairs(-5,0,110,116,1)
    b.fill(-7,117,11,-3,119,14,AIR)
    b.fill(-19,116,18,19,116,27,PAVE);b.entry(-7,116,17,7,18)
    b.fill(-19,117,27,19,117,27,'minecraft:glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]')
    b.sign(19,113,8,['早云山','SOUNZAN','索道 ↑ / 登山缆车 ↓'],'east')
    b.route(b.point(21,110,10),(697,99,778),3)
    b.route((697,99,778),(684,99,773),3)
    b.goal('entrance',17,111,10);b.goal('lower platform',10,105,-6);b.goal('upper boarding',-12,117,-5);b.goal('viewing terrace',0,117,24);b.goal('road',32,100,6)
    b.bounds=(628,98,744,701,125,800)
    return b


def gora(s):
    # The mountain railway runs north/south; the cable-car interchange meets
    # its west end. The town-side concourse and forecourt are on the east.
    b=Builder(s,950,643);b.room(10,13,55,'minecraft:dark_oak_planks',6)
    for x in range(-11,12):
        h=61+max(0,4-abs(x)//3)
        b.fill(x,h,-15,x,h,15,'minecraft:dark_oak_planks')
    b.entry(10,55,-3,12,3);b.entry(-11,55,-5,-9,5)
    b.counter(4,55,-9,4,'强罗 · 乘车服务');b.bench(1,55,7,5)
    # Side and island platforms include accessible end crossings. Rail slots
    # are left unobstructed for native track geometry authored in the next pass.
    b.fill(-25,53,-23,-11,54,25,'minecraft:gravel')
    for x,X in [(-25,-23),(-18,-15),(-12,-11)]:
        b.fill(x,55,-23,X,55,25,PAVE)
        b.fill(x,56,-23,X,60,25,AIR)
        b.fill(x,55,-23,x,55,25,'minecraft:yellow_concrete')
    for z in (-20,20):b.fill(-25,55,z,-9,55,z+3,PAVE)
    for x in (-24,-16):
        for z in (-17,-3,11):b.fill(x,56,z,x,59,z,'minecraft:dark_oak_log[axis=y]')
        b.fill(x-1,60,-20,x+2,60,22,'minecraft:light_gray_concrete')
    # The cable-car waiting bay is the uphill (west) branch of the interchange.
    b.fill(-38,55,-1,-26,55,12,PAVE);b.fill(-38,56,-1,-26,60,12,AIR)
    b.fill(-38,61,-1,-26,61,12,'minecraft:gray_concrete')
    b.fill(-38,56,12,-26,56,12,RAIL)
    b.route(b.point(-16,55,22),b.point(-32,55,9),3)
    b.sign(11,58,-6,['強羅','GORA','登山电车 / 登山缆车'],'east')
    b.route(b.point(12,55,0),(971,51,649),5)
    # Fine-grained station-front retail: four narrow addresses with usable
    # doors and furnished rooms, rather than a large decorative box frontage.
    for i,label in enumerate(['土产店','温泉案内','站前喫茶','旅行书店']):
        shop=Builder(s,976+i*9,620);shop.room(4,6,54,'minecraft:bricks'if i%2 else'minecraft:white_terracotta',5)
        shop.entry(-1,54,6,1,8);shop.counter(-2,54,-3,4,label);shop.bench(-2,54,2)
        for x in range(-5,6):
            h=59+max(0,2-abs(x)//2);shop.fill(x,h,-7,x,h,7,'minecraft:dark_oak_planks')
        shop.sign(-2,57,7,[label],'south');shop.route(shop.point(0,54,6),shop.point(0,54,9),3)
        shop.route(shop.point(0,54,9),(976+i*9,51,638),3)
        b.goals['shop '+str(i)]=shop.point(0,55,0)
    # A continuous street walk joins all storefronts and the bus/taxi forecourt.
    b.route((970,51,639),(1011,51,639),5)
    b.route((971,51,639),(971,51,649),5)
    b.route((971,51,649),(989,51,659),5)
    b.fill(29,51,10,45,51,22,PAVE)
    for x in (30,44):b.fill(x,52,20,x,55,20,'minecraft:gray_concrete')
    b.fill(28,56,17,46,56,23,'minecraft:light_gray_concrete');b.bench(34,51,20,5)
    b.sign(31,54,19,['强罗站 公交','小涌谷 / 箱根汤本'])
    b.goal('entrance',9,56,0);b.goal('rail platform',-16,56,7);b.goal('cable interchange',-32,56,7);b.goal('bus',39,52,15);b.goal('road',21,52,6)
    b.bounds=(908,49,609,1017,69,672)
    return b


def reachable(e,b):
    def stand(p):
        x,y,z=p;air=('minecraft:air','minecraft:cave_air')
        return e.state(x,y,z).split('[')[0]in air and e.state(x,y+1,z).split('[')[0]in air and e.state(x,y-1,z).split('[')[0]not in (*air,'minecraft:water','minecraft:glass_pane','minecraft:iron_bars')
    start=tuple(b.goals['entrance']);seen={start};queue=deque([start]);lo=b.bounds[:3];hi=b.bounds[3:]
    while queue:
        x,y,z=queue.popleft()
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            for dy in (0,1,-1):
                q=x+dx,y+dy,z+dz
                if q in seen or any(q[i]<lo[i]or q[i]>hi[i]for i in range(3)):continue
                if stand(q):seen.add(q);queue.append(q);break
    return[('unreachable',name,p)for name,p in b.goals.items()if tuple(p)not in seen],len(seen)


def author(a):
    a.candidate.mkdir(parents=True,exist_ok=True);(a.candidate/'source').mkdir(exist_ok=True);(a.candidate/'delta').mkdir(exist_ok=True)
    (a.candidate/'functional-check.json').write_text(json.dumps({'errors':['Authoring incomplete']}),'utf8')
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    # Copy measured compressed arrays only. The candidate remains independent
    # of the live region files and can be revised without touching the save.
    for name in capture['source_files']:
        target=a.candidate/name
        if not target.exists():shutil.copy2(a.source/name,target)
        (a.candidate/'delta'/Path(name).name).unlink(missing_ok=True)
    e=Editor(a.candidate);s=Station(e);buildings=[fn(s)for fn in (ubako,owakudani,sounzan,gora)];errors=[];reports=[]
    with stopped_world(world):
        for b in buildings:
            # Existing BEs are retained even when they sit in an unchanged
            # corner of the measured area; only actual block changes matter.
            for p,tag in iter_block_entities(world,'projectseele:geofront',b.bounds[:3],b.bounds[3:]):
                if e.state(*p)!=e.state(*p,original=True):errors.append(['original-device-overwrite',p])
            for r in capture['actors']:
                if all(b.bounds[i]<=r['pos'][i]<=b.bounds[i+3]for i in range(3)):errors.append(['actor-in-envelope',r['id'],r['pos']])
    for b in buildings:
        issues,count=reachable(e,b);errors.extend(issues);reports.append(dict(centre=[b.x,b.z],bounds=b.bounds,goals=b.goals,reachable=count))
    # Original inhabited parcels are volumes, not merely their chest blocks.
    neighbours=json.loads((a.source.parent/'main-district-candidate/neighbourhood.json').read_text('utf8'))
    for row in neighbours:
        site=row['site'];x,z=site['centre'];hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        if not any(b.bounds[0]<=x+hx+2 and x-hx-2<=b.bounds[3]and b.bounds[2]<=z+hz+2 and z-hz-2<=b.bounds[5]for b in buildings):continue
        for xx in range(x-hx-2,x+hx+3):
            for zz in range(z-hz-2,z+hz+3):
                for yy in range(site['floor'],min(319,site['floor']+site['floors']*5+9)+1):
                    if e.state(xx,yy,zz)!=e.state(xx,yy,zz,original=True):
                        errors.append(['original-parcel-overwrite',row['id'],[xx,yy,zz]]);break
    for row in s.devices:
        tag=row['After'];p=tuple(int(tag[k])for k in ('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['overwritten-sign',p])
    regions=e.save();nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(a.candidate/'block-entities.dat',gzipped=True)
    report=dict(errors=errors,stations=reports,new_signs=len(s.devices),existing_devices_changed=0,actors_changed=0,visual_verified=False)
    (a.candidate/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    manifest=dict(world=str(world),bounds_xz=capture['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[],
                  source='Cached GSI station centres and official Hakone Navi station floor programmes; dimensions adapted for walking',
                  official_plans=['https://www.hakonenavi.jp/transportation/station/'+n+'/'for n in ('ubako','ohwakudani','sounzan','gora')])
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(errors=errors,stations=len(buildings),cells=manifest['cells']),ensure_ascii=False),flush=True)
    if errors:raise ValueError('Resolve station public routes before installation')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','candidate'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
