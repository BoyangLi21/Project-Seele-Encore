"""Fit a compact side-platform station to a measured cardinal rail corridor.

This is a geographic adaptation, not a claim about an exact prototype building.
Only natural source material can be changed; old streets and fixtures stay exact.
Native service connections are deliberately a separate stage-three deliverable.
"""
import argparse,copy,heapq,json,math,shutil
from pathlib import Path
import nbtlib
import numpy as np
from author_wadagahara_station import GuardedEditor,NATURAL
from author_hakone_togendai import Station
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory,assert_preserved
from map_pipeline.launch_protection import load,check_candidate
from prepare_hakone_city_cross import packed

class Frame:
    def __init__(self,e,origin,rotation):self.e=e;self.origin=origin;self.rotation=rotation%4
    def point(self,x,y,z):
        for _ in range(self.rotation):x,z=-z,x
        return x+self.origin[0],y+self.origin[1],z+self.origin[2]
    def local(self,x,z):
        x-=self.origin[0];z-=self.origin[2]
        for _ in range(self.rotation):x,z=z,-x
        return x,z
    def direction(self,value):
        dirs=['north','east','south','west'];return dirs[(dirs.index(value)+self.rotation)%4]
    def block(self,state):
        if '['not in state:return state
        name,props=state[:-1].split('[',1);out=[]
        for item in props.split(','):
            k,v=item.split('=')
            if k=='facing'and v in('north','east','south','west'):v=self.direction(v)
            if k=='axis'and v in('x','z')and self.rotation%2:v='z'if v=='x'else'x'
            if k in('north','east','south','west'):k=self.direction(k)
            out.append(k+'='+v)
        return name+'['+','.join(sorted(out))+']'
    def state(self,x,y,z):return self.e.state(*self.point(x,y,z))
    def put(self,x,y,z,state):self.e.put(*self.point(x,y,z),self.block(state))
    def fill(self,x,y,z,X,Y,Z,state):
        for px in range(x,X+1):
            for pz in range(z,Z+1):
                for py in range(y,Y+1):self.put(px,py,pz,state)
    def box(self,q):
        a=self.point(*q[:3]);b=self.point(*q[3:]);return[min(a[i],b[i])for i in range(3)]+[max(a[i],b[i])for i in range(3)]

def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')

def author(a):
    config=json.loads(a.plan.read_text('utf8'));cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world'])
    a.out.mkdir(exist_ok=False);shutil.copytree(a.source/'source',a.out/'source');(a.out/'delta').mkdir()
    for name in('capture.json','measured.npz','captured-devices.dat'):shutil.copy2(a.source/name,a.out/name)
    tags=nbtlib.load(a.source/'captured-devices.dat')['Devices'];devices={tuple(int(t[k])for k in('x','y','z'))for t in tags}
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');assert_preserved(world,inventory(a.out/'preserved-native'));guard=load(world)
    e=GuardedEditor(a.out,devices);f=Frame(e,config['origin'],config['rotation']);s=Station(f);walk={};parts=[]
    def part(kind,box):parts.append(dict(kind=kind,bounds=f.box(box)))
    def fill(box,state):f.fill(*box,state)
    def floorbox(x,z,X,Z,kind):
        fill((x,-2,z,X,-1,Z),'minecraft:stone_bricks');fill((x,0,z,X,0,Z),'minecraft:smooth_stone')
        fill((x,1,z,X,5,Z),'minecraft:air')
        for px in range(x,X+1):
            for pz in range(z,Z+1):
                q=f.point(px,0,pz);walk[q[0],q[2]]=q[1]*2
        part(kind,(x,-2,z,X,5,Z))
    fill((-28,-2,-1,28,-2,2),'minecraft:stone');fill((-28,-1,-1,28,-1,2),'minecraft:gravel')
    fill((-28,0,-1,28,6,2),'minecraft:air');part('rail bed and reserved vehicle clearance',(-28,-2,-1,28,6,2))
    floorbox(-26,-7,26,-2,'48-block boarding platform with end margins')
    fill((-26,0,-2,26,0,-2),'projectseele:station_tactile_warning')
    floorbox(-8,-21,8,-8,'station hall and platform access');floorbox(-8,-27,8,-22,'station forecourt')
    for zz in(-21,-9):fill((-8,1,zz,8,4,zz),'minecraft:light_gray_concrete')
    for xx in(-8,8):fill((xx,1,-21,xx,4,-9),'minecraft:light_gray_concrete')
    for xx in(-6,4):
        for zz in(-21,-9):fill((xx,2,zz,xx+2,3,zz),'minecraft:light_gray_stained_glass')
    for zz in(-18,-13):
        for xx in(-8,8):fill((xx,2,zz,xx,3,zz+2),'minecraft:light_gray_stained_glass')
    for zz in(-21,-9):fill((-2,1,zz,2,3,zz),'minecraft:air')
    fill((-9,5,-22,9,5,-8),'minecraft:gray_concrete')
    fill((-8,6,-21,8,6,-9),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]');part('hall roof',(-9,5,-22,9,6,-8))
    for xx in(-6,6):
        for zz in(-18,-12):f.put(xx,4,zz,'minecraft:sea_lantern')
    fill((-7,1,-18,-5,1,-16),'minecraft:smooth_quartz')
    s.bench(4,1,-13,3);s.bench(-21,1,-7,3);s.bench(17,1,-7,3)
    fill((-27,6,-8,27,6,-2),'minecraft:light_gray_concrete')
    fill((-27,7,-7,27,7,-4),'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for xx in(-25,-13,13,25):
        fill((xx,1,-7,xx,5,-7),'minecraft:dark_oak_log[axis=y]');fill((xx,5,-7,xx,5,-3),'minecraft:dark_oak_log[axis=z]')
    part('supported platform canopy',(-27,1,-8,27,7,-2))
    for xx in(-19,0,19):f.put(xx,5,-5,'minecraft:sea_lantern')
    s.sign(0,4,-22,[config['name'],config['roman'],config['line'],'入口 / 改札'],'north')
    s.sign(-7,3,-15,['きっぷ','票务 / Tickets'],'east')
    s.sign(14,3,-4,[config['short_name'],config['roman'],config['directions']],'south')
    with np.load(a.authority/'network.npz')as ar:
        ax,az,aX,aZ=map(int,ar['bounds']);oldwalk=ar['walk'];oldgrade=ar['grade2']
    origin_y=config['origin'][1];target=tuple(config['street_anchor'][::2]);start3=f.point(0,0,-25);start=(start3[0],start3[2])
    targetgrade=round((config['street_anchor'][1]-1)*2)
    if not oldwalk[target[1]-az,target[0]-ax]or int(oldgrade[target[1]-az,target[0]-ax])!=targetgrade:raise ValueError('Street anchor is not the retained public floor')
    lo=min(origin_y,(targetgrade+1)//2)-2;hi=max(origin_y,(targetgrade+1)//2)+3
    l,t,r,b=cap['bounds_xz'];memo={}
    def clear(px,pz):
        if(px,pz)in memo:return memo[px,pz]
        ok=True
        for dx in(-1,0,1):
            for dz in(-1,0,1):
                xx,zz=px+dx,pz+dz
                if not(l<=xx<=r and t<=zz<=b):ok=False;continue
                if oldwalk[zz-az,xx-ax]:
                    yy=(int(oldgrade[zz-az,xx-ax])+1)//2
                    if any(e.state(xx,Y,zz,True).split('[')[0]not in AIR|{'minecraft:light'}for Y in(yy+1,yy+2)):ok=False
                elif any(e.state(xx,Y,zz,True).split('[')[0]not in NATURAL or(xx,Y,zz)in devices for Y in range(lo,hi+1)):ok=False
        memo[px,pz]=ok;return ok
    cost={start:0};parents={start:None};queue=[(0,start)]
    while queue:
        _,p=heapq.heappop(queue)
        if p==target:break
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz;u,v=f.local(*q)
            if not(-85<=u<=85 and -100<=v<=-25)or not clear(*q):continue
            value=cost[p]+1
            if value>=cost.get(q,float('inf')):continue
            cost[q]=value;parents[q]=p;heapq.heappush(queue,(value+abs(q[0]-target[0])+abs(q[1]-target[1]),q))
    if target not in parents:raise ValueError('No fixture-preserving three-wide street route')
    route=[];p=target
    while p is not None:route.append(p);p=parents[p]
    route.reverse();columns={};initial=origin_y*2;difference=targetgrade-initial
    if len(route)-8<abs(difference)*3:raise ValueError('Insufficient route length for half-block grades')
    for i,(px,pz)in enumerate(route):
        fraction=max(0,min(1,(i-5)/max(1,len(route)-10)));grade=initial+round(difference*fraction)
        for dx in(-1,0,1):
            for dz in(-1,0,1):columns[px+dx,pz+dz]=grade
    for(px,pz),grade in list(columns.items()):
        if oldwalk[pz-az,px-ax]:columns[px,pz]=int(oldgrade[pz-az,px-ax])
        elif(px,pz)in walk:columns[px,pz]=walk[px,pz]
    for(px,pz),grade in columns.items():
        y=(grade+1)//2
        if not oldwalk[pz-az,px-ax]:
            e.fill(px,y-2,pz,px,y-1,pz,'minecraft:stone_bricks')
            e.put(px,y,pz,'minecraft:smooth_stone'if grade%2==0 else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
            e.fill(px,y+1,pz,px,y+3,pz,'minecraft:air')
        walk[px,pz]=grade
    parts.append(dict(kind='three-wide graded street link',columns=[[x,z,g]for(x,z),g in sorted(columns.items())],vertical_margin=[-2,3]))
    # Every two-block foundation must meet existing natural bearing below it.
    bases={}
    for p in parts:
        if 'bounds'not in p or p['bounds'][1]!=origin_y-2:continue
        x,y,z,X,Y,Z=p['bounds']
        for px in range(x,X+1):
            for pz in range(z,Z+1):bases[px,pz]=y
    for(x,z),g in columns.items():
        if not oldwalk[z-az,x-ax]:bases[x,z]=(g+1)//2-2
    for(x,z),base in bases.items():
        for y in range(base-1,base-7,-1):
            state=e.state(x,y,z,True).split('[')[0]
            if state in SOIL:break
            if state not in AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:light'}:raise ValueError(('Foreign foundation bearing',x,y,z,state))
            e.put(x,y,z,'minecraft:stone_bricks');parts.append(dict(kind='measured footing extension',bounds=[x,y,z,x,y,z]))
        else:raise ValueError('Foundation has no measured soil bearing within six blocks')
    goals={k:list(f.point(*v))for k,v in dict(forecourt=(0,1,-25),entrance=(0,1,-20),ticket=(-4,1,-17),waiting=(3,1,-12),platform_centre=(0,1,-5),platform_end_a=(-23,1,-5),platform_end_b=(24,1,-5)).items()}
    goals['street']=config['street_anchor']
    for(px,pz),grade in list(walk.items()):
        y=(grade+1)//2
        if any(e.state(px,Y,pz).split('[')[0]not in AIR|{'minecraft:light'}for Y in(y+1,y+2)):del walk[px,pz]
    for actor in cap.get('actors',[]):
        px,py,pz=actor['pos']
        if any(q[0]-2<=px<=q[3]+2 and q[1]-2<=py<=q[4]+2 and q[2]-2<=pz<=q[5]+2 for q in(p['bounds']for p in parts if 'bounds'in p))or any(abs(px-x)<3 and abs(pz-z)<3 for x,z in columns):raise ValueError('Existing actor overlaps proposed station or street link')
    regions=e.save();e.regions.clear();changes=[];signs=[]
    for device in s.devices:
        tag=copy.deepcopy(device['After']);pos=f.point(*(int(tag[k])for k in('x','y','z')))
        for k,v in zip(('x','y','z'),pos):tag[k]=nbtlib.Int(v)
        changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'After':tag}))
        signs.append(dict(pos=list(pos),title=json.loads(str(tag['front_text']['messages'][0]))['text']))
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(a.out/'block-entities.dat',gzipped=True)
    bounds=f.box([-28,-4,-28,28,11,3]);endpoint_a=list(f.point(-24,0,0));endpoint_b=list(f.point(24,0,0))
    native=dict(rails=[dict(id=config['id']+'-platform-1',**{'from':endpoint_a,'to':endpoint_b},from_angle=f.direction('east')[0].upper(),to_angle=f.direction('west')[0].upper(),mode='TRAIN',kind='platform',vertical_radius=40)],stations=[dict(id=config['id'],name=config['name'],min=bounds[:3],max=bounds[3:],color=0x35875C)],lines=[])
    proof=dict(station=config['name'],station_id=config['id'],geographic_reference_centre=config['reference_centre'],reference_axis_degrees=config['reference_axis_degrees'],native_axis_degrees=90*(config['rotation']%2),platform_length=48,planned_maximum_consist_length=40,through_service_complete=False,parts=parts,public_columns=[[x,z,g]for(x,z),g in sorted(walk.items())],goals=goals,retained_street_anchor=config['street_anchor'],rail_clearance_bounds=f.box([-24,0,-1,24,4,2]),expected_signs=signs,native_plan='native-station-plan.json',geographic_adaptation=True,source_authority=str(a.authority),physical_scope_complete=False,world_written=False)
    write(a.out/'station-design.json',proof);write(a.out/'native-station-plan.json',native);write(a.out/'authoring-plan.json',config)
    write(a.out/'manifest.json',dict(world=str(world),kind='measured-regional-station',bounds_xz=cap['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),station_design='station-design.json',native_station_pending=True,world_written=False))
    write(a.out/'launch-protection.json',check_candidate(guard,a.out));write(a.out/'functional-check.json',dict(errors=['Independent station verification pending']))
    print('Prepared station',config['name'],sum(r['cells']for r in regions),'cells;',len(walk),'public columns;',len(route),'street-link points.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','plan','out'):p.add_argument('--'+n,type=Path,required=True)
    author(p.parse_args())
