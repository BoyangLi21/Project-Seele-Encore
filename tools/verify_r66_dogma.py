"""Read native post-build blocks: full swept standing chassis and the walk from the B lift."""
import argparse
from collections import Counter,deque
import json
import math
from pathlib import Path

import numpy as np

from map_buildings.mca import World
from r66_dogma_geometry import AIR, LOW, door_block
from write_deep_cells import REGION


def chassis_clear(name):
    return name in (AIR,'minecraft:cave_air','minecraft:void_air') or name.startswith(
        ('projectseele:lcl[','minecraft:light[','minecraft:water'))


class Occupancy:
    def __init__(self,world,open_door):
        self.world=world
        self.cache={}
        self.open_door=open_door

    def solid(self,cx,cy,cz):
        key=cx,cy,cz
        if key not in self.cache:
            chunk=self.world.chunk(cx,cz)
            if chunk is None: raise ValueError(f'Ungenerated chunk {cx} {cz}')
            section=chunk[0].get(cy)
            if section is None:
                array=np.zeros((16,16,16),dtype=bool)
            else:
                ids,pal=section
                array=np.array([not chassis_clear(s) for s in pal])[ids].reshape((16,16,16))
            if self.open_door and cx in (1,2) and cz==16 and -79<=cy<=-76:
                for y in range(max(LOW+1,cy*16),min(-1202,cy*16+15)+1):
                    for x in range(max(18,cx*16),min(42,cx*16+15)+1):
                        if y!=-1231 or x>20:
                            array[y&15,2:5,x&15]=False
            self.cache[key]=array
        return self.cache[key]

    def hits(self,x0,y0,z0,x1,y1,z1):
        for cx in range(x0>>4,(x1>>4)+1):
            for cz in range(z0>>4,(z1>>4)+1):
                for cy in range(y0>>4,(y1>>4)+1):
                    x,y,z=cx*16,cy*16,cz*16
                    xa,ya,za=max(0,x0-x),max(0,y0-y),max(0,z0-z)
                    vol=self.solid(cx,cy,cz)[ya:min(16,y1-y+1),za:min(16,z1-z+1),xa:min(16,x1-x+1)]
                    if np.any(vol):
                        iy,iz,ix=np.argwhere(vol)[0]
                        return x+xa+int(ix),y+ya+int(iy),z+za+int(iz)
        return None


def connect(a,b):
    steps=max(abs(b[i]-a[i]) for i in range(3))
    return [tuple(round(a[i]+(b[i]-a[i])*t/max(steps,1)) for i in range(3)) for t in range(steps+1)]


def check_walk(w,start,targets,open_door=False):
    def open_at(x,y,z):
        if open_door and 16<=x<=44 and LOW<y<=-1202 and 258<=z<=260:
            block='projectseele:nerv_floor_panel' if y==-1231 and 18<=x<=20 else door_block(x,y,z,25)
        else:
            block=w.get(x,y,z) or ''
        return chassis_clear(block) or 'wall_sign' in block or '_wall_torch' in block
    queue=deque([start]);seen={start}
    while queue:
        x,y,z=queue.popleft()
        for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):
            for dy in (0,-1,1):
                q=(x+dx,y+dy,z+dz)
                if q in seen or not (-88<=q[0]<=47 and -1261<=q[1]<=-1227 and 93<=q[2]<=317): continue
                a,b,c=q
                if open_at(a,b,c) and open_at(a,b+1,c) and not open_at(a,b-1,c):
                    seen.add(q);queue.append(q)
                    break
    return {k:list(v) if v in seen else None for k,v in targets.items()}


def inspect(world):
    w=World(world/REGION)
    opening=sum(w.get(x,-1202,258)==AIR for x in range(18,43))
    solid=Occupancy(w,opening<25)
    routes={}
    for i,x in enumerate((72,30,-12)):
        routes[f'original_geofront_outlet_{i}']=[(x,-466,124),(x+13,-466,124),(x+13,-466,164),(139,-466,164),
                                                (139,-466,175),(144,-466,175),(144,-466,176),(145,-466,176),
                                                (145,-466,177),(147,-466,177),(147,-466,178),(160,-466,178),(160,-466,187),
                                                (141,-466,187),(141,-1051,187),(133,-1051,187),
                                                (133,-1051,219),(154,-1051,219),(154,-1051,242),(136,-1051,242)]
    routes['lower_full_chassis']=[(136,-1051,242),(136,-1264,242),(30,-1264,242),(30,-1264,260),
                                 (30,-1264,265),(30,-1266,270),(30,-1266,333)]
    routes['climb_out_and_back_at_upper_lip']=[(141,-475,188),(141,-466,188),(160,-466,188)]
    routes['climb_out_and_back_at_lower_lip']=[(136,-1062,242),(136,-1051,242),(155,-1051,242),(155,-1051,218),
                                              (91,-1051,218),(91,-1051,242),(72,-1051,242)]
    # Three original wet-cage doors discharge into this common hall. The still
    # closed wet-door barriers and cranes are owned by the live transport system.
    for i,x in enumerate((72,30,-12)):
        routes[f'released_hangar_hall_{i}']=[(x,-1067,289),(x,-1063,263),(x,-1051,242),(91,-1051,242),
                                            (91,-1051,218),(155,-1051,218),(155,-1051,242)]
    result={}
    for name,path in routes.items():
        pts=[]
        for a,b in zip(path,path[1:]): pts+=connect(a,b)
        errs=Counter();first=[];unsupported=[]
        previous=None
        for x,y,z in dict.fromkeys(pts):
            # Recover the actual foot height where the chassis follows the shallow
            # hangar apron or the submerged shelf. Vanilla can stand with part of
            # its bounding box on the higher tread when the rest overhangs a step.
            on_apron=name.startswith('released_hangar') and x<100
            on_shelf=name=='lower_full_chassis' and z>=260
            if on_apron or on_shelf:
                heights=range(-1070,-1039) if on_apron else range(-1296,-1261)
                choices=[h for h in heights if not solid.hits(x-8,h,z-8,x+8,h+59,z+8)
                         and solid.hits(x-8,h-1,z-8,x+8,h-1,z+8)]
                if choices:
                    y=min(choices,key=lambda h:abs(h-(previous if previous is not None else y)))
                else:
                    unsupported.append([x,y,z])
                if previous is not None and abs(y-previous)>20: raise ValueError((name,previous,y))
            elif (name.startswith('released_hangar') or (name.startswith('original_geofront') and y==-466 and z!=187)) and not solid.hits(x-8,y-1,z-8,x+8,y-1,z+8):
                unsupported.append([x,y,z])
            previous=y
            hit=solid.hits(x-8,y,z-8,x+8,y+59,z+8)
            if hit:
                state=w.get(*hit);errs[state]+=1
                if len(first)<5:first.append([x,y,z,list(hit),state])
        result[name]={'centres':len(set(pts)),'blocked':sum(errs.values()),'states':dict(errs),'examples':first,
                      'unsupported_floor_samples':unsupported}
    # Read the actual upper and lower door drives, including the stationary pedestrian bridge.
    mismatch=[]
    for x in range(16,45):
        for y in range(LOW+1,-1201):
            for z in range(258,261):
                expected='projectseele:nerv_floor_panel' if y==-1231 and 18<=x<=20 else door_block(x,y,z,opening)
                if w.get(x,y,z)!=expected: mismatch.append((x,y,z,w.get(x,y,z),expected))
    points={'old_room':(-21,-1230,200),'graveyard':(-32,-1230,143),'dummy_core':(3,-1230,122),
            'western_door_bridge':(19,-1230,256),'lake_view':(18,-1230,279),'lower_lake_overlook':(10,-1255,311)}
    walk=check_walk(w,(-42,-1230,259),points)
    upon_open=walk if opening==25 else check_walk(w,(-42,-1230,259),points,True)
    outside=('old_room','graveyard','dummy_core','western_door_bridge')
    grips={}
    for name,face,foot,top,z0,z1 in [('lower',145,-1264,-1051,237,248),('upper',150,-1051,-466,184,192)]:
        contacts={(face,max(foot+4,min(y+30,top-2)),z) for y in range(foot,top+1) for z in range(z0,z1+1)}
        gaps=[pos for pos in sorted(contacts) if chassis_clear(w.get(*pos) or AIR)]
        grips[name]={'checked_contact_cells':len(contacts),'missing':len(gaps),'examples':gaps[:4]}
    return {'dimension':'projectseele:geofront','eva_full_box':[17,60,17],'door_saved_width':opening,
            'open_door_evaluation':'native open' if opening==25 else 'native leaves checked at saved width; full-open collision evaluated using the same leaf geometry',
            'door_discrepancies':len(mismatch),'door_examples':mismatch[:4],'sweeps':result,'wall_contacts':grips,
            'personnel_B_lift_walk_at_saved_width':walk,
            'personnel_B_lift_walk_after_full_open':upon_open,
            'personnel_full_open_evidence':'sampled native saved blocks' if opening==25 else 'evaluated animated door cells only; all surrounding terrain sampled from native save',
            'all_ok':not mismatch and all(not v['missing'] for v in grips.values()) and all(walk[k] for k in outside) and all(upon_open.values())
                     and all(not v['blocked'] and not v['unsupported_floor_samples'] for v in result.values())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();d=inspect(a.world);a.report.write_text(json.dumps(d,indent=2,ensure_ascii=False),'utf8')
    print(json.dumps({**d,'sweeps':{k:[v['blocked'],v['examples'][:1]] for k,v in d['sweeps'].items()}},ensure_ascii=False))
    raise SystemExit(0 if d['all_ok'] else 1)
