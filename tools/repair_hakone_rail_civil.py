"""Repair measured native railway civil works without replacing native tracks.

All writes are confined to an offline saved-array candidate. Exact occupied
buildings, existing public passage, devices and mechanical volumes are guarded.
"""
import argparse,json,math,os,shutil
from collections import Counter,deque
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import binary_closing,label
from author_hakone_lakefront import Editor
from map_pipeline.rail_civil_geometry import columns,dense_points,vertical_bounds,block_top
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from install_r53_carrier_trays import stopped_world

EMPTY=AIR|PLANTS|{'minecraft:light'}
PASSIVE=SOIL|EMPTY|{'minecraft:water','minecraft:gravel','minecraft:stone_bricks','minecraft:stone_brick_slab',
    'minecraft:light_gray_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:sea_lantern',
    'minecraft:black_concrete','minecraft:white_concrete','minecraft:polished_andesite'}
STONE='minecraft:stone_bricks'


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


def repair(a):
    spec=json.loads(a.design.read_text('utf8'));cap=json.loads((a.source/'capture.json').read_text('utf8'))
    x,z,X,Z=cap['bounds_xz'];world=Path(cap['world'])
    if cap['unavailable_chunks']:raise ValueError('Rail civil requires current FULL chunks')
    if cap['actors']:raise ValueError('Captured actors need explicit finite civil protection')
    curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))['trains'];indices=spec['curve_indices']
    env=columns(curves,indices);wide=columns(curves,indices,2.75,2.75)
    if any(not(x+4<=px<=X-4 and z+4<=pz<=Z-4) for px,pz in wide):raise ValueError('Capture clips the finite civil envelope')
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json');shutil.copy2(a.design,a.out/'plan/rail-civil-design.json')
    shutil.copy2(a.authority/'native-curves.json',a.out/'plan/native-curves.json')
    shutil.copy2(a.authority/'catalog.json',a.out/'plan/catalog.json')
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);area=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[area].copy() if k!='bounds' else np.array([x,z,X,Z])) for k,v in g.items()}
    del g
    with np.load(a.source/'measured.npz') as f:oldground=f['top']
    # Geometry-only repairs do not rebase the terrain field or redefine roads.
    d['old_ground']=d['ground'].copy()
    tags={};station_rows=[];passenger_cells=set()
    for source in spec.get('station_sources',[]):
        station_rows.extend(row for row in json.loads((Path(source)/'plan/buildings.json').read_text('utf8')) if row.get('kind')=='station')
        for station in json.loads((Path(source)/'station-access-check.json').read_text('utf8'))['stations']:
            for px,py,pz in station['path']:
                passenger_cells.update((px,Y,pz) for Y in range(py-1,py+3))
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        for pos,tag in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)):tags[pos]=tag
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(tags.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    launch=load(world);e=Editor(a.out);edits={};issues=[];pier_columns=[];canopy_records=[];thin_deck=[]
    canopy_cells=set()
    for canopy in spec.get('canopies',[]):
        b=canopy['bounds']
        cells={(px,yy,pz) for px in range(b[0],b[3]+1) for pz in range(b[2],b[5]+1) for yy in range(b[1],b[4]+1)
               if e.state(px,yy,pz,original=True)=='minecraft:dark_oak_planks'}
        if len(cells)!=canopy['cells']:raise ValueError('Current complete canopy differs from surveyed footprint')
        canopy_cells.update(cells)
    box_index={}
    for row in catalog:
        b=row['occupied_bounds']
        if b[0]>X or b[3]<x or b[2]>Z or b[5]<z:continue
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):box_index.setdefault((cx,cz),[]).append(b)
    road_y,_=road_blocks(d['grade2'])
    def guarded(pos):
        px,py,pz=pos
        if not(x<=px<=X and z<=pz<=Z and -128<=py<320):return 'capture boundary'
        if pos in tags:return 'device'
        if pos in passenger_cells:return 'station passenger passage'
        if launch.chunk_mask(px//16,pz//16)[py+128,pz%16,px%16]:return 'mechanism'
        for b in box_index.get((px//16,pz//16),[]):
            if all(b[k]<=pos[k]<=b[k+3] for k in range(3)):return 'occupied building'
        j,i=pz-z,px-x
        if d['walk'][j,i] and int(road_y[j,i])-2<=py<=int(road_y[j,i])+4:return 'public passage'
        return None
    def put(pos,state,kind,extra=()):
        old=e.state(*pos)
        if old==state:return
        problem=guarded(pos)
        if problem=='public passage' and state=='minecraft:air' and pos[1]>int(road_y[pos[2]-z,pos[0]-x]):problem=None
        if problem:issues.append([problem,*pos,old,state,kind]);return
        if old.split('[')[0] not in PASSIVE|set(extra):issues.append(['foreign structure',*pos,old,state,kind]);return
        record=edits.setdefault(pos,dict(pos=list(pos),before=old,after=state,kind=kind))
        record['after']=state;record['kind']=kind;e.put(*pos,state)
    # Old roof pieces were generated without continuous walls. Retire only
    # their finite roof band; canopy timber is handled as complete assemblies.
    for (px,pz),row in wide.items():
        for yy in range(math.floor(row['low'])+3,math.ceil(row['high'])+7):
            if e.state(px,yy,pz).split('[')[0] in {STONE,'minecraft:sea_lantern'}:
                put((px,yy,pz),'minecraft:air','retired unlined legacy roof')
    # Continuous half-step bearing: every voxel surface stays below the track.
    for (px,pz),row in env.items():
        floor,state,top,roof=vertical_bounds(row)
        if guarded((px,floor-1,pz))=='public passage':thin_deck.append([px,floor,pz])
        else:put((px,floor-1,pz),STONE,'continuous rail deck')
        put((px,floor,pz),state,'continuous rail bearing')
        for yy in range(floor+1,roof):
            pos=(px,yy,pz)
            put(pos,'minecraft:air','rail clearance',{'minecraft:dark_oak_planks'} if pos in canopy_cells else ())
    # True covered spans derive from current soil, not a projected aerial mask.
    covered=set();spans=[]
    for index in indices:
        if curves[index].get('kind')=='platform':continue
        p=dense_points(curves[index]['points']);mask=[]
        for q in p:
            px,pz=map(int,np.floor(q[[0,2]]));mask.append(oldground[pz-z,px-x]>=math.ceil(q[1]+4.5)+1)
        mask=binary_closing(np.pad(mask,16,mode='edge'),iterations=16)[16:-16]
        labels,count=label(mask)
        for k in range(1,count+1):
            at=np.flatnonzero(labels==k)
            if len(at)<33:continue
            segment=dict(points=p[at].tolist(),kind='rail')
            owned=columns([segment],[0]);covered.update(q for q in owned if q in env)
            spans.append(dict(curve=index,start=p[at[0]].tolist(),end=p[at[-1]].tolist(),length=float(np.linalg.norm(np.diff(p[at][:,[0,2]],axis=0),axis=1).sum())))
    roofs={q:vertical_bounds(env[q])[3] for q in covered};walls={}
    for (px,pz),roof in roofs.items():
        ceiling=max([roof]+[roofs.get(q,roof) for q in [(px-1,pz),(px+1,pz),(px,pz-1),(px,pz+1)]])
        for yy in range(roof,ceiling+1):put((px,yy,pz),STONE,'continuous tunnel roof')
        for q in [(px-1,pz),(px+1,pz),(px,pz-1),(px,pz+1)]:
            if q in env:continue
            floor=vertical_bounds(env[px,pz])[0]
            if q in walls:walls[q]=(min(walls[q][0],floor-2),max(walls[q][1],ceiling))
            else:walls[q]=(floor-2,ceiling)
    def support_column(px,pz,start,kind):
        pending=[]
        for yy in range(start,max(-128,start-48)-1,-1):
            old=e.state(px,yy,pz);mat=old.split('[')[0]
            if mat in SOIL and 'type=bottom' not in old:break
            if guarded((px,yy,pz)) or mat not in PASSIVE:return False
            pending.append((px,yy,pz))
        else:return False
        for pos in reversed(pending):put(pos,STONE,kind)
        if pending:pier_columns.append(dict(top=list(pending[0]),footing=[px,yy,pz],kind=kind))
        return True
    for (px,pz),(low,high) in walls.items():
        if not support_column(px,pz,low-1,'tunnel wall footing'):issues.append(['unfounded tunnel sidewall',px,low,pz]);continue
        for yy in range(low,high+1):put((px,yy,pz),STONE,'continuous tunnel sidewall')
    # Piers below the deck are selected at eight-metre intervals. A road below
    # rejects the entire candidate pier, leaving its clear span unobstructed.
    for index in indices:
        p=dense_points(curves[index]['points'],1.)
        for k in range(0,len(p),8):
            px,pz=map(int,np.floor(p[k,[0,2]]))
            candidates=sorted([q for q in env if abs(q[0]-px)<=2 and abs(q[1]-pz)<=2],key=lambda q:(q[0]-px)**2+(q[1]-pz)**2)
            for Q,R in candidates:
                floor=vertical_bounds(env[Q,R])[0]
                if support_column(Q,R,floor-2,'measured bridge pier'):break
    # Explicit complete platform canopies move one block upward when needed,
    # providing 5 m clearance while keeping their measured timber footprint.
    for canopy in spec.get('canopies',[]):
        b=canopy['bounds'];cells=[]
        for px in range(b[0],b[3]+1):
            for pz in range(b[2],b[5]+1):
                for yy in range(b[1],b[4]+1):
                    if e.state(px,yy,pz,original=True)=='minecraft:dark_oak_planks':cells.append((px,yy,pz))
        if len(cells)!=canopy['cells']:raise ValueError('Current canopy footprint changed')
        shift=canopy.get('raise',1)
        for pos in cells:
            target=(pos[0],pos[1]+shift,pos[2])
            if e.state(*target).split('[')[0] not in AIR:issues.append(['canopy destination occupied',*target]);continue
            put(pos,'minecraft:air','raised complete station canopy',{'minecraft:dark_oak_planks'})
            put(target,'minecraft:dark_oak_planks','raised complete station canopy')
        supports=[]
        for px,py,pz in sorted(cells,key=lambda q:(q[0],q[2])):
            if (px,pz) in env:continue
            if any(math.hypot(px-q[0],pz-q[2])<7 for q in supports):continue
            roof=py+shift;pending=[]
            for yy in range(roof-1,roof-12,-1):
                state=e.state(px,yy,pz);mat=state.split('[')[0]
                if mat not in EMPTY:
                    if mat in PASSIVE and 'type=bottom' not in state:break
                    pending=[];break
                if guarded((px,yy,pz)):pending=[];break
                pending.append((px,yy,pz))
            else:pending=[]
            if not pending:continue
            for pos in pending:put(pos,'minecraft:polished_andesite','station canopy column')
            supports.append([px,yy,pz])
        if len(supports)<2:issues.append(['insufficient canopy columns',canopy['name'],len(supports)])
        canopy_records.append(dict(name=canopy['name'],timber_cells=len(cells),raised=shift,supports=supports))
    for removal in spec.get('retire_cells',[]):
        pos=tuple(removal['pos'])
        if e.state(*pos,original=True)!=removal['state']:raise ValueError(('Stale explicit remnant',pos))
        put(pos,'minecraft:air','reviewed detached old civil remnant')
    for fragment in spec.get('support_fragments',[]):
        px,py,pz=fragment['base']
        if e.state(px,py,pz,original=True)!=fragment['state']:raise ValueError('Stale measured exterior fragment')
        if not support_column(px,pz,py-1,'measured exterior fragment footing'):issues.append(['exterior fragment footing blocked',px,py,pz])
    patches=e.save();e.regions.clear()
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=[x,z,X,Z],regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'civil-edits.json',list(edits.values()));save(a.out/'civil-conflicts.json',issues)
    save(a.out/'rail-civil-geometry.json',dict(curves=indices,columns=[dict(x=q[0],z=q[1],**{k:(sorted(v) if k=='curves' else v) for k,v in r.items()}) for q,r in env.items()],covered_columns=[list(q) for q in sorted(covered)],tunnels=spans,pier_columns=pier_columns,canopies=canopy_records,road_overpass_single_course_deck=thin_deck))
    # Current road/city planning stays authoritative; this patch owns rail
    # structures only and does not declare any new pedestrian/cargo routes.
    np.savez_compressed(a.out/'plan/network.npz',**d)
    save(a.out/'plan/buildings.json',station_rows);save(a.out/'plan/footways.json',[])
    save(a.out/'functional-check.json',dict(errors=issues,native_curves_unchanged=True,devices_untouched=len(tags),civil_edits=len(edits),tunnel_spans=spans,canopies=canopy_records))
    save(a.out/'launch-protection.json',check_candidate(launch,a.out))
    print('Rail civil candidate',sum(r['cells'] for r in patches),'cells;',len(env),'track columns;',len(spans),'tunnel spans;',len(issues),'conflicts',flush=True)
    if issues:raise ValueError(issues[:12])


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','authority','design','out'):p.add_argument('--'+n,type=Path,required=True)
    repair(p.parse_args())
