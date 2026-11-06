"""Build a measured north-side station and its connection to the installed street.

The 48-block platform reserves capacity for compact regional consists. Native
station registration follows separately; through services belong to stage 3.
Every changed source cell must be natural soil, grass or air. Existing devices,
public surfaces, buildings, native identities and actors remain protected.
"""
import argparse,copy,heapq,json,shutil
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory,assert_preserved
from map_pipeline.launch_protection import load,check_candidate

NATURAL=SOIL|AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:light'}

class GuardedEditor(Editor):
    def __init__(self,folder,devices):super().__init__(folder);self.devices=devices
    def put(self,x,y,z,name):
        current=self.state(x,y,z)
        if current==name:return
        before=self.state(x,y,z,True)
        if (x,y,z)in self.devices:raise ValueError('Existing device in station construction')
        if before.split('[')[0]not in NATURAL:raise ValueError(('Unowned original station cell',(x,y,z),before,name))
        super().put(x,y,z,name)
    def fill(self,x,y,z,X,Y,Z,name):
        for px in range(x,X+1):
            for pz in range(z,Z+1):
                for py in range(y,Y+1):self.put(px,py,pz,name)

def author(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world'])
    a.out.mkdir(exist_ok=False);shutil.copytree(a.source/'source',a.out/'source');(a.out/'delta').mkdir()
    for name in('capture.json','measured.npz','captured-devices.dat'):shutil.copy2(a.source/name,a.out/name)
    tags=nbtlib.load(a.source/'captured-devices.dat')['Devices'];devices={tuple(int(t[k])for k in('x','y','z'))for t in tags}
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        assert_preserved(world,inventory(a.out/'preserved-native'));guard=load(world)
    e=GuardedEditor(a.out,devices);s=Station(e);walk={};parts=[];goals={}
    def fill(box,name):e.fill(*box,name)
    def floorbox(x,z,X,Z,y=-72,kind='station public floor'):
        fill((x,y-2,z,X,y-1,Z),'minecraft:stone_bricks');fill((x,y,z,X,y,Z),'minecraft:smooth_stone')
        fill((x,y+1,z,X,y+5,Z),'minecraft:air')
        for px in range(x,X+1):
            for pz in range(z,Z+1):walk[px,pz]=y*2
        parts.append(dict(kind=kind,bounds=[x,y-2,z,X,y+5,Z]))
    # Through-track datum and platform: the native renderer supplies the rails.
    fill((2498,-74,-1160,2554,-74,-1157),'minecraft:stone')
    fill((2498,-73,-1160,2554,-73,-1157),'minecraft:gravel')
    fill((2498,-72,-1160,2554,-66,-1157),'minecraft:air')
    parts.append(dict(kind='rail bed and reserved vehicle clearance',bounds=[2498,-74,-1160,2554,-66,-1157]))
    floorbox(2500,-1166,2552,-1161,kind='48-block boarding platform with end margins')
    fill((2500,-72,-1161,2552,-72,-1161),'projectseele:station_tactile_warning')
    floorbox(2518,-1180,2534,-1167,kind='station hall and platform access')
    floorbox(2518,-1186,2534,-1181,kind='station forecourt')
    # Low station hall, with windows, two generous doors and a clear central aisle.
    for zz in(-1180,-1168):fill((2518,-71,zz,2534,-68,zz),'minecraft:light_gray_concrete')
    for xx in(2518,2534):fill((xx,-71,-1180,xx,-68,-1168),'minecraft:light_gray_concrete')
    for xx in(2520,2530):
        for zz in(-1180,-1168):fill((xx,-70,zz,xx+2,-69,zz),'minecraft:light_gray_stained_glass')
    for zz in(-1177,-1172):
        for xx in(2518,2534):fill((xx,-70,zz,xx,-69,zz+2),'minecraft:light_gray_stained_glass')
    for zz in(-1180,-1168):fill((2524,-71,zz,2528,-69,zz),'minecraft:air')
    fill((2517,-67,-1181,2535,-67,-1167),'minecraft:gray_concrete')
    fill((2518,-66,-1180,2534,-66,-1168),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    parts.append(dict(kind='hall roof',bounds=[2517,-67,-1181,2535,-66,-1167]))
    for xx in(2520,2532):
        for zz in(-1177,-1171):e.put(xx,-68,zz,'minecraft:sea_lantern')
    # Ticket counter and waiting seats stand outside the through aisle.
    fill((2519,-71,-1177,2521,-71,-1175),'minecraft:smooth_quartz')
    s.bench(2530,-71,-1172,3);s.bench(2505,-71,-1166,3);s.bench(2543,-71,-1166,3)
    # Shallow pitched canopy with explicit posts and transverse bearing beams.
    fill((2499,-66,-1167,2553,-66,-1161),'minecraft:light_gray_concrete')
    fill((2499,-65,-1166,2553,-65,-1163),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for xx in(2501,2513,2539,2551):
        fill((xx,-71,-1166,xx,-67,-1166),'minecraft:dark_oak_log[axis=y]')
        fill((xx,-67,-1166,xx,-67,-1162),'minecraft:dark_oak_log[axis=z]')
    parts.append(dict(kind='supported platform canopy',bounds=[2499,-71,-1167,2553,-65,-1161]))
    for xx in(2507,2526,2545):e.put(xx,-67,-1164,'minecraft:sea_lantern')
    s.sign(2526,-68,-1181,['和田河原駅','WADAGAHARA','大雄山線','入口 / 改札'],'north')
    s.sign(2519,-69,-1174,['きっぷ','票务 / Tickets'],'east')
    s.sign(2540,-69,-1163,['和田河原','WADAGAHARA','小田原 ←  → 大雄山'],'south')
    # Three-wide public path, with half-block grades over the one-block rise.
    with np.load(a.authority/'network.npz')as f:
        ax,az,aX,aZ=map(int,f['bounds']);oldwalk=f['walk'];oldgrade=f['grade2']
    def corridor_clear(px,pz):
        for dx in(-1,0,1):
            for dz in(-1,0,1):
                xx,zz=px+dx,pz+dz
                if oldwalk[zz-az,xx-ax]:
                    yy=(int(oldgrade[zz-az,xx-ax])+1)//2
                    if any(e.state(xx,Y,zz,True).split('[')[0]not in AIR|{'minecraft:light'}for Y in(yy+1,yy+2)):return False
                elif any(e.state(xx,Y,zz,True).split('[')[0]not in NATURAL or(xx,Y,zz)in devices for Y in range(-75,-68)):
                    return False
        return True
    start=(2526,-1184);target=(2515,-1202);cost={start:0};parents={start:None};queue=[(0,start)]
    while queue:
        _,p=heapq.heappop(queue)
        if p==target:break
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz
            if not(2504<=q[0]<=2540 and -1210<=q[1]<=-1184)or not corridor_clear(*q):continue
            value=cost[p]+1
            if value>=cost.get(q,float('inf')):continue
            cost[q]=value;parents[q]=p;heapq.heappush(queue,(value+abs(q[0]-target[0])+abs(q[1]-target[1]),q))
    if target not in parents:raise ValueError('No three-wide station link avoiding installed street fixtures')
    route=[];p=target
    while p is not None:route.append(p);p=parents[p]
    route.reverse();points=[]
    for index,(px,pz)in enumerate(route):
        grade=-144 if index<=5 else -145 if index<=10 else -146
        points.append([int(px),grade/2,int(pz)])
    columns={}
    for px,grade,pz in points:
        for dx in(-1,0,1):
            for dz in(-1,0,1):columns[px+dx,pz+dz]=round(grade*2)
    for(px,pz),grade in list(columns.items()):
        if oldwalk[pz-az,px-ax]:columns[px,pz]=int(oldgrade[pz-az,px-ax])
    for(px,pz),grade in columns.items():
        y=(grade+1)//2
        if oldwalk[pz-az,px-ax]:
            walk[px,pz]=grade;continue
        fill((px,y-2,pz,px,y-1,pz),'minecraft:stone_bricks')
        e.put(px,y,pz,'minecraft:smooth_stone'if grade%2==0 else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        fill((px,y+1,pz,px,y+3,pz),'minecraft:air');walk[px,pz]=grade
    parts.append(dict(kind='three-wide graded street link',columns=[[x,z,y]for(x,z),y in sorted(columns.items())],vertical_margin=[-2,3]))
    goals=dict(street=[2515,-72,-1202],forecourt=[2526,-71,-1184],entrance=[2526,-71,-1179],
        ticket=[2522,-71,-1176],waiting=[2529,-71,-1171],platform_centre=[2526,-71,-1164],
        platform_west=[2503,-71,-1164],platform_east=[2550,-71,-1164])
    # Passenger graph omits walls, posts and furniture; no blanket hall rectangle
    # is recorded as traversable merely because its floor was built first.
    for (px,pz),grade in list(walk.items()):
        y=(grade+1)//2
        if any(e.state(px,Y,pz).split('[')[0]not in AIR|{'minecraft:light'}for Y in(y+1,y+2)):del walk[px,pz]
    regions=e.save();e.regions.clear()
    # Add sign/device payloads through the ordinary reversible NBT patch path.
    from prepare_hakone_city_cross import packed
    changes=[]
    for device in s.devices:
        tag=device['After'];pos=tuple(int(tag[k])for k in('x','y','z'))
        changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'After':tag}))
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(a.out/'block-entities.dat',gzipped=True)
    native=dict(rails=[dict(id='wadagahara-platform-1',**{'from':[2502,-72,-1159],'to':[2550,-72,-1159]},
        from_angle='E',to_angle='W',mode='TRAIN',kind='platform',vertical_radius=40)],
        stations=[dict(id='wadagahara',name='和田河原駅',min=[2498,-76,-1187],max=[2554,-61,-1156],color=0x35875C)],lines=[])
    proof=dict(station='和田河原駅',geographic_reference_centre=[2525.6115,-1159.225],
        reference_axis_degrees=10.763,native_axis_degrees=0,platform_length=48,
        planned_maximum_consist_length=40,through_service_complete=False,parts=parts,
        public_columns=[[x,z,y]for(x,z),y in sorted(walk.items())],goals=goals,
        retained_street_anchor=[2515,-72,-1202],physical_scope_complete=False,world_written=False)
    (a.out/'station-design.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
    (a.out/'native-station-plan.json').write_text(json.dumps(native,ensure_ascii=False,indent=2),'utf8')
    manifest=dict(world=str(world),kind='measured-regional-station',bounds_xz=cap['bounds_xz'],regions=regions,
        cells=sum(r['cells']for r in regions),station_design='station-design.json',native_station_pending=True,world_written=False)
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(guard,a.out),indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Independent station verification pending']),indent=2),'utf8')
    print('Prepared Wadagahara station candidate:',manifest['cells'],'changed cells;',len(walk),'public columns;',len(changes),'signs.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    author(p.parse_args())
