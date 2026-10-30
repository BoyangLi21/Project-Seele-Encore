"""Fit the native ground cable railway into the two installed interchange levels."""
import argparse,json,shutil,math,heapq
from pathlib import Path
import numpy as np
import nbtlib
from PIL import Image,ImageDraw
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station,AIR,STONE,PAVE
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world
from plan_ashi_landscape_r54 import NATURAL


def author(a):
    if a.out.exists():raise ValueError('Use a fresh cable-railway candidate')
    (a.out/'source').mkdir(parents=True);(a.out/'delta').mkdir()
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    for file in(a.source/'source').glob('*.npz'):shutil.copy2(file,a.out/'source'/file.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    e=Editor(a.out);s=Station(e);samples=json.loads((a.native/'track_samples.json').read_text('utf8'));plan=json.loads((a.native.parent/'plan.json').read_text('utf8'))
    cells={};platforms=[];errors=[]
    with np.load(a.source/'measured.npz')as f:height=f['top'];x0,z0,x1,z1=f['bounds']
    for row in samples:
        if not row['id'].startswith('HC'):continue
        for x,y,z in row['points']:
            x,y,z=math.floor(x),math.floor(y),math.floor(z)
            for dx in(-1,0,1):
                for dz in(-1,0,1):cells[x+dx,z+dz]=min(cells.get((x+dx,z+dz),y),y)
        if row['kind']=='platform':platforms.append(row)
    with np.load(a.source.parent/'main-district-candidate/district-surface.npz')as f:
        bounds=f['bounds'];walk=f['walk'];oldtarget=f['target']
    ox,oz,X,Z=bounds;tunnelim=Image.new('L',(int(x1-x0+1),int(z1-z0+1)))
    streets=json.loads((a.source.parent/'main-district-candidate/district-plan.json').read_text('utf8'))['streets']
    for street in streets:
        if street['tunnel']:ImageDraw.Draw(tunnelim).line([(round(x-x0),round(z-z0))for x,z in street['points']],fill=1,width=15)
    tunnel=np.asarray(tunnelim,bool);roadfloor={};roadkind={}
    paving=('minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone')
    for x in range(int(x0),int(x1)+1):
        for z in range(int(z0),int(z1)+1):
            if not(walk[z-oz,x-ox]or tunnel[z-z0,x-x0]):continue
            h=int(oldtarget[z-oz,x-ox]);choices=[]
            for y in range(max(-127,h-14),min(318,h+2)+1):
                state=e.state(x,y,z,True).split('[')[0]
                if state in paving:choices.append((y,state))
            if choices:
                y,state=min(choices,key=lambda item:abs(item[0]-h));roadfloor[x,z]=y;roadkind[x,z]=state
    raised={p:2*y for p,y in roadfloor.items()};queue=[]
    for p,y in cells.items():
        x,z=p;station=(628<=x<=681 and 744<=z<=800)or(908<=x<=943 and 609<=z<=680)
        if not station and p in raised and roadfloor[p]<=y+4 and roadfloor[p]>=y-2:
            raised[p]=max(raised[p],2*(y+6));heapq.heappush(queue,(-raised[p],p))
    while queue:
        neg,p=heapq.heappop(queue);h=-neg
        if raised[p]!=h:continue
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz
            if q in raised and raised[q]<h-1:raised[q]=h-1;heapq.heappush(queue,(-raised[q],q))
    for(x,z),y in cells.items():
        ground=int(height[z-z0,x-x0]);station=(628<=x<=681 and 744<=z<=800)or(908<=x<=943 and 609<=z<=680)
        for Y in range(y-1,y+5):
            state=e.state(x,Y,z,True).split('[')[0]
            public=(x,z)in roadfloor and abs(roadfloor[x,z]-Y)<=2 and state in(*paving,STONE)
            if not station and state not in NATURAL and not public:errors.append(['retained-object',x,Y,z,state])
        if ground<y-2:e.fill(x,ground,z,x,y-2,z,STONE)
        e.put(x,y-1,z,'minecraft:gravel');e.fill(x,y,z,x,y+4,z,AIR)
        if not station and ground>y+5:e.put(x,y+5,z,STONE)
    # Grade a public road bridge above each measured cable crossing. No road
    # drops into the railway cutting, and no native transport identity changes.
    roadchanges=[]
    for(x,z),top2 in raised.items():
        old=roadfloor[x,z]
        if top2<=2*old:continue
        y=top2//2;material=roadkind[x,z]
        e.fill(x,old,z,x,y+4,z,AIR)
        if(x,z)not in cells:e.fill(x,old-1,z,x,y-1,z,STONE)
        else:e.put(x,y-1,z,STONE)
        if top2%2:
            material=('minecraft:smooth_stone_slab'if material==PAVE else'projectseele:road_marking_slab'if material=='minecraft:white_concrete'else'projectseele:road_asphalt_slab')+'[type=bottom,waterlogged=false]'
        e.put(x,y,z,material);roadchanges.append([x,old,z,top2])
    for row in platforms:
        definition=next(r for r in plan['rails']if r['id']==row['id']);p,q=np.asarray(definition['from']),np.asarray(definition['to'])
        v=q[[0,2]]-p[[0,2]];v=v/np.linalg.norm(v);n=np.array([-v[1],v[0]])
        path=[]
        for t in np.linspace(0,1,round(np.linalg.norm(q-p))+1):
            xyz=p+(q-p)*t;x,z=np.rint(xyz[[0,2]]+n*4).astype(int);y=round(float(xyz[1]));path.append([int(x),y,int(z)])
        s.path(path,3)
        middle=path[len(path)//2];s.sign(middle[0]+3,middle[1]+3,middle[2],['登山缆车','强罗 ↔ 早云山'])
    # Join the exposed public side to the installed station circulation.
    routes=[((663,104,768),(666,104,774)),((666,104,774),(660,104,775)),
            ((915,55,658),(921,55,661)),((921,55,661),(934,55,665))]
    for p,q in routes:
        steps=max(abs(p[0]-q[0]),abs(p[2]-q[2]));s.path([list(map(int,v))for v in np.rint(np.linspace(p,q,steps+1))],3)
    # Crossings remain walkable at the rail head; no runtime stop/check is added.
    for(x,z),y in cells.items():
        if e.state(x,y,z)!=AIR:e.put(x,y,z,AIR)
    with stopped_world(world):
        for p,tag in iter_block_entities(world,'projectseele:geofront',(int(x0),-128,int(z0)),(int(x1),319,int(z1))):
            if e.state(*p)!=e.state(*p,original=True):errors.append(['original-device',p])
    for row in s.devices:
        tag=row['After'];p=tuple(int(tag[k])for k in('x','y','z'))
        if 'sign'not in e.state(*p):errors.append(['overwritten-sign',p])
    regions=e.save();nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](s.devices)}).save(a.out/'block-entities.dat',gzipped=True)
    manifest=dict(world=str(world),bounds_xz=capture['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[],native_receipt=str(a.native/'native_transit_receipt.json'),road_overpass_cells=len(roadchanges))
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,track_columns=len(cells),public_platforms=2,visual_verified=False),ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(errors=errors[:15],cells=manifest['cells']),ensure_ascii=False),flush=True)
    if errors:raise ValueError('Cable railway meets an original object')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('source','out','native'):p.add_argument('--'+name,type=Path,required=True)
    author(p.parse_args())
