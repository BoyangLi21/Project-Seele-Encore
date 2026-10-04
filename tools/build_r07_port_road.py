"""A measured, graded harbor approach with half-height ramps and supported river bridges."""
import json,math
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
import regional_voxels as vox

OUT=vox.ROOT/'artifacts/world_expansion_r07';vox.OUT=OUT
regions=[]
for name in ('connection_west','connection_joint','connection_east','port'):
    with np.load(OUT/'survey'/(name+'.npz')) as archive:
        regions.append({key:archive[key] for key in ('lo','hi','top','water')})
def surface(x,z):
    for d in regions:
        lo=d['lo'];hi=d['hi']
        if lo[0]<=x<=hi[0] and lo[2]<=z<=hi[2]:
            return int(d['top'][z-lo[2],x-lo[0]]),bool(d['water'][z-lo[2],x-lo[0]]) and x<1224
    raise RuntimeError(('Unsurveyed road column',x,z))
curve=PchipInterpolator([444,496,576,688,992,1216,1296],[304,304,400,432,432,432,432])
def height(x):return round((80-12*min(1,max(0,(x-496)/720)))*2)/2
p=vox.Painter();p.protect((432,32,270,444,159,464),'existing_city')
chunks={};bridge_columns=0
for x in range(445,1297):
    centre=float(curve(x));h=height(x);f=math.floor(h)
    for z in range(math.floor(centre)-27,math.ceil(centre)+28):
        distance=abs(z+.5-(centre+.5));original,water=surface(x,z)
        if distance>26 or water or x>=1224:continue
        t=max(0,min(1,(distance-7)/19));t=t*t*(3-2*t);desired=round(f*(1-t)+original*t)
        key=(x//16,z//16)
        if key not in chunks:
            chunks[key]=(np.zeros((16,16),int),np.zeros((16,16),bool))
        a,active=chunks[key];a[z&15,x&15]=desired;active[z&15,x&15]=True
for (cx,cz),(heights,active) in chunks.items():p.heightfield(cx,cz,heights,active,'r07/port_road/land_grade')
for x in range(445,1297):
    centre=round(float(curve(x)));h=height(x);f=math.floor(h);water=surface(x,centre)[1]
    o='r07/port_road'
    for dz in range(-6,7):
        z=centre+dz;side=abs(dz)>=5
        p.fill(x,f-2,z,x,f,z,'minecraft:gray_concrete',o+'/deck')
        if h%1:
            state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if side else 'minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]';y=f+1
        else:state='projectseele:nerv_floor_panel' if side else 'minecraft:black_concrete';y=f
        p.put(x,y,z,state,o+'/paving')
        if x>=1224:p.match((x,y,z,x,y,z),'projectseele:nerv_floor_panel',state,o+'/yard_seam')
        p.fill(x,y+1,z,x,127,z,'minecraft:air',o+'/headroom')
    if h%1==0 and x%16<6:p.put(x,f,centre,'minecraft:white_concrete',o+'/marking')
    if water:
        bridge_columns+=1
        for dz in (-7,7):p.fill(x,math.ceil(h)+1,centre+dz,x,math.ceil(h)+1,centre+dz,'minecraft:gray_concrete',o+'/parapet')
        if x%20==0:
            for dz in (-5,5):p.fill(x-1,32,centre+dz-1,x+1,f-2,centre+dz+1,'minecraft:polished_andesite',o+'/bridge_pile')
    elif x%56==0:
        p.fill(x,f+1,centre+8,x,f+6,centre+8,'minecraft:gray_concrete',o+'/lamp_post');p.fill(x,f+7,centre+6,x,f+7,centre+8,'projectseele:nerv_strip_light',o+'/lamp')
path=[[444.5,81,304.5]]+[[x+.5,height(x)+1,float(curve(x))+.5] for x in range(456,1296,16)]+[[1296.5,69,432.5]]
cases=[dict(id='r07/connection/port_road',path=path),dict(id='r07/connection/port_road/return',path=path[::-1])]
p.meta.update(source='Five R07 exact saved-volume surveys; existing X444 Y80 Z304 street',bridge_columns=bridge_columns,walk_cases=cases)
p.apply('port_road');(OUT/'road_walk_cases.json').write_text(json.dumps(cases,indent=2));print('Connected port approach; bridged columns',bridge_columns,flush=True)
