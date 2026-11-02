"""Compile reviewed street alignments, daylight earthworks and finite retirements.

The design file supplies surveyed ports and explicit reconstruction volumes.
This compiler never interprets an arbitrary air cell as construction authority.
It prepares reversible arrays only; the shared installer owns cold publication.
"""
import argparse
import json
import os
import shutil
import heapq
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt

from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_earthworks import ground
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

EMPTY = AIR | PLANTS | {'minecraft:light'}


def fit_ports(walk, desired, existing_walk, existing_grade):
    """Fit half-block steps to every retained interface across the full width."""
    lower=np.full(walk.shape,-30000,np.int32);upper=-lower
    for dz,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        outside=np.roll(existing_walk&~walk,(-dz,-dx),(0,1))
        values=np.roll(existing_grade,(-dz,-dx),(0,1)).astype(np.int32)
        boundary=walk&outside
        lower[boundary]=np.maximum(lower[boundary],values[boundary]-1)
        upper[boundary]=np.minimum(upper[boundary],values[boundary]+1)

    def envelope(values):
        values=values.copy();queue=[(int(values[z,x]),int(z),int(x))for z,x in np.argwhere(walk& (values<30000))]
        heapq.heapify(queue)
        while queue:
            value,z,x=heapq.heappop(queue)
            if value!=values[z,x]:continue
            for Z,X in ((z+1,x),(z-1,x),(z,x+1),(z,x-1)):
                if 0<=Z<walk.shape[0] and 0<=X<walk.shape[1] and walk[Z,X] and values[Z,X]>value+1:
                    values[Z,X]=value+1;heapq.heappush(queue,(value+1,Z,X))
        return values

    lower=-envelope(-lower);upper=envelope(upper)
    if np.any(walk&(lower>upper)):
        raise ValueError('Retained interfaces need a wider or longer approach')
    result=desired.copy()
    # A minimum-distance envelope removes raster jumps while respecting the
    # propagated lower bound; it does not relax any retained interface.
    fitted=envelope(np.clip(desired,lower,upper))
    result[walk]=fitted[walk]
    return result


def alignment(row):
    points=np.asarray(row['points'],float)
    distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points[:,[0,2]],axis=0),axis=1))]
    if np.any(np.diff(distance)<=0): raise ValueError('Repeated horizontal design port')
    along=np.linspace(0,distance[-1],int(np.ceil(distance[-1]*4))+1)
    curve=np.column_stack([PchipInterpolator(distance,points[:,i])(along)for i in range(3)])
    ds=np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1)
    slope=abs(np.diff(curve[:,1]))/ds
    if slope.max()>row.get('maximum_grade',.25)+1e-6:
        raise ValueError((row['id'],'alignment grade exceeds design',float(slope.max())))
    return curve,along


def retain_bearings(target,old,walk,bearings,bounds,slope):
    """Carry retained foundation grades out into the daylight slope."""
    x,z,X,Z=bounds;lower=np.full(old.shape,-30000.,float);seed=np.zeros(old.shape,bool)
    for a,b,c,A,B,C in bearings:
        l,t,r,s=max(x,a),max(z,c),min(X,A),min(Z,C)
        if l>r or t>s:continue
        area=np.s_[t-z:s-z+1,l-x:r-x+1]
        # Preserve the measured supporting ground, never infer a new room
        # from an air column below a platform or roof.
        if not np.any(target[area]!=old[area]):continue
        seed[area]|=old[area]>-129
    lower[seed]=old[seed]
    queue=[(-float(lower[iz,ix]),int(iz),int(ix))for iz,ix in np.argwhere(seed)]
    heapq.heapify(queue)
    steps=[(dz,dx,slope*np.hypot(dz,dx))for dz in (-1,0,1)for dx in (-1,0,1)if dz or dx]
    while queue:
        value,iz,ix=heapq.heappop(queue);value=-value
        if value!=lower[iz,ix]:continue
        for dz,dx,cost in steps:
            j,i=iz+dz,ix+dx
            if 0<=j<old.shape[0] and 0<=i<old.shape[1] and lower[j,i]<value-cost:
                lower[j,i]=value-cost;heapq.heappush(queue,(-lower[j,i],j,i))
    upper=np.full(old.shape,30000.,float);upper[seed]=old[seed]
    queue=[(float(upper[iz,ix]),int(iz),int(ix))for iz,ix in np.argwhere(seed)];heapq.heapify(queue)
    while queue:
        value,iz,ix=heapq.heappop(queue)
        if value!=upper[iz,ix]:continue
        for dz,dx,cost in steps:
            j,i=iz+dz,ix+dx
            if 0<=j<old.shape[0] and 0<=i<old.shape[1] and upper[j,i]>value+cost:
                upper[j,i]=value+cost;heapq.heappush(queue,(upper[j,i],j,i))
    low,high=np.rint(lower).astype(np.int16),np.rint(upper).astype(np.int16)
    if np.any(low>high):raise ValueError('Retained foundation grades require explicit retaining walls')
    fitted=np.clip(target,low,high)
    if np.any(walk&(fitted!=target)):
        iz,ix=np.argwhere(walk&(fitted!=target))[0]
        raise ValueError(('Road and retained building bearings require a different grade or retaining structure',
                          int(ix+x),int(iz+z),int(target[iz,ix]),int(fitted[iz,ix])))
    return fitted


def compile_street(e,row,protected,rail,existing=None,bearings=()):
    bx,bz,bX,bZ=map(int,row['bounds']); zz,xx=np.mgrid[bz:bZ+1,bx:bX+1]
    curve,along=alignment(row)
    distance,nearest=cKDTree(curve[:,[0,2]]).query(np.column_stack((xx.ravel(),zz.ravel())))
    distance=distance.reshape(xx.shape); nearest=nearest.reshape(xx.shape)
    radius=row['carriage_width']/2
    carriage=(distance<=radius) & (not row.get('pedestrian',False))
    walk=distance<=radius+row.get('sidewalk_width',2)
    grade2=np.rint(2*(curve[nearest,1]-1)).astype(np.int16)
    retired_walk=np.zeros(walk.shape,bool)
    complete_retirements=row.get('retire_complete_volumes',[])
    if existing is not None:
        x0,z0,_,_=existing['bounds'];area=np.s_[bz-z0:bZ-z0+1,bx-x0:bX-x0+1]
        base_walk=existing['walk'][area].copy();base_grade=existing['grade2'][area]
        base_floor,_=road_blocks(base_grade)
        for a,b,c,A,B,C in complete_retirements:
            retired_walk|=base_walk&(xx>=a)&(xx<=A)&(zz>=c)&(zz<=C)&(base_floor>=b)&(base_floor<=B)
        base_walk[retired_walk]=False
        station=along[nearest].copy()
        for end,other in ((0,1),(-1,-2)):
            tangent=curve[end,[0,2]]-curve[other,[0,2]];tangent/=np.linalg.norm(tangent)
            projection=(xx-curve[end,0])*tangent[0]+(zz-curve[end,2])*tangent[1]
            at_end=(nearest==(0 if end==0 else len(curve)-1))&(projection>0)
            station[at_end]+=projection[at_end]*(1 if end else -1)
        scope=(station>=-5)&(station<=along[-1]+8)&(distance<=radius+row.get('sidewalk_width',2)+4)
        # Regrade the existing FULL sidewalk width together with the road;
        # leaving a one-column strip at its former height creates a new kerb wall.
        if row.get('include_existing_walk',True):walk|=scope&base_walk
        if not row.get('pedestrian',False) and row.get('include_existing_walk',True):
            carriage|=scope&existing['road'][area]&base_walk
        blend=np.clip((station-along[-1]+15)/20,0,1)
        blend=blend*blend*(3-2*blend)
        use=walk&base_walk
        grade2[use]=np.rint(grade2[use]*(1-blend[use])+base_grade[use]*blend[use]).astype(np.int16)
        grade2=fit_ports(walk,grade2,base_walk,base_grade)
    old=ground(e,row['bounds']); known=old>-129
    if np.any(walk&~known): raise ValueError((row['id'],'unknown ground under commissioned corridor'))
    hy,slab=road_blocks(grade2)
    shoulder_distance,shoulder_nearest=distance_transform_edt(~walk,return_indices=True)
    # Half-slab ramps have integer subbase steps. Fit the daylight slope from
    # the nearest full-width edge rather than treating those discrete steps as
    # mutually contradictory continuous terrain pins.
    edge_base=(hy-1)[tuple(shoulder_nearest)]
    allowance=shoulder_distance*row.get('earth_slope',.5)
    target=np.rint(np.clip(old,edge_base-allowance,edge_base+allowance)).astype(np.int16)
    target=retain_bearings(target,old,walk,bearings,row['bounds'],row.get('earth_slope',.5))
    target[~known]=old[~known]
    if existing is not None:
        retained=base_walk&~walk
        target[retained]=old[retained]
    active=known&(target!=old)
    if any(np.any(edge)for edge in(active[0],active[-1],active[:,0],active[:,-1])):
        raise ValueError((row['id'],'earthworks do not meet untouched ground before design boundary'))
    if int(abs(target-old)[active].max(initial=0))>row.get('maximum_earthwork',12):
        raise ValueError((row['id'],'requires a bridge/tunnel or a longer approach',int(abs(target-old)[active].max())))
    local_boxes=[b for b in protected if b[0]<=bX and b[3]>=bx and b[2]<=bZ and b[5]>=bz]
    local_rail=rail[(rail[:,0]>=bx-5)&(rail[:,0]<=bX+5)&(rail[:,2]>=bz-5)&(rail[:,2]<=bZ+5)]
    railtree=cKDTree(local_rail[:,[0,2]])if len(local_rail)else None
    writes={}; blockers=[]; counts=Counter(); retired=row.get('retire_volumes',[])+complete_retirements
    auxiliary_points={tuple(r['pos']):r['state'] for r in row.get('retire_auxiliary_points',[])}
    for pos,expected in auxiliary_points.items():
        if not (bx<=pos[0]<=bX and bz<=pos[2]<=bZ) or e.state(*pos)!=expected:
            raise ValueError(('Changed explicitly retired remnant',pos,expected))

    def auxiliary_at(x,y,z):
        result=set(row.get('retire_auxiliary_materials',[])) if any(
            a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in retired) else set()
        if (x,y,z) in auxiliary_points:result.add(auxiliary_points[x,y,z].split('[')[0])
        return result

    def protected_at(x,y,z):
        if any(a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in local_boxes):return True
        if railtree:
            ids=railtree.query_ball_point((x,z),4)
            if any(local_rail[i,1]-3<=y<=local_rail[i,1]+8 for i in ids):return True
        return False

    def put(x,y,z,state,purpose,allowed):
        oldstate=e.state(x,y,z); bare=oldstate.split('[')[0]
        if writes.get((x,y,z),oldstate)==state:return
        if protected_at(x,y,z):
            blockers.append([x,y,z,'retained finite object',oldstate,purpose]);return
        if bare not in allowed:
            blockers.append([x,y,z,'unowned material',oldstate,purpose]);return
        prior=writes.get((x,y,z))
        # Stages are explicit: retirement -> earthworks -> roadway. Later
        # stages refine this object's own plan, never another street's plan.
        writes[x,y,z]=state
        counts[purpose]+=int(prior!=state)

    for a,b,c,A,B,C in retired:
        if a<bx or A>bX or c<bz or C>bZ:raise ValueError('Retirement outside design bounds')
        for x in range(a,A+1):
            for z in range(c,C+1):
                if row.get('retire_only_within_walk',True) and [a,b,c,A,B,C] not in complete_retirements and not walk[z-bz,x-bx]:continue
                for y in range(b,B+1):
                    state=e.state(x,y,z).split('[')[0]
                    if state in PAVEMENT | set(row.get('retire_auxiliary_materials',[])):
                        put(x,y,z,'minecraft:air','superseded roadway',PAVEMENT | set(row.get('retire_auxiliary_materials',[])))
    for pos,expected in auxiliary_points.items():
        put(*pos,'minecraft:air','explicit buried remnant',{expected.split('[')[0]})
    for iz,ix in np.argwhere(active|walk):
        x,z=int(xx[iz,ix]),int(zz[iz,ix]);before=int(old[iz,ix]);after=int(target[iz,ix])
        if active[iz,ix]:
            for y in range(min(before,after)-2,max(before,after)+1):
                state=e.state(x,y,z).split('[')[0]
                if y>after:
                    if state in SOIL|PLANTS:put(x,y,z,'minecraft:air','daylight cut',SOIL|PLANTS)
                elif state in SOIL|PLANTS|AIR|auxiliary_at(x,y,z) or (state in PAVEMENT and
                        (walk[iz,ix] or not row.get('retire_only_within_walk',True) or any(
                            a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in complete_retirements)) and any(
                        a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in retired)):
                    replacement=('minecraft:stone' if y<after-2 or walk[iz,ix] else
                                 'minecraft:grass_block[snowy=false]' if y==after else 'minecraft:dirt')
                    put(x,y,z,replacement,'supported embankment',SOIL|PLANTS|AIR|PAVEMENT|auxiliary_at(x,y,z))
        if not walk[iz,ix]:continue
        floor=int(hy[iz,ix])
        # Full slab base and five blocks of vehicle space. The declared
        # retirement volume is the only permission to remove an old road layer.
        allowed=SOIL|EMPTY|PAVEMENT
        for y in range(floor-1,floor+row.get('clearance',5)+1):
            owned_aux=auxiliary_at(x,y,z)
            if y>floor:
                material=e.state(x,y,z).split('[')[0]
                if material in PAVEMENT and not any(a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in retired):
                    blockers.append([x,y,z,'another pavement layer requires explicit ownership',e.state(x,y,z)]);continue
                put(x,y,z,'minecraft:air','full-width clearance',allowed|owned_aux)
            elif y<floor:put(x,y,z,'minecraft:stone','continuous subbase',allowed|owned_aux)
            else:
                marking=carriage[iz,ix] and distance[iz,ix]<.55 and int(along[nearest[iz,ix]]//5)%2==0
                if slab[iz,ix]:
                    material=('projectseele:road_marking_slab'if marking else
                              'projectseele:road_asphalt_slab'if carriage[iz,ix]else'minecraft:smooth_stone_slab')
                    material+='[type=bottom,waterlogged=false]'
                else:material='minecraft:white_concrete'if marking else'minecraft:black_concrete'if carriage[iz,ix]else'minecraft:smooth_stone'
                put(x,y,z,material,'road and sidewalk',allowed|owned_aux)
    # Devices are not inferred from materials: their exact captured locations
    # become one-cell protected volumes in the caller.
    if blockers:
        return dict(id=row['id'],status='blocked',blockers=blockers,planned_cells=len(writes)),None
    # Verify finite support and physical clearance in the composed volume.
    def state(x,y,z):return writes.get((x,y,z),e.state(x,y,z)).split('[')[0]
    errors=[]
    for iz,ix in np.argwhere(walk):
        x,z,y=int(xx[iz,ix]),int(zz[iz,ix]),int(hy[iz,ix])
        if state(x,y,z)not in PAVEMENT:errors.append([x,y,z,'floor'])
        if state(x,y-1,z)in EMPTY:errors.append([x,y-1,z,'unsupported deck'])
        if any(state(x,Y,z)in EMPTY for Y in range(min(int(old[iz,ix]),y)-1,y)):
            errors.append([x,y,z,'gap below subbase'])
        if any(state(x,Y,z)not in EMPTY for Y in range(y+1,y+row.get('clearance',5)+1)):
            errors.append([x,y,z,'clearance'])
    if errors:raise ValueError((row['id'],errors[:10]))
    return (dict(id=row['id'],status='prepared',changed_cells=len(writes),walk_columns=int(walk.sum()),
                counts=dict(counts),ports=row['points'][::len(row['points'])-1],bounds=row['bounds']),
           (writes,dict(bounds=row['bounds'],old=old,target=target,active=active,
                        walk=walk,road=carriage,grade2=grade2,retired_walk=retired_walk,clearance=row.get('clearance',5))))


def publish_plan(candidate,base):
    """Make later street work use the same grades as the actual authored delta."""
    out=candidate/'plan';out.mkdir(exist_ok=True)
    with np.load(base/'network.npz')as f:d={k:f[k]for k in f.files}
    x0,z0,_,_=map(int,d['bounds']);e=Editor(candidate);ids=[]
    for path in sorted((candidate/'earthworks').glob('*.npz')):
        with np.load(path)as f:q={k:f[k]for k in f.files}
        x,z,X,Z=map(int,q['bounds']);area=np.s_[z-z0:Z-z0+1,x-x0:X-x0+1];mask=q['walk']
        for key in ('walk','road','marking'):
            d[key][area][q.get('retired_walk',np.zeros(mask.shape,bool))]=False
        d['walk'][area]|=mask
        for key in ('road','grade2'):d[key][area][mask]=q[key][mask]
        d['ground'][area][q['active']]=q['target'][q['active']]
        for iz,ix in np.argwhere(mask):
            y,_=road_blocks(q['grade2'][iz,ix]);state=e.state(x+int(ix),int(y),z+int(iz))
            d['marking'][z-z0+iz,x-x0+ix]='road_marking_slab'in state or state=='minecraft:white_concrete'
        ids.append(path.stem);e.regions.clear()
    np.savez_compressed(out/'network.npz',**d)
    for path in base.glob('*.json'):shutil.copy2(path,out/path.name)
    (out/'authored-corridors.json').write_text(json.dumps(dict(ids=ids,source=str(base),
        candidate=str(candidate),grade_authority='actual compiled full-width corridors'),indent=2),'utf8')
    return out


def main(a):
    from map_pipeline.launch_protection import load,check_candidate
    design=json.loads(a.design.read_text('utf8'))
    launch_guard=load(Path(design['world']))
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(a.design,a.out/'authored-design.json')
    for sub in ('source','delta','earthworks'):(a.out/sub).mkdir()
    for p in(a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    bearings=[r['occupied_bounds']for r in json.loads((a.plan/'catalog.json').read_text('utf8'))]
    boxes=[[x,y-3,z,X,Y,Z]for x,y,z,X,Y,Z in bearings]
    boxes+=json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    boxes+=design.get('preserved_volumes',[])
    for p in a.measure.glob('*.json'):
        for r in json.loads(p.read_text('utf8')).get('devices',[]):boxes.append([*r['pos'],*r['pos']])
    rail=np.asarray([p for row in json.loads((a.plan/'native-curves.json').read_text('utf8'))['trains']for p in row['points']],float).reshape(-1,3)
    e=Editor(a.out); rows=[]; owned={}
    with np.load(a.plan/'network.npz')as f:
        existing={k:f[k]for k in ('bounds','walk','road','grade2')}
    for row in design['streets']:
        report,result=compile_street(e,row,boxes,rail,existing,bearings);rows.append(report)
        if result:
            writes,field=result
            for pos,state in writes.items():
                if pos in owned and owned[pos]!=state and not (
                        row.get('join_previous_earthworks',False) and owned[pos].split('[')[0] in SOIL|AIR):
                    raise ValueError(('Conflicting street designs',pos))
                owned[pos]=state;e.put(*pos,state)
            np.savez_compressed(a.out/'earthworks'/(row['id']+'.npz'),**field)
            e.save()
            x,z,X,Z=map(int,field['bounds']);x0,z0,_,_=map(int,existing['bounds'])
            area=np.s_[z-z0:Z-z0+1,x-x0:X-x0+1]
            for key in ('walk','road'):existing[key][area][field['retired_walk']]=False
            existing['walk'][area]|=field['walk']
            for key in ('road','grade2'):existing[key][area][field['walk']]=field[key][field['walk']]
        e.regions.clear();print(row['id'],report['status'],report.get('changed_cells',0),'blockers',len(report.get('blockers',[])),flush=True)
    patches=e.save()
    (a.out/'manifest.json').write_text(json.dumps(dict(world=design['world'],regions=patches,
        cells=sum(p['cells']for p in patches),streets=rows,world_written=False),indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=[['unresolved street',r['id']]for r in rows if r['status']!='prepared'],
        prepared_streets=[r['id']for r in rows if r['status']=='prepared'],
        unresolved_streets=[r for r in rows if r['status']!='prepared'],visual_verified=False),indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(launch_guard,a.out),indent=2),'utf8')
    if patches:publish_plan(a.out,a.plan)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('source','plan','measure','design','out'):p.add_argument('--'+k,type=Path,required=True)
    main(p.parse_args())
