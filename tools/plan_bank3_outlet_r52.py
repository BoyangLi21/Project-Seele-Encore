"""Root-only three-lane Hakone launch corridor, measured before construction.

Staggered bearing heights keep the three long inclined branches separate.
The actual R50 carrier/body bounds are expanded, never reduced to a torso box.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,math
from pathlib import Path
from collections import defaultdict
import numpy as np
from query_blocks import chunk_statuses,iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE

WORLD=BASE/'WORLD_R52'
OUT=BASE/'bank3_outlet'
BASE_ROT=np.diag([-1.,1.,-1.])


def rotation(direction,amount=1.):
    d=np.asarray(direction,float);d/=np.linalg.norm(d);axis=np.cross([0.,1.,0.],d);s=np.linalg.norm(axis)
    if s<1e-12:return BASE_ROT.copy()
    axis/=s;theta=math.acos(float(np.clip(d[1],-1,1)))*amount
    x,y,z=axis;k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return (np.eye(3)+math.sin(theta)*k+(1-math.cos(theta))*(k@k))@BASE_ROT


def corners(lo,hi):return np.asarray([[x,y,z]for x in (lo[0],hi[0])for y in(lo[1],hi[1])for z in(lo[2],hi[2])])


def component(label,foot,rot,lower,upper,lane,kind):
    lo=np.asarray(lower,float);hi=np.asarray(upper,float);f=np.asarray(foot,float);verts=corners(lo-2,hi+2)@rot.T+f
    return dict(id=label,lane=lane,kind=kind,foot=f,rotation=rot,lower=lo,upper=hi,bounds=[verts.min(0),verts.max(0)])


def contains(c,points,lining=0):
    local=(points-c['foot'])@c['rotation']
    # A block whose cube intersects the oriented corridor is included, so
    # diagonal voxel corners cannot remain inside the actual moving envelope.
    radius=.5*np.sum(np.abs(c['rotation']),axis=0)+lining
    return np.all(local>=c['lower']-radius,axis=1)&np.all(local<=c['upper']+radius,axis=1)


def design():
    facts=json.loads((Path(__file__).resolve().parents[1]/'.Codex/r52_original_mesh_geometry_candidate/FACTORY_BOUNDS_AND_SOLES.json').read_text('utf8'))
    soles={}
    for u in facts['units']:
        # Actual per-variant foot centres are supplied explicitly below after
        # the frozen source audit; no entity-origin-as-bearing shortcut.
        soles[u['variant']]={0:.224014043808,1:.223975896835,2:.183567047119}[u['variant']]
    components=[];routes=[]
    for lane,x in enumerate((-11.5,30.5,72.5)):
        variant=2-lane;sole=soles[variant]
        bank=np.array([x,-646.,-448.5]);start=np.array([x,-636.+42*lane,-448.5])
        end=np.array([-1919.5,-580.+30*lane,570.5+48*lane]);surface=np.array([end[0],105.,end[2]])
        offset=np.array([0.,0.,-sole]);bf,sf,ef,pf=[p+offset for p in (bank,start,end,surface)]
        direction=ef-sf;length=np.linalg.norm(direction);r=rotation(direction)
        lower=np.array([-15.94,-3.21,-15.59-sole]);upper=np.array([15.,61.01,15.59-sole])
        components.append(component(f'lane{lane}_first_vertical',bf,BASE_ROT,lower,upper+[0,start[1]-bank[1],0],lane,'vertical'))
        # Half-degree angular samples plus a full metre source-bound margin.
        theta=math.degrees(math.acos(float(direction[1]/length)))
        for index,t in enumerate(np.linspace(0,1,math.ceil(theta/.5)+1)):
            q=rotation(direction,float(t))
            components.append(component(f'lane{lane}_turn_in_{index}',sf,q,lower,upper,lane,'bearing'))
            components.append(component(f'lane{lane}_turn_out_{index}',ef,q,lower,upper,lane,'bearing'))
        components.append(component(f'lane{lane}_incline',sf,r,lower,upper+[0,length,0],lane,'incline'))
        components.append(component(f'lane{lane}_last_vertical',ef,BASE_ROT,lower,upper+[0,surface[1]-end[1],0],lane,'vertical'))
        routes.append(dict(lane=lane,variant=variant,body_roots=[bank.tolist(),start.tolist(),end.tolist(),surface.tolist()],
            foot_nodes=[bf.tolist(),sf.tolist(),ef.tolist(),pf.tolist()],incline_metres=float(length),incline_body_rotation_matrix=r.tolist(),
            surface_block_centre=[-1920,104,570+48*lane],actual_sole_z=sole))
    return components,routes


def main():
    OUT.mkdir(exist_ok=True);parts,routes=design();selected=defaultdict(set);per_section=defaultdict(list)
    for index,c in enumerate(parts):
        a,b=c['bounds'];a=np.floor(a/16).astype(int);b=np.floor(b/16).astype(int)
        for cx in range(a[0],b[0]+1):
            for cz in range(a[2],b[2]+1):
                for sy in range(a[1],b[1]+1):
                    centre=np.array([[cx*16+8.,sy*16+8.,cz*16+8.]])
                    local=(centre-c['foot'])@c['rotation'];radius=8*np.sum(np.abs(c['rotation']),axis=0)+2
                    if not(np.all(local>=c['lower']-radius)and np.all(local<=c['upper']+radius)):continue
                    selected[cx,cz].add(sy);per_section[cx,cz,sy].append(index)
    status=chunk_statuses(WORLD,'projectseele:geofront',selected)
    missing={f'{x},{z}':s for (x,z),s in status.items()if s!='full'}
    document=dict(schema='projectseele.r52.root-bank3-spatial.v1',map_author='root',world_written=False,playable=False,
        routes=routes,selected_chunks=len(selected),selected_sections=len(per_section),missing_chunks=missing,
        source_box_margins=True,native_whole_triangle_sweep_pending=True,
        pending=['actual block/retained component conflicts','corridor separation and physical rails','surface aprons and real doors','final source-specific native transit'])
    (OUT/'DESIGN.json').write_text(json.dumps(document,indent=2),'utf8')
    if missing:print(json.dumps(dict(status='NATIVE_CHUNKS_REQUIRED',count=len(missing),first=list(missing.items())[:15])));return
    local=np.array([[x+.5,y+.5,z+.5]for y in range(16)for z in range(16)for x in range(16)])
    palette=['minecraft:air'];ids={palette[0]:0};records=[];counts=defaultdict(int);first=defaultdict(list);lane_overlaps=0
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
        'minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:sand','minecraft:gravel','minecraft:water[level=0]','minecraft:grass','minecraft:fern'}
    for cx,cz,sy,names,old in iter_selected_sections(WORLD,'projectseele:geofront',selected):
        indices=per_section.get((cx,cz,sy),[])
        if not indices:continue
        p=local+[cx*16,sy*16,cz*16];core=np.zeros(4096,bool);shell=np.zeros(4096,bool);lanes=np.zeros(4096,np.uint8)
        for k in indices:
            c=parts[k];v=contains(c,p);core|=v;shell|=contains(c,p,2);lanes[v]|=1<<c['lane']
        if not shell.any():continue
        lane_overlaps+=int(np.count_nonzero((lanes!=0)&((lanes&(lanes-1))!=0)))
        mapping=[]
        for state in names:
            if state not in ids:ids[state]=len(palette);palette.append(state)
            mapping.append(ids[state])
        values=np.asarray(mapping,np.uint16)[old];touched=np.flatnonzero(shell)
        for v in np.unique(values[touched]):
            state=palette[int(v)]
            if state in natural or '_leaves['in state or '_log['in state:continue
            match=np.flatnonzero(shell&(values==v));counts[state]+=len(match)
            for j in match[:max(0,10-len(first[state]))]:first[state].append(np.floor(p[j]).astype(int).tolist())
        records.append((cx,cz,sy,values,core,shell))
    target=OUT/'SECTION_SOURCE.npz'
    np.savez_compressed(target,section_keys=np.array([r[:3]for r in records],np.int32),before=np.array([r[3]for r in records],np.uint16),
        core=np.array([r[4]for r in records],bool),shell=np.array([r[5]for r in records],bool),palette=palette)
    document.update(measured_sections=len(records),measured_core_cells=int(sum(r[4].sum()for r in records)),
        measured_outer_cells=int(sum(r[5].sum()for r in records)),overlapping_lane_core_cells=lane_overlaps,
        nonnatural_counts=dict(counts),first_nonnatural_positions=dict(first))
    (OUT/'DESIGN.json').write_text(json.dumps(document,indent=2),'utf8')
    print(json.dumps({k:v for k,v in document.items()if k not in ('routes','first_nonnatural_positions','pending')}),flush=True)


if __name__=='__main__':main()
