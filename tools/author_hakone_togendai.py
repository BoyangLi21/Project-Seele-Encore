"""Compose the real Togendai interchange in a measured, reversible candidate.

The surveyed station location and official vertical programme guide a playable
adaptation. Existing shops, actors and inventory are outside the construction
envelope. Source arrays are immutable; the playable save is installed separately.
"""
import argparse,json,shutil,copy
from collections import deque
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world

AIR='minecraft:air'
STONE='minecraft:stone_bricks'
PAVE='minecraft:smooth_stone'
GLASS='minecraft:light_gray_stained_glass'
RAIL='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'


class Station:
    def __init__(self,editor):self.e=editor;self.devices=[];self.goals={};self.paths=[]
    def fill(self,box,state):self.e.fill(*box,state)
    def sign(self,x,y,z,lines,facing='north'):
        dx,dz={'north':(0,1),'south':(0,-1),'west':(1,0),'east':(-1,0)}[facing]
        bx,bz=x+dx,z+dz
        by=y
        while by>-127 and self.e.state(bx,by,bz).split('[')[0]in ('minecraft:air','minecraft:cave_air','minecraft:water'):by-=1
        if by<y:self.fill((bx,by+1,bz,bx,y,bz),'minecraft:gray_concrete')
        self.e.put(x,y,z,f'minecraft:oak_wall_sign[facing={facing},waterlogged=false]')
        messages=nbtlib.List[nbtlib.String]([json.dumps({'text':s},ensure_ascii=False)for s in (lines+['']*4)[:4]])
        face=nbtlib.Compound({'messages':messages,'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),
                            'front_text':face,'back_text':copy.deepcopy(face),'is_waxed':nbtlib.Byte(1)})
        self.devices.append(nbtlib.Compound({'After':tag}))
    def path(self,points,width=3,material=PAVE):
        self.paths.append(points)
        for x,y,z in points:
            d=width//2
            self.fill((x-d,y-2,z-d,x+d,y-1,z+d),STONE)
            self.fill((x-d,y,z-d,x+d,y,z+d),material)
            self.fill((x-d,y+1,z-d,x+d,y+3,z+d),AIR)
    def bench(self,x,y,z,n=3):
        self.fill((x,y,z,x+n-1,y,z),'minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    def light(self,x,y,z):
        self.fill((x,y,z,x,y+3,z),'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
        self.e.put(x,y+4,z,'minecraft:lantern[hanging=false,waterlogged=false]')


def author(a):
    a.candidate.mkdir(parents=True,exist_ok=True)
    (a.candidate/'source').mkdir(exist_ok=True);(a.candidate/'delta').mkdir(exist_ok=True)
    (a.candidate/'functional-check.json').write_text(json.dumps({'errors':['Authoring incomplete']}),'utf8')
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    for name in ('r.-1.1.npz','r.-1.2.npz'):
        if not(a.candidate/'source'/name).exists():shutil.copy2(a.source/'source'/name,a.candidate/'source'/name)
        (a.candidate/'delta'/name).unlink(missing_ok=True)
    e=Editor(a.candidate);s=Station(e)
    # None of the measured station envelope contains original devices or actors.
    envelope=(-332,95,977,-244,124,1083)
    with stopped_world(world):devices=dict(iter_block_entities(world,'projectseele:geofront',envelope[:3],envelope[3:]))
    if devices:raise ValueError('Original device within station envelope: '+str(list(devices)))
    actors=[r for r in capture['actors']if all(envelope[i]<=r['pos'][i]<=envelope[i+3]for i in range(3))]
    if actors:raise ValueError('Actor within station envelope')
    # Shore edge stays at the surveyed water elevation. The station is a pier
    # structure with piles, not a rectangular embankment filling Lake Ashi.
    s.fill((-305,100,997,-267,122,1034),AIR)
    for x in (-303,-286,-269):
        for z in (999,1015,1031):s.fill((x,91,z,x+1,99,z+1),STONE)
    levels=[100,104,109,114]
    for y in levels:
        s.fill((-303,y,999,-269,y,1031),PAVE)
        top=103 if y==100 else y+4 if y<114 else 119
        for z in (999,1031):s.fill((-303,y+1,z,-269,top,z),'minecraft:white_concrete')
        for x in (-303,-269):s.fill((x,y+1,999,x,top,1031),'minecraft:white_concrete')
        for x in range(-300,-271,5):
            for z in (999,1031):s.fill((x,y+2,z,x+2,min(top,y+3),z),GLASS)
        for z in range(1002,1029,5):
            for x in (-303,-269):s.fill((x,y+2,z,x,min(top,y+3),z+2),GLASS)
        for x in (-298,-286,-274):
            for z in (1004,1014,1025):e.put(x,top,z,'minecraft:sea_lantern')
    # Cantilevered segmented station roof, horizontal brise-soleil and visible
    # structure give the building its transport character from every approach.
    for x in range(-305,-266):
        y=120+max(0,3-abs(x+286)//6)
        s.fill((x,y,997,x,y,1033),'minecraft:light_gray_concrete')
    for x in range(-302,-268,6):
        s.fill((x,115,999,x,119,999),'minecraft:gray_concrete')
        s.fill((x,115,1031,x,119,1031),'minecraft:gray_concrete')
    for y in (104,109,114):
        s.fill((-305,y,997,-267,y,997),'minecraft:gray_concrete')
        s.fill((-305,y,1033,-267,y,1033),'minecraft:gray_concrete')
    # B2 boat concourse and B1 restaurant face the lake. B1 has an outdoor
    # terrace and sliding/open entrances rather than an inaccessible facade.
    s.fill((-291,101,1031,-283,103,1034),AIR)
    s.fill((-303,104,1032,-269,104,1037),PAVE)
    s.fill((-299,105,1031,-293,107,1031),AIR)
    s.fill((-282,105,1031,-275,107,1031),AIR)
    s.fill((-302,105,1037,-270,105,1037),'minecraft:glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]')
    for x in (-297,-288,-278):
        for z in (1014,1023):
            e.put(x,105,z,'minecraft:dark_oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
            e.put(x,106,z,'minecraft:dark_oak_pressure_plate[powered=false]')
            s.bench(x-1,105,z+2)
    s.fill((-274,105,1002,-271,105,1009),'minecraft:smooth_quartz')
    s.sign(-275,107,1005,['湖畔餐厅','LAKE VIEW','B1F'],facing='west')
    # First-floor passenger hall: central public aisle, shops and ticket office.
    s.fill((-291,110,997,-283,112,1001),AIR)
    s.fill((-300,110,1003,-297,110,1008),'minecraft:smooth_quartz')
    s.fill((-300,111,1003,-300,111,1008),GLASS)
    s.sign(-297,112,1004,['桃源台站','索道 / 游船','票务服务'],facing='east')
    s.fill((-275,110,1005,-272,110,1017),'minecraft:dark_oak_planks')
    for z in (1007,1011,1015):
        s.fill((-270,110,z,-270,112,z+1),'minecraft:bookshelf')
    s.sign(-275,112,1005,['土产 / 便利店','1F'],facing='west')
    for x in (-298,-276):s.bench(x,110,1025)
    # Boarding level opens towards the surveyed northeast ropeway alignment.
    s.fill((-269,115,1002,-266,118,1007),AIR)
    s.fill((-268,114,1000,-261,114,1010),PAVE)
    for z in (1000,1010):s.fill((-268,115,z,-261,115,z),RAIL)
    s.fill((-267,114,1008,-262,114,1008),'minecraft:yellow_concrete')
    s.sign(-275,116,1001,['箱根索道','姥子 · 大涌谷','2F'],facing='north')
    for z in (1016,1024):s.bench(-293,115,z,7)
    # A continuous sheltered west stair connects all levels. Broad intermediate
    # landings also serve the restaurant terrace and lake promenade.
    stairs=[]
    for i,z in enumerate(range(1045,1002,-1)):
        y=100+min(14,i//3);stairs.append((-309,y,z))
        s.fill((-310,95,z,-308,y-1,z),STONE)
        s.fill((-310,y,z,-308,y,z),PAVE)
        s.fill((-310,y+1,z,-308,y+3,z),AIR)
        if i and i%3==0:
            s.fill((-310,y,z+1,-308,y,z+1),'minecraft:stone_brick_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
        s.fill((-312,y+1,z,-312,y+1,z),'minecraft:glass_pane[east=false,north=true,south=true,waterlogged=false,west=false]')
    s.paths.append(stairs)
    for y,z in [(100,1045),(104,1033),(109,1018),(114,1003)]:
        target=-303 if y>100 else-286
        # The lowest landing meets the open pier, not the upper restaurant slab.
        s.path([(x,y,z)for x in range(-309,target+1)],3)
        if y>100:s.fill((-304,y+1,z-1,-302,y+3,z+1),AIR)
    # Small ticket booth inside the boat concourse, separated from the walkway.
    s.fill((-300,101,1005,-297,101,1012),'minecraft:smooth_quartz')
    s.sign(-297,102,1008,['芦之湖游船','候船大厅 / B2F'],facing='east')
    for x in (-298,-278):s.bench(x,101,1022)
    # Wide floating-look boarding pontoon and actual connected gangways.
    s.path([(-286,100,z)for z in range(1032,1077)],5,'minecraft:spruce_planks')
    s.fill((-314,100,1074,-256,100,1081),'minecraft:spruce_planks')
    for x in range(-314,-255,12):s.fill((x,90,1077,x+1,99,1078),STONE)
    for z in (1074,1081):s.fill((-314,101,z,-256,101,z),'minecraft:spruce_fence[east=true,north=false,south=false,waterlogged=false,west=true]')
    s.fill((-288,101,1074,-284,103,1074),AIR)
    for x in (-308,-262):s.fill((x,101,1081,x+3,103,1081),AIR)
    s.sign(-291,102,1068,['芦之湖 · 桃源台港','元箱根 / 箱根町方面'])
    # Resolve the former road-end into a graded station forecourt. It joins
    # measured existing north/east roads and the retained store approach.
    grades=np.empty((18,81),np.int16)
    for x in range(-326,-245):
        for z in range(979,997):
            old=max((y for y in range(94,116)if e.state(x,y,z,True).split('[')[0]not in ('minecraft:air','minecraft:cave_air','minecraft:water')),default=99)
            blend=min(1,(z-979)/16);y=round(old+(109-old)*blend)
            grades[z-979,x+326]=min(109,max(103,y))
    for _ in range(12):
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            grades[dst]=np.minimum(grades[dst],grades[src]+1)
    for x in range(-326,-245):
        for z in range(979,997):
            y=int(grades[z-979,x+326])
            s.fill((x,95,z,x,y-1,z),STONE)
            s.fill((x,y+1,z,x,123,z),AIR)
            road=(981<=z<=986)or(-325<=x<=-319 and z<994)or(-251<=x<=-246 and z<994)
            e.put(x,y,z,'minecraft:black_concrete'if road else PAVE)
    # Public north entrance joins the forecourt exactly, with three clear lanes.
    s.path([(-287,109,z)for z in range(993,1003)],5)
    # Bus bays, marked pockets, shelters and a short taxi rank share the plaza.
    for x,name in [(-318,'箱根汤本 / 小田原'),(-277,'仙石原 / 强罗')]:
        s.fill((x,109,991,x+8,109,994),PAVE)
        for px in (x,x+8):s.fill((px,110,994,px,113,994),'minecraft:gray_concrete')
        s.fill((x-1,114,990,x+9,114,995),'minecraft:light_gray_concrete')
        s.bench(x+2,110,994,4)
        s.sign(x+1,112,993,['桃源台 公交',name])
    for x in range(-311,-288,6):s.fill((x,109,989,x+3,109,989),'minecraft:yellow_concrete')
    for x,z in [(-326,997),(-249,997),(-316,1036),(-276,1056)]:
        if z<1000:y=109
        elif z==1036:y=104
        else:y=100
        if z==1056:s.fill((x-1,100,z-1,x+1,100,z+1),'minecraft:spruce_planks')
        s.light(x,y+1,z)
    s.sign(-295,112,998,['桃 源 台','TOGENDAI','索道 · 游船 · 公交'])
    s.goals={'entrance':(-287,110,1000),'ticket_hall':(-286,110,1013),'restaurant':(-286,105,1014),
             'boat_hall':(-286,101,1025),'pontoon':(-286,101,1078),'ropeway':(-264,115,1004),
             'bus_west':(-313,110,992),'bus_east':(-272,110,992)}
    # Walkability is checked in the authored data, never as a gameplay gate.
    def passable(p):return e.state(*p).split('[')[0]in ('minecraft:air','minecraft:cave_air')
    def stand(p):
        x,y,z=p
        return passable(p)and passable((x,y+1,z))and e.state(x,y-1,z).split('[')[0]not in ('minecraft:air','minecraft:cave_air','minecraft:water','minecraft:glass_pane','minecraft:iron_bars')
    start=s.goals['entrance'];seen={start};queue=deque([start]);errors=[]
    while queue:
        x,y,z=queue.popleft()
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            for dy in (0,1,-1):
                q=(x+dx,y+dy,z+dz)
                if not(-331<=q[0]<=-244 and 100<=q[1]<=118 and 978<=q[2]<=1082)or q in seen:continue
                if stand(q):seen.add(q);queue.append(q);break
    for name,p in s.goals.items():
        if p not in seen:errors.append(['unreachable',name,p])
    for path in s.paths:
        if any(abs(p[1]-q[1])>1 for p,q in zip(path,path[1:])):errors.append(['path-grade'])
    # All new block-entity tags match an actual authored sign block.
    for row in s.devices:
        tag=row['After'];p=tuple(int(tag[k])for k in ('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['overwritten-sign',p,e.state(*p)])
    regions=e.save()
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(a.candidate/'block-entities.dat',gzipped=True)
    manifest=dict(world=str(world),bounds_xz=[-512,512,-1,1279],regions=regions,cells=sum(r['cells']for r in regions),
                  programme=['B2 boat concourse and pier','B1 lake restaurant','1F ticket hall, shops and bus forecourt','2F ropeway boarding'],
                  source='GSI station centre and official Hakone Navi Togendai floor plan; adapted playable dimensions',
                  official_plan='https://www.hakonenavi.jp/transportation/station/togendai/',progress_files_written=[],world_written=False)
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    report=dict(errors=errors,reachable_cells=len(seen),public_goals=s.goals,new_signs=len(s.devices),existing_devices_changed=0,actors_changed=0,visual_verified=False)
    (a.candidate/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Authored station connectivity requires correction')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','candidate'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
