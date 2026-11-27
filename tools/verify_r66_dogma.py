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


def check_walk(w,start,targets,open_door=False,central_deck=False,
               bounds=(-88,94,93,390)):
    x0,x1,z0,z1 = bounds
    def open_at(x,y,z):
        if central_deck and open_door and 18<=x<=42 and 258<=z<=260 and -1230<=y<=-1202:
            return True
        if open_door and not central_deck and 16<=x<=44 and LOW<y<=-1202 and 258<=z<=260:
            block='projectseele:nerv_floor_panel' if y==-1231 and 18<=x<=20 else door_block(x,y,z,25)
        else:
            block=w.get(x,y,z) or ''
        return chassis_clear(block) or 'wall_sign' in block or '_wall_torch' in block or '_door[' in block or '_button[' in block or '_pressure_plate[' in block
    queue=deque([start]);seen={start};pending=set(targets.values())-{start}
    while queue and pending:
        x,y,z=queue.popleft()
        for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):
            for dy in (0,-1,1):
                q=(x+dx,y+dy,z+dz)
                if q in seen or not (x0<=q[0]<=x1 and -1261<=q[1]<=-1227 and z0<=q[2]<=z1): continue
                a,b,c=q
                if open_at(a,b,c) and open_at(a,b+1,c) and not open_at(a,b-1,c):
                    seen.add(q);queue.append(q);pending.discard(q)
                    break
    return {k:list(v) if v in seen else None for k,v in targets.items()}


def inspect(world):
    w=World(world/REGION)
    normal_walk = {}
    gallery_checks = {}
    manifest = world / 'r52/dogma_interlocks.nbt'
    if manifest.is_file():
        import nbtlib
        # Exercise the personnel deck and released chassis routes as separate configurations.
        # Mutate only the decoded in-memory sections of this survey reader.
        gate = nbtlib.load(manifest)
        palette = list(map(str, gate['Palette']))
        rows = gate['Cells'].reshape(-1, 5).tolist()
        def apply_gate(column):
            for row in rows:
                x, y, z = row[:3]
                ids, names = w.chunk(x >> 4, z >> 4)[0][y >> 4]
                material = palette[row[column]]
                if material not in names:
                    names.append(material)
                ids[(y & 15) * 256 + (z & 15) * 16 + (x & 15)] = names.index(material)
        apply_gate(3)
        # Keep the older geometry test available for worlds without the dogleg.
        front_arm = w.get(37,-1256,331) == "projectseele:nerv_floor_panel"
        revised = front_arm or w.get(16,-1256,340) == "projectseele:nerv_floor_panel"
        new_target = {"lower_dogleg_end": (37,-1255,331) if front_arm else (16,-1255,340)} if revised else {
            "inspection_bridge_end": (31,-1230,343)}
        if revised:
            west, east = -31, 91
            north, south = 270, 382
            corners = [(west,north),(west,south),(east,south),(east,north)]
            belts = [(-34,-28,268,386),(-32,93,381,387),
                     (89,94,268,386),(-32,93,262,273)]
            for (x,z), (X,Z), belt in zip(corners, corners[1:]+corners[:1], belts):
                gallery_checks[f"ring_{x}_{z}_to_{X}_{Z}"] = bool(check_walk(
                    w, (x,-1230,z), {"end":(X,-1230,Z)}, bounds=belt)["end"])
            def retired_span_clear():
                return all(chassis_clear(w.get(x,y,z)) for x in range(23,38)
                           for y in range(-1234,-1228) for z in range(288,345))
            def jamb_clear():
                iron = [(x,y,z) for x,z in ((8,268),(16,261)) for y in range(-1230,-1224)]
                return all(w.get(*p) != "minecraft:iron_block" for p in [*iron,(8,-1225,261)])
            gallery_checks["normal_centre_open"] = retired_span_clear()
            gallery_checks["normal_right_jamb_clear"] = jamb_clear()
            guard_posts = ((5,329),(11,321),(39,331),(30,329),(30,334)) if front_arm else ((5,330),(11,330),(18,340),(16,337),(16,342))
            gallery_checks["lower_turn_guard"] = all("nerv_edge_rail" in w.get(x,-1255,z)
                for x,z in guard_posts)
        normal_walk = check_walk(w, (-42,-1230,259), {
            'first_lab': (-23,-1230,197), 'tank_console': (-11,-1230,119),
            'graveyard': (-32,-1230,164), 'central_door': (31,-1230,257),
            **new_target
        }, open_door=True, central_deck=True)
        apply_gate(4)
        if revised:
            if front_arm:
                gallery_checks["arm_retracted"] = all(chassis_clear(w.get(x,y,z))
                    for x in range(20,40) for z in range(329,335) for y in range(-1257,-1254))
                gallery_checks["retracted_edge_guarded"] = all("nerv_edge_rail" in w.get(19,-1255,z)
                    for z in range(329,335))
            gallery_checks["emergency_centre_open"] = retired_span_clear()
            gallery_checks["emergency_right_jamb_clear"] = jamb_clear()
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
    if normal_walk:
        if gallery_checks:
            points["lower_dogleg_end"] = (17,-1255,331) if front_arm else (16,-1255,340)
        points.update(old_room=(-23,-1230,197), dummy_core=(-11,-1230,119))
    walk=check_walk(w,(-42,-1230,259),points)
    upon_open=walk if opening==25 else check_walk(w,(-42,-1230,259),points,True)
    outside=('old_room','graveyard','dummy_core','western_door_bridge')
    grips={}
    # Native Unit-01 standing east, measured from its actual Forge
    # server AABB during powered ascent. The width exceeds its registry width.
    pose=(-9.52686882019043,9.52686882019043,-7.943214416503906,9.91646194458008)
    for name,face,foot,top,z0,z1 in [('lower',145,-1264,-1051,240,244),('upper',150,-1051,-466,185,190)]:
        contacts={(face,max(foot+4,min(y+30,top-2)),z) for y in range(foot,top+1) for z in range(z0,z1+1)}
        gaps=[pos for pos in sorted(contacts) if chassis_clear(w.get(*pos) or AIR)]
        centre=face-1.5-pose[1]
        clashes=[]
        for z in np.arange(z0,z1+.01,.5):
            for x,y in [(centre,y) for y in range(foot,top+1)]+[(x,top) for x in np.arange(centre,face+10.01,.5)]:
                hit=solid.hits(math.floor(x+pose[0]),y,math.floor(z+pose[2]),
                               math.ceil(x+pose[1])-1,y+59,math.ceil(z+pose[3])-1)
                if hit:clashes.append([round(float(z),2),y,list(hit)])
        grips[name]={'checked_contact_cells':len(contacts),'missing':len(gaps),'examples':gaps[:4],
                     'observed_Unit01_pose_xz_offsets':list(pose),'aligned_x':centre,
                     'pose_collision_count':len(clashes),'pose_collision_examples':clashes[:3]}
    return {'dimension':'projectseele:geofront','eva_full_box':[17,60,17],'door_saved_width':opening,
            'open_door_evaluation':'native open' if opening==25 else 'native leaves checked at saved width; full-open collision evaluated using the same leaf geometry',
            'door_discrepancies':len(mismatch),'door_examples':mismatch[:4],'sweeps':result,'wall_contacts':grips,
            'personnel_B_lift_walk_at_saved_width':walk,
            'personnel_B_lift_walk_after_full_open':upon_open,
            'personnel_full_open_evidence':'sampled native saved blocks' if opening==25 else 'evaluated animated door cells only; all surrounding terrain sampled from native save',
            'normal_personnel_walk_after_door_access': normal_walk,
            'ring_and_central_span':gallery_checks,
            'all_ok':all(gallery_checks.values()) and all(normal_walk.values()) and not mismatch and all(not v['missing'] and not v['pose_collision_count'] for v in grips.values()) and all(walk[k] for k in outside) and all(upon_open.values())
                     and all(not v['blocked'] and not v['unsupported_floor_samples'] for v in result.values())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();d=inspect(a.world);a.report.write_text(json.dumps(d,indent=2,ensure_ascii=False),'utf8')
    print(json.dumps({**d,'sweeps':{k:[v['blocked'],v['examples'][:1]] for k,v in d['sweeps'].items()}},ensure_ascii=False))
    raise SystemExit(0 if d['all_ok'] else 1)
