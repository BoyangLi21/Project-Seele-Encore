"""Author walkable district buildings while moving every original device intact.

Coordinates are local to a frontage; all placement is rotated as one component.
The recorder contains cuboids, not another world/chunk decoder.
"""
import copy,json,re
from pathlib import Path
import nbtlib
import numpy as np

DIRECTIONS=['south','west','north','east']


def rotate_state(state,rotation):
    def change(match):
        return 'facing='+DIRECTIONS[(DIRECTIONS.index(match[1])+rotation)%4]
    state=re.sub(r'facing=(south|west|north|east)',change,state)
    if rotation%2:
        state=re.sub(r'axis=([xz])',lambda m:'axis='+('z'if m[1]=='x'else'x'),state)
    if 'rotation='in state:
        state=re.sub(r'rotation=(\d+)',lambda m:'rotation='+str((int(m[1])+4*rotation)%16),state)
    return state


class Frontage:
    def __init__(self,site):
        self.site=site;self.operations=[];self.devices=[];self.walk=[];self.doors=[]
    def point(self,x,y,z):
        for _ in range(self.site['rotation']):x,z=-z,x
        return [int(x+self.site['centre'][0]),int(y+self.site['floor']),int(z+self.site['centre'][1])]
    def fill(self,x,y,z,X,Y,Z,state):
        a=self.point(x,y,z);b=self.point(X,Y,Z)
        self.operations.append([*map(min,zip(a,b)),*map(max,zip(a,b)),rotate_state(state,self.site['rotation'])])
    def put(self,x,y,z,state):self.fill(x,y,z,x,y,z,state)
    def walkpoint(self,x,y,z):self.walk.append(self.point(x,y,z))
    def device(self,item,pos,state=None):
        self.put(*pos,state or item['state']);target=self.point(*pos)
        tag=copy.deepcopy(item['nbt'])
        for k,v in zip(('x','y','z'),target):tag[k]=nbtlib.Int(v)
        self.devices.append(dict(source=item['source'],target=target,before=item['nbt'],after=tag))


def load_original(folder,row):
    with np.load(folder/(row['snapshot']+'.npz'))as data:
        origin=data['origin'];blocks=data['blocks'];names=data['palette']
    result=[]
    for tag in nbtlib.load(folder/(row['snapshot']+'.dat'))['BlockEntities']:
        pos=[int(tag[k])for k in ('x','y','z')];x,y,z=np.asarray(pos)-origin
        result.append(dict(source=pos,state=str(names[blocks[y,z,x]]),nbt=copy.deepcopy(tag)))
    return result


def text_use(devices):
    for item in devices:
        if str(item['nbt']['id'])=='minecraft:sign':
            lines=item['nbt'].get('front_text',{}).get('messages',[])
            if lines:return json.loads(str(lines[0])).get('text','')
    return '街角公园'


def author(site,row,folder):
    c=Frontage(site);hx,hz=site['half'];n=site['floors'];items=load_original(folder,row)
    use=text_use(items);residential=site['style']=='residential';variant=int(row['id'].split('/')[1].replace('-',''))%4
    wall=['minecraft:white_terracotta','minecraft:smooth_sandstone','minecraft:light_gray_concrete','minecraft:bricks'][variant]
    accent=['minecraft:dark_oak_planks','minecraft:gray_terracotta','minecraft:cyan_terracotta','minecraft:smooth_quartz'][variant]
    c.fill(-hx-2,0,-hz-2,hx+2,0,hz+2,'minecraft:smooth_stone')
    c.fill(-hx-2,1,-hz-2,hx+2,n*5+9,hz+2,'minecraft:air')
    if n==0:
        c.fill(-hx,0,-hz,hx,0,hz,'minecraft:grass_block[snowy=false]')
        c.fill(-1,0,-hz,1,0,hz+2,'minecraft:stone_bricks')
        c.fill(-hx,0,-1,hx,0,1,'minecraft:stone_bricks')
        for x,z in [(-hx+3,-hz+3),(hx-3,-hz+3),(-hx+3,hz-3),(hx-3,hz-3)]:
            c.fill(x,1,z,x,4,z,'minecraft:oak_log[axis=y]')
            c.fill(x-2,4,z-2,x+2,5,z+2,'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]')
            c.fill(x-1,6,z-1,x+1,6,z+1,'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]')
        for x in (-4,4):c.fill(x-1,1,3,x+1,1,3,'minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
        if items:raise ValueError('Unassigned park devices')
        for z in range(-hz,hz+3):c.walkpoint(0,1,z)
        return c,dict(id=row['id'],kind='park',use=use,site=site,door=c.point(0,1,hz),approach=c.point(0,1,hz+3))
    # A separate stair bay leaves an uninterrupted public corridor beside it.
    for level in range(n):
        y=level*5
        c.fill(-hx,y,-hz,hx,y,hz,'minecraft:smooth_stone')
        for z in (-hz,hz):c.fill(-hx,y+1,z,hx,y+4,z,wall)
        for x in (-hx,hx):c.fill(x,y+1,-hz,x,y+4,hz,wall)
        for x in range(-hx+2,hx-1,4):
            for z in (-hz,hz):
                c.fill(x,y+2,z,min(x+1,hx-1),y+3,z,'minecraft:light_gray_stained_glass')
                c.fill(x,y+1,z,min(x+1,hx-1),y+1,z,accent)
        for z in range(-hz+10,hz-2,4):
            for x in (-hx,hx):c.fill(x,y+2,z,x,y+3,z+1,'minecraft:light_gray_stained_glass')
        c.fill(-hx+5,y+1,-hz+1,-hx+5,y+3,hz-5,'minecraft:white_concrete')
        c.fill(-hx+5,y+1,-hz+8,-hx+5,y+2,-hz+10,'minecraft:air')
        for x,z in [(-hx+3,-hz+8),(2,0),(2,hz-3)]:c.put(x,y+4,z,'minecraft:sea_lantern')
        if residential and level:
            # Alternating recessed side balconies have a room entrance and a
            # complete outer parapet, rather than decorative floating slabs.
            x=hx if level%2 else-hx;sign=1 if x>0 else-1
            c.fill(min(x,x+2*sign),y,2,max(x,x+2*sign),y,6,'minecraft:stone_bricks')
            c.fill(x+2*sign,y+1,2,x+2*sign,y+1,6,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
            for z in (2,6):c.fill(min(x,x+sign),y+1,z,max(x,x+sign),y+1,z,wall)
            c.fill(x,y+1,4,x,y+2,4,'minecraft:air')
        elif not residential:
            # Vertical piers and floor spandrels break up office glazing.
            for x in (-hx,-2,hx):c.fill(x,y+1,hz,x,y+4,hz,accent)
        for z in range(-hz+8,hz):c.walkpoint(-hx+3,y+1,z)
    for level in range(n-1):
        y=level*5
        c.fill(-hx+2,y+5,-hz+2,-hx+4,y+5,-hz+5,'minecraft:air')
        for step in range(5):
            c.fill(-hx+2,y+1+step,-hz+2+step,-hx+4,y+1+step,-hz+2+step,
                   'minecraft:stone_brick_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
            c.walkpoint(-hx+3,y+2+step,-hz+2+step)
    roof=n*5;c.fill(-hx,roof,-hz,hx,roof,hz,'minecraft:stone_bricks')
    if residential and n<=4:
        for step in range(5):
            for sign in (-1,1):c.fill(-hx-1,roof+1+step,sign*(hz-step),hx+1,roof+1+step,sign*(hz-step),'minecraft:dark_oak_planks')
        c.fill(-hx-1,roof+5,-hz+4,hx+1,roof+5,hz-4,'minecraft:dark_oak_planks')
    else:
        for z in (-hz,hz):c.fill(-hx,roof+1,z,hx,roof+1,z,accent)
        for x in (-hx,hx):c.fill(x,roof+1,-hz,x,roof+1,hz,accent)
        c.fill(-hx+2,roof+1,-hz+2,-hx+5,roof+2,-hz+4,'minecraft:light_gray_concrete')
        c.fill(-hx+2,roof+3,-hz+2,-hx+5,roof+3,-hz+4,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]')
    # Shops use street glazing at ground level; residential entries have a
    # narrower porch. All doors have the same measured two-block clear opening.
    for x in (-hx+2,3):c.fill(x,1,hz,min(x+3,hx-1),3,hz,'minecraft:glass')
    c.fill(0,1,hz-2,1,3,hz,'minecraft:air')
    for x,hinge in [(0,'left'),(1,'right')]:
        for y,half in [(1,'lower'),(2,'upper')]:c.put(x,y,hz,f'minecraft:oak_door[facing=south,half={half},hinge={hinge},open=false,powered=false]')
        c.doors.append(c.point(x,1,hz))
    c.fill(-hx+1,4,hz+1,hx-1,4,hz+2,accent)
    c.fill(0,3,hz,1,3,hz,'minecraft:glass')
    # The stair lobby is reachable directly from the front vestibule.
    for x in range(-hx+3,2):c.walkpoint(x,1,hz-3)
    if '书店'in use:
        for z in (-1,3):c.fill(1,1,z,hx-2,2,z,'minecraft:bookshelf')
    elif '喫茶'in use:
        for x,z in [(1,0),(hx-3,4)]:
            c.put(x,1,z,'minecraft:oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
            c.put(x,2,z,'minecraft:oak_pressure_plate[powered=false]')
            for dz,face in [(-2,'south'),(2,'north')]:c.put(x,1,z+dz,f'minecraft:oak_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]')
    elif '诊所'in use:
        c.fill(1,1,2,hx-2,1,2,'minecraft:white_concrete');c.fill(hx-2,1,4,hx-2,2,5,'minecraft:quartz_block')
    elif '商店'in use:
        for z in (-1,3):c.fill(1,1,z,hx-2,1,z,'minecraft:bookshelf')
    # Inventory and bedroom contents keep their original floor association.
    slots={};feet={};bedslots={};fixture=0;signcount=0
    for item in items:
        if str(item['nbt']['id'])=='minecraft:bed'and 'part=foot'in item['state']:
            level=(item['source'][1]-row['floor']-1)//5;slot=bedslots.get(level,0);bedslots[level]=slot+1
            if slot>=2 or not 0<=level<n:raise ValueError('Unassigned original bed')
            feet[tuple(item['source'])]=(hx-2-slot*4,level*5+1,-hz+7)
    for item in items:
        kind=str(item['nbt']['id']);state=item['state']
        if kind=='minecraft:chest':
            level=(item['source'][1]-row['floor']-1)//5;slot=slots.get(level,0);slots[level]=slot+1
            if slot>=3 or not 0<=level<n:raise ValueError('Unassigned original inventory')
            pos=(hx-2-slot*2,level*5+1,-hz+2)
            state=re.sub(r'facing=\w+','facing=south',state)
        elif kind=='minecraft:bed':
            facing=re.search(r'facing=(\w+)',state)[1];dx,dz={'south':(0,1),'north':(0,-1),'east':(1,0),'west':(-1,0)}[facing]
            sx,sy,sz=item['source'];head='part=head'in state
            foot=(sx-dx,sy,sz-dz)if head else(sx,sy,sz)
            bx,by,bz=feet[foot];pos=(bx,by,bz+int(head));state=re.sub(r'facing=\w+','facing=south',state)
        elif kind=='minecraft:sign':
            pos=(4+signcount*2,3,hz+1);signcount+=1
            state='minecraft:oak_wall_sign[facing=south,waterlogged=false]'
        elif kind=='projectseele:period_fixture':
            slotpos=[(-hx+2,1,hz+1),(-hx+2,1,hz-3),(-hx+5,1,hz+1),(0,5,hz+1),(hx-2,1,hz-3),(hx-2,1,hz+1)]
            pos=slotpos[fixture];fixture+=1;state=re.sub(r'facing=\w+','facing=south',state)
            if 'kind=shop_sign'in state:c.put(pos[0],pos[1],pos[2]-1,wall)
        else:raise ValueError('Unassigned original device '+kind)
        c.device(item,pos,state)
    return c,dict(id=row['id'],kind='building',use=use,site=site,door=c.point(0,1,hz),approach=c.point(0,1,hz+3))
