"""Rehouse displaced neighbourhood uses around the cross, retaining full inventories.

This module authors onto the measured city canvas only; it never opens a save
for writing. The four former lift corners become ordinary mixed-use terraces.
"""
import copy,json
from pathlib import Path
import nbtlib
import numpy as np

# Parcel positions lie in the retired corners, outside every moving footprint.
# Original uses and floor inventories stay associated with their original IDs.
SITES={
 'tokyo_west/09-07':(-142,48,83,13,12,'minecraft:smooth_quartz','minecraft:light_blue_terracotta'),
 'tokyo_west/09-09':(-150,368,82,13,13,'minecraft:bricks','minecraft:gray_terracotta'),
 'tokyo_south/09-01':(-124,417,84,13,12,'minecraft:cut_sandstone','minecraft:green_terracotta'),
 'tokyo_south/10-01':(190,52,83,14,13,'minecraft:white_concrete','minecraft:light_blue_terracotta'),
 'tokyo_south/11-01':(190,94,81,14,12,'minecraft:bricks','minecraft:brown_terracotta'),
 'tokyo_south/12-01':(190,366,90,14,13,'minecraft:light_gray_concrete','minecraft:gray_terracotta'),
 'tokyo_south/13-01':(190,416,101,13,12,'minecraft:smooth_sandstone','minecraft:orange_terracotta'),
}
PARK=(-165,81,-123,105,82)
PARKS={'tokyo_west/09-08':PARK}


def configure(file):
    global SITES,PARKS
    data=json.loads(Path(file).read_text('utf8'))
    SITES={k:tuple(v)for k,v in data['buildings'].items()}
    PARKS={k:tuple(v)for k,v in data['parks'].items()}


def retire_old_lots(c,folder):
    rows=json.loads((folder/'manifest.json').read_text('utf-8'))['plots'];result=[]
    for row in rows:
        a=np.load(folder/(row['snapshot']+'.npz'));origin=a['origin'];states=a['palette'];blocks=a['blocks']
        bes=list(nbtlib.load(folder/(row['snapshot']+'.dat'))['BlockEntities']);devices=[]
        for tag in bes:
            p=tuple(int(tag[k])for k in ('x','y','z'))
            if c.original_be.get(p)!=tag:raise ValueError(f'Changed original parcel inventory at {p}')
            local=np.asarray(p)-origin;state=str(states[blocks[local[1],local[2],local[0]]])
            devices.append(dict(source=p,state=state,nbt=copy.deepcopy(tag)))
            c.be.pop(p,None)
        lo=row['source_bounds_xyz'][:3];hi=row['source_bounds_xyz'][3:]
        # The full parcel shell is retired, including its old upper floors.
        # Native railway preservation remains active on the measured canvas.
        c.fill(lo[0],row['floor'],lo[2],hi[0],hi[1],hi[2],'minecraft:air')
        result.append(dict(row,devices=devices))
    return result


def parcel_mask(c,rows):
    mask=np.zeros(c.blocks.shape[1:],bool)
    for a,b,d,e,_ in PARKS.values():mask[b-c.z0:e+1-c.z0,a-c.x0:d+1-c.x0]=True
    for row in rows:
        if row['id']not in SITES:continue
        x,z,f,hx,hz,_,_=SITES[row['id']]
        mask[z-hz-c.z0:z+hz+1-c.z0,x-hx-c.x0:x+hx+1-c.x0]=True
    return mask


def place_device(c,device,pos,state=None):
    x,y,z=pos;c.put(x,y,z,state or device['state'])
    tag=copy.deepcopy(device['nbt'])
    for key,value in zip(('x','y','z'),pos):tag[key]=nbtlib.Int(value)
    c.be[tuple(pos)]=tag
    return dict(source=list(device['source']),target=list(pos),id=str(tag['id']))


def build_parcels(c,rows,protected):
    reports=[];footprint=parcel_mask(c,rows)
    if np.any(footprint&protected):raise ValueError('A replacement parcel intersects an original device, rail pier or moving lot')
    for row in rows:
        if row['id']not in SITES:continue
        x,z,f,hx,hz,wall,accent=SITES[row['id']];n=row['storeys'];x0,x1=x-hx,x+hx;z0,z1=z-hz,z+hz
        # The known GeoFront roof remains beneath the engineered city terraces.
        c.fill(x0-2,24,z0-2,x1+2,24,z1+2,'projectseele:nerv_structural_panel')
        c.fill(x0-2,25,z0-2,x1+2,f-1,z1+2,'minecraft:stone')
        c.fill(x0-2,f,z0-2,x1+2,f,z1+2,'minecraft:smooth_stone')
        c.fill(x0-2,f+1,z0-2,x1+2,f+n*5+5,z1+2,'minecraft:air')
        for level in range(n):
            y=f+level*5
            c.fill(x0,y,z0,x1,y,z1,'minecraft:smooth_stone')
            for zz in (z0,z1):c.fill(x0,y+1,zz,x1,y+4,zz,wall)
            for xx in (x0,x1):c.fill(xx,y+1,z0,xx,y+4,z1,wall)
            for xx in range(x0+2,x1-1,5):
                for zz in (z0,z1):
                    c.fill(xx,y+2,zz,min(xx+2,x1-1),y+3,zz,'minecraft:light_gray_stained_glass')
                    c.fill(xx,y+1,zz,min(xx+2,x1-1),y+1,zz,accent)
            for zz in range(z0+11,z1-1,5):
                for xx in (x0,x1):c.fill(xx,y+2,zz,xx,y+3,min(zz+2,z1-1),'minecraft:light_gray_stained_glass')
            # A circulation spine separates the stairwell from occupied rooms.
            c.fill(x0+9,y+1,z0+1,x0+9,y+3,z1-5,'minecraft:white_concrete')
            c.fill(x0+9,y+1,z0+10,x0+9,y+2,z0+12,'minecraft:air')
            c.put(x0+7,y+4,z0+10,'minecraft:sea_lantern')
            c.put(x1-5,y+4,z0+8,'minecraft:sea_lantern')
            c.fill(x1-8,y+1,z0+1,x1-8,y+3,z0+5,accent)
        # Each flight has its own opening in the next floor; no solid slab is
        # restored over its headroom when the next storey is built.
        for level in range(n-1):
            y=f+level*5
            c.fill(x0+3,y+5,z0+3,x0+5,y+5,z0+7,'minecraft:air')
            for step in range(5):
                c.fill(x0+3,y+1+step,z0+3+step,x0+5,y+1+step,z0+3+step,
                       'minecraft:stone_brick_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
        roof=f+n*5
        c.fill(x0,roof,z0,x1,roof,z1,'minecraft:smooth_stone')
        for zz in (z0,z1):c.fill(x0,roof+1,zz,x1,roof+1,zz,accent)
        for xx in (x0,x1):c.fill(xx,roof+1,z0,xx,roof+1,z1,accent)
        c.fill(x0+3,roof+1,z0+3,x0+6,roof+2,z0+5,'minecraft:light_gray_concrete')
        c.fill(x0+3,roof+3,z0+3,x0+6,roof+3,z0+5,'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]')
        # Two-leaf entrance, shop glazing, transom and a weather canopy.
        c.fill(x-1,f+1,z1-2,x+2,f+3,z1,'minecraft:air')
        for dx,hinge in ((0,'left'),(1,'right')):
            for dy,half in ((1,'lower'),(2,'upper')):
                c.put(x+dx,f+dy,z1,f'minecraft:oak_door[facing=south,half={half},hinge={hinge},open=false,powered=false]')
        c.fill(x,f+3,z1,x+1,f+3,z1,'minecraft:light_gray_stained_glass')
        c.fill(x0+1,f+4,z1+1,x1-1,f+4,z1+2,accent)
        for xx in (x0+3,x1-3):c.fill(xx,f+1,z1+2,xx,f+3,z1+2,'minecraft:polished_basalt[axis=y]')
        c.fill(x0+2,f+1,z1-6,x0+6,f+1,z1-6,'minecraft:oak_planks')
        # Ground-floor furnishings follow the existing use, recovered from
        # the actual sign instead of assigning every building the same room.
        signs=[d for d in row['devices']if str(d['nbt']['id'])=='minecraft:sign']
        name=''
        if signs:
            messages=signs[0]['nbt'].get('front_text',{}).get('messages',[])
            if messages:name=json.loads(str(messages[0])).get('text','')
        if '书店'in name:
            for zz in range(z0+9,z1-6,4):c.fill(x1-6,f+1,zz,x1-2,f+2,zz,'minecraft:bookshelf')
        elif '喫茶'in name:
            for xx,zz in [(x1-5,z0+10),(x1-5,z0+16),(x,z0+16)]:
                c.put(xx,f+1,zz,'minecraft:oak_fence[east=false,north=false,south=false,waterlogged=false,west=false]')
                c.put(xx,f+2,zz,'minecraft:oak_pressure_plate[powered=false]')
                for dz,face in ((-2,'south'),(2,'north')):
                    c.put(xx,f+1,zz+dz,f'minecraft:oak_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]')
        elif '商店'in name:
            for zz in (z0+10,z0+15):c.fill(x1-7,f+1,zz,x1-2,f+2,zz,'minecraft:bookshelf')
        moved=[];chests=sorted([d for d in row['devices']if str(d['nbt']['id'])=='minecraft:chest'],key=lambda d:d['source'][1])
        floor_chests={}
        for d in chests:
            level=(d['source'][1]-row['floor']-1)//5;slot=floor_chests.get(level,0);floor_chests[level]=slot+1
            if not 0<=level<n or slot>2:raise ValueError('Unassigned original inventory floor')
            moved.append(place_device(c,d,(x1-3-slot*2,f+level*5+1,z0+3)))
        bed_feet=sorted([d['source']for d in row['devices']if str(d['nbt']['id'])=='minecraft:bed'and 'part=foot'in d['state']],key=lambda p:(p[1],p[0],p[2]))
        bed_positions={};floor_beds={}
        for foot in bed_feet:
            level=(foot[1]-row['floor']-1)//5;slot=floor_beds.get(level,0);floor_beds[level]=slot+1
            if not 0<=level<n or slot>1:raise ValueError('Unassigned original bed floor')
            bed_positions[foot]=(x1-5-slot*6,f+level*5+1,z0+10)
        for d in row['devices']:
            kind=str(d['nbt']['id'])
            if kind=='minecraft:chest':continue
            if kind=='minecraft:sign':pos=(x+4,f+3,z1+1)
            elif kind=='minecraft:bed':
                facing=next(v for v in ('north','south','east','west')if 'facing='+v in d['state'])
                dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[facing]
                head='part=head'in d['state'];sx,sy,sz=d['source'];foot=(sx-dx,sy,sz-dz)if head else(sx,sy,sz)
                bx,by,bz=bed_positions[foot];pos=(bx+dx,by,bz+dz)if head else(bx,by,bz)
            else:raise ValueError(f'Unassigned preserved device {kind}')
            moved.append(place_device(c,d,pos))
        reports.append(dict(id=row['id'],kind='building',use=name,centre=[x,f,z],bounds=[x0,f,z0,x1,roof+3,z1],
            floors=n,door=[x,f+1,z1],approach_start=[x,z1+3],devices=moved))
    for name,bounds in PARKS.items():reports.append(build_park(c,name,bounds))
    return reports,footprint


def build_park(c,name,bounds):
    x0,z0,x1,z1,f=bounds;x=(x0+x1)//2
    c.fill(x0,24,z0,x1,24,z1,'projectseele:nerv_structural_panel')
    c.fill(x0,25,z0,x1,f-1,z1,'minecraft:stone')
    c.fill(x0,f,z0,x1,f,z1,'minecraft:grass_block[snowy=false]')
    c.fill(x0,f+1,z0,x1,f+8,z1,'minecraft:air')
    c.fill(x-1,f,z0+2,x+1,f,z1,'minecraft:smooth_stone')
    c.fill(x0+3,f,z0+12,x1-3,f,z0+14,'minecraft:smooth_stone')
    for xx,zz in ((x0+5,z0+5),(x1-5,z0+5),(x0+5,z1-5),(x1-5,z1-5)):
        c.fill(xx,f+1,zz,xx,f+4,zz,'minecraft:oak_log[axis=y]')
        c.fill(xx-2,f+4,zz-2,xx+2,f+5,zz+2,'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]')
        c.fill(xx-1,f+6,zz-1,xx+1,f+6,zz+1,'minecraft:oak_leaves[distance=7,persistent=true,waterlogged=false]')
    for xx in (x0+11,x1-11):
        c.fill(xx-1,f+1,z0+10,xx+1,f+1,z0+10,'minecraft:oak_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]')
    return dict(id=name,kind='park',use='街角公园',centre=[x,f,(z0+z1)//2],
        bounds=[x0,f,z0,x1,f+6,z1],floors=0,door=[x,f+1,z1],approach_start=[x,z1+3],devices=[])
