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
from scipy.ndimage import distance_transform_edt,binary_dilation

from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_earthworks import ground
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

EMPTY = AIR | PLANTS | {'minecraft:light'}


def fit_ports(walk, desired, existing_walk, existing_grade, cross_sections=()):
    """Fit half-block steps to every retained interface across the full width."""
    lower=np.full(walk.shape,-30000,np.int32);upper=-lower
    for dz,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        outside=np.roll(existing_walk&~walk,(-dz,-dx),(0,1))
        values=np.roll(existing_grade,(-dz,-dx),(0,1)).astype(np.int32)
        boundary=walk&outside
        lower[boundary]=np.maximum(lower[boundary],values[boundary]-1)
        upper[boundary]=np.minimum(upper[boundary],values[boundary]+1)

    across={}
    for section in cross_sections:
        for point in section:
            across.setdefault(point,set()).update(q for q in section if q!=point)

    def envelope(values):
        values=values.copy();queue=[(int(values[z,x]),int(z),int(x))for z,x in np.argwhere(walk& (values<30000))]
        heapq.heapify(queue)
        while queue:
            value,z,x=heapq.heappop(queue)
            if value!=values[z,x]:continue
            for Z,X in ((z+1,x),(z-1,x),(z,x+1),(z,x-1),*across.get((z,x),())):
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


def retain_bearings(target,old,walk,bearings,bounds,slope,relative=False):
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
    lower[seed]=0 if relative else old[seed]
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
    upper=np.full(old.shape,30000.,float);upper[seed]=0 if relative else old[seed]
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
    fitted=np.clip(target-old,low,high)+old if relative else np.clip(target,low,high)
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
        sections=[]
        if not row.get('pedestrian',False):
            for i in range(1,len(curve)-1,4):
                tangent=curve[i+1,[0,2]]-curve[i-1,[0,2]];tangent/=np.linalg.norm(tangent)
                normal=np.array([-tangent[1],tangent[0]])
                q=np.rint(curve[i,[0,2]]+np.linspace(-radius+.5,radius-.5,int(row['carriage_width']))[:,None]*normal).astype(int)
                sections.append({(int(z-bz),int(x-bx))for x,z in q if walk[z-bz,x-bx]})
        grade2=fit_ports(walk,grade2,base_walk,base_grade,sections)
    old=ground(e,row['bounds']); known=old>-129
    if np.any(walk&~known): raise ValueError((row['id'],'unknown ground under commissioned corridor'))
    hy,slab=road_blocks(grade2)
    bridge=row.get('bridge',{})
    tunnel=row.get('tunnel',{})
    if bridge and tunnel:raise ValueError('One corridor cannot be both a bridge and a tunnel')
    span=np.zeros(walk.shape,bool)
    if bridge:
        s0,s1=map(float,bridge['along'])
        span=(along[nearest]>=s0)&(along[nearest]<=s1)&(distance<=bridge.get('terrain_span_halfwidth',radius+row.get('sidewalk_width',2)+2))
        if not np.any(walk&span) or np.any(span[[0,-1]]) or np.any(span[:,[0,-1]]):
            raise ValueError('Bridge span must be finite and interior')
    bore=np.zeros(walk.shape,bool)
    if tunnel:
        t0,t1=map(float,tunnel['along'])
        # A bored road does not publish its floor as the mountain surface.
        bore=(along[nearest]>=t0)&(along[nearest]<=t1)
        if not np.any(bore&walk):raise ValueError('Tunnel has no commissioned roadway')
        span|=bore
    shoulder_distance,shoulder_nearest=distance_transform_edt(~(walk&~span),return_indices=True)
    # Half-slab ramps have integer subbase steps. Fit the daylight slope from
    # the nearest full-width edge rather than treating those discrete steps as
    # mutually contradictory continuous terrain pins.
    edge_base=(hy-1)[tuple(shoulder_nearest)]
    allowance=shoulder_distance*row.get('earth_slope',.5)
    target=np.rint(np.clip(old,edge_base-allowance,edge_base+allowance)).astype(np.int16)
    incremental=row.get('incremental_earthworks',False)
    if incremental:
        delta=edge_base-old[tuple(shoulder_nearest)]
        target=np.rint(old+np.sign(delta)*np.maximum(0,abs(delta)-allowance)).astype(np.int16)
    target=retain_bearings(target,old,walk,bearings,row['bounds'],row.get('earth_slope',.5),incremental)
    # A bridge spans the measured terrain/rail void; its deck grade is never
    # published as a new soil column or turned into a solid embankment.
    target[span]=old[span]
    if tunnel:
        # The portal face is confined to the lined opening. Continue the
        # untouched hillside down outside it, rather than ending every cut at
        # the same transverse plane and leaving a wide rectangular cliff.
        portal_distance,portal_near=distance_transform_edt(~bore,return_indices=True)
        shoulder=np.rint(old[tuple(portal_near)]-portal_distance*row.get('earth_slope',.5)).astype(np.int16)
        outside=~walk&~bore
        target[outside]=np.maximum(target[outside],np.minimum(old,shoulder)[outside])
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
    sweep=np.asarray(bridge.get('train_boxes',[]),float).reshape(-1,6)
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

    def protected_at(x,y,z,retiring=False):
        if any(a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in local_boxes):return True
        if len(sweep) and railtree:
            ids=railtree.query_ball_point((x+.5,z+.5),2.5)
            if any(local_rail[i,1]-3<=y+1 and y<local_rail[i,1]+.01 for i in ids):return True
        if len(sweep) and not retiring:
            from map_pipeline.train_clearance import intersects
            if intersects(sweep,x,y,z):return True
        elif not len(sweep) and railtree:
            ids=railtree.query_ball_point((x,z),4)
            if any(local_rail[i,1]-3<=y<=local_rail[i,1]+8 for i in ids):return True
        return False

    def put(x,y,z,state,purpose,allowed):
        oldstate=e.state(x,y,z); bare=oldstate.split('[')[0]
        if writes.get((x,y,z),oldstate)==state:return
        if protected_at(x,y,z,purpose=='superseded roadway' and row.get('retire_planned_surface_only',False)):
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
                    keep=next((p for p in row.get('retire_keep_points',[])if p['pos']==[x,y,z]),None)
                    if keep:
                        if e.state(x,y,z)!=keep['state']:raise ValueError('Retained underlying support changed')
                        continue
                    if row.get('retire_planned_surface_only',False):
                        if existing is None:raise ValueError('Planned surface retirement needs its original grade')
                        ix,iz=x-bx,z-bz
                        if not (existing['road'][area][iz,ix] or existing['walk'][area][iz,ix]) or y!=int(base_floor[iz,ix]):continue
                    materials=set(row.get('retire_materials',PAVEMENT)) | set(row.get('retire_auxiliary_materials',[]))
                    if state in materials:
                        put(x,y,z,'minecraft:air','superseded roadway',materials)
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
        if bridge and walk[iz,ix] and not span[iz,ix] and min(abs(along[nearest[iz,ix]]-s0),abs(along[nearest[iz,ix]]-s1))<=2:
            for y in range(min(before,after)-1,int(hy[iz,ix])):
                put(x,y,z,'minecraft:stone_bricks','bridge abutment',SOIL|EMPTY|PAVEMENT)
        if not walk[iz,ix]:continue
        floor=int(hy[iz,ix])
        # Full slab base and five blocks of vehicle space. The declared
        # retirement volume is the only permission to remove an old road layer.
        allowed=SOIL|EMPTY|PAVEMENT
        depth=int(bridge.get('deck_depth',2)) if bridge and span[iz,ix] else 1
        for y in range(floor-depth,floor+row.get('clearance',5)+1):
            owned_aux=auxiliary_at(x,y,z)
            if y>floor:
                material=e.state(x,y,z).split('[')[0]
                if material in PAVEMENT and not any(a<=x<=A and b<=y<=B and c<=z<=C for a,b,c,A,B,C in retired):
                    blockers.append([x,y,z,'another pavement layer requires explicit ownership',e.state(x,y,z)]);continue
                put(x,y,z,'minecraft:air','full-width clearance',allowed|owned_aux)
            elif y<floor:put(x,y,z,'minecraft:stone_bricks' if bridge and span[iz,ix] else 'minecraft:stone','continuous subbase',allowed|owned_aux)
            else:
                marking=carriage[iz,ix] and distance[iz,ix]<.55 and int(along[nearest[iz,ix]]//5)%2==0
                if slab[iz,ix]:
                    material=('projectseele:road_marking_slab'if marking else
                              'projectseele:road_asphalt_slab'if carriage[iz,ix]else'minecraft:smooth_stone_slab')
                    material+='[type=bottom,waterlogged=false]'
                else:material='minecraft:white_concrete'if marking else'minecraft:black_concrete'if carriage[iz,ix]else'minecraft:smooth_stone'
                put(x,y,z,material,'road and sidewalk',allowed|owned_aux)
        if bore[iz,ix]:
            for y in range(floor+row.get('clearance',5)+1,floor+row.get('clearance',5)+3):
                light=y==floor+row.get('clearance',5)+1 and distance[iz,ix]<.8 and along[nearest[iz,ix]]%12<1.5
                put(x,y,z,'minecraft:sea_lantern' if light else 'minecraft:stone_bricks','tunnel crown',allowed|owned_aux)
    wall=np.zeros(walk.shape,bool)
    wing=np.zeros(walk.shape,bool)
    if tunnel:
        wall=binary_dilation(bore&walk,structure=np.ones((3,3)))&~walk
        for iz,ix in np.argwhere(wall):
            x,z,floor=int(xx[iz,ix]),int(zz[iz,ix]),int(hy[iz,ix])
            for y in range(floor-1,floor+row.get('clearance',5)+3):
                put(x,y,z,'minecraft:stone_bricks','tunnel lining',SOIL|EMPTY|PAVEMENT)
        wing=binary_dilation(walk,structure=np.ones((3,3)))&~walk&~wall&~bore
        if existing is not None:wing&=~base_walk
        wing&=target>hy+1
        for iz,ix in np.argwhere(wing):
            x,z,floor=int(xx[iz,ix]),int(zz[iz,ix]),int(hy[iz,ix])
            for y in range(floor-1,int(target[iz,ix])):
                put(x,y,z,'minecraft:stone_bricks','portal wing wall',SOIL|EMPTY|PAVEMENT)
    parapet=np.zeros(walk.shape,bool)
    if bridge:
        # The parapet has its own edge deck outside the commissioned clear
        # sidewalk. A fence placed inside that sidewalk would reduce its width.
        parapet=binary_dilation(span&walk,structure=np.ones((3,3)))&~walk
        for iz,ix in np.argwhere(parapet):
            x,z,floor=int(xx[iz,ix]),int(zz[iz,ix]),int(hy[iz,ix])
            for y in range(floor-int(bridge.get('deck_depth',2)),floor+1):
                put(x,y,z,'minecraft:stone_bricks','parapet edge beam',SOIL|EMPTY|PAVEMENT)
            sides={k:('low' if 0<=iz+dz<walk.shape[0] and 0<=ix+dx<walk.shape[1] and parapet[iz+dz,ix+dx] else 'none')
                   for k,dz,dx in [('east',0,1),('north',-1,0),('south',1,0),('west',0,-1)]}
            state='minecraft:stone_brick_wall['+','.join(f'{k}={v}'for k,v in sorted({**sides,'up':'true','waterlogged':'false'}.items()))+']'
            put(x,floor+1,z,state,'bridge parapet',SOIL|EMPTY|PAVEMENT)
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
        if not span[iz,ix] and any(state(x,Y,z)in EMPTY for Y in range(min(int(old[iz,ix]),y)-1,y)):
            errors.append([x,y,z,'gap below subbase'])
        if any(state(x,Y,z)not in EMPTY for Y in range(y+1,y+row.get('clearance',5)+1)):
            errors.append([x,y,z,'clearance'])
    if errors:raise ValueError((row['id'],errors[:10]))
    return (dict(id=row['id'],status='prepared',changed_cells=len(writes),walk_columns=int(walk.sum()),
                counts=dict(counts),ports=row['points'][::len(row['points'])-1],bounds=row['bounds']),
           (writes,dict(bounds=row['bounds'],old=old,target=target,active=active,
                        walk=walk,road=carriage,grade2=grade2,retired_walk=retired_walk,clearance=row.get('clearance',5),
                        bridge_span=span&bool(bridge),deck_depth=bridge.get('deck_depth',1),
                        tunnel=bore&walk,tunnel_wall=wall,portal_wing=wing)))


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
        d['tunnel'][area][q.get('retired_walk',np.zeros(mask.shape,bool))]=False
        d['tunnel'][area][mask]=q.get('tunnel',np.zeros(mask.shape,bool))[mask]
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
    inherited=list((a.source/'delta').glob('*.npz'))
    if inherited:
        retirement=json.loads((a.source/'retirement-check.json').read_text('utf8'))
        previous=json.loads((a.source/'manifest.json').read_text('utf8'))
        if retirement['errors'] or Path(previous['world']).resolve()!=Path(design['world']).resolve():
            raise ValueError('Only a verified retirement for this same world may precede a corridor')
        for p in inherited:shutil.copy2(p,a.out/'delta'/p.name)
        for name in ('retirement-check.json','retired-surface.npz'):shutil.copy2(a.source/name,a.out/name)
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
