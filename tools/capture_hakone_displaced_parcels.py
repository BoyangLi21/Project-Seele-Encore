"""Capture whole original parcels intersected by an authorized new city outline."""
import argparse,copy,json
from pathlib import Path
import numpy as np
import nbtlib
from query_blocks import chunk_statuses,iter_selected_sections,iter_block_entities,dimension_dir
from install_r53_carrier_trays import stopped_world
from transplant_s22_authority import read_region,parse_chunk


def capture(a):
    if a.out.exists()and not a.resume:raise ValueError('Use a fresh parcel snapshot or explicitly resume its incomplete capture')
    rects=json.loads(a.plan.read_text('utf8'))['cross_rectangles_xz']
    plots=json.loads(a.catalogue.read_text('utf8'))['kept_plots']
    retired=set()
    for file in a.already_retired:retired.update(r['id']for r in json.loads(file.read_text('utf8'))['plots'])
    a.out.mkdir(parents=True,exist_ok=True);rows=[]
    for plot in plots:
        if plot['id']in retired:continue
        x0,x1,z0,z1=plot['bounds'];base=plot['floor']
        if not any(x1>=x and x0<=X and z1>=z and z0<=Z for x,z,X,Z in rects):continue
        lo=[x0-4,base-3,z0-4];hi=[x1+4,base+plot.get('storeys',1)*5+7,z1+4]
        key=plot['id'].replace('/','_')
        if a.resume and (a.out/f'{key}.npz').exists()and(a.out/f'{key}.dat').exists():
            with np.load(a.out/f'{key}.npz')as saved:
                if list(saved['origin'])!=lo or tuple(saved['blocks'].shape)!=(hi[1]-lo[1]+1,hi[2]-lo[2]+1,hi[0]-lo[0]+1):raise ValueError('Different parcel scope in resumed capture')
            tags=list(nbtlib.load(a.out/f'{key}.dat')['BlockEntities'])
            rows.append(dict(plot,source_bounds_xyz=lo+hi,block_entities=len(tags),inventories=sum(bool(t.get('Items'))for t in tags),snapshot=key,actors=[]))
            continue
        selected={(cx,cz):set(range(lo[1]//16,hi[1]//16+1))for cx in range(lo[0]//16,hi[0]//16+1)for cz in range(lo[2]//16,hi[2]//16+1)}
        if any(v!='full'for v in chunk_statuses(a.world,'projectseele:geofront',selected).values()):raise ValueError(plot['id'])
        palette=['minecraft:air'];codes={palette[0]:0};voxels=np.zeros((hi[1]-lo[1]+1,hi[2]-lo[2]+1,hi[0]-lo[0]+1),np.uint16)
        for cx,cz,sy,pal,ids in iter_selected_sections(a.world,'projectseele:geofront',selected):
            for state in pal:
                if state not in codes:codes[state]=len(palette);palette.append(state)
            block=np.array([codes[s]for s in pal],np.uint16)[ids].reshape(16,16,16)
            start=np.maximum([cx*16,sy*16,cz*16],lo);end=np.minimum([cx*16+16,sy*16+16,cz*16+16],np.array(hi)+1)
            voxels[start[1]-lo[1]:end[1]-lo[1],start[2]-lo[2]:end[2]-lo[2],start[0]-lo[0]:end[0]-lo[0]]=block[start[1]-sy*16:end[1]-sy*16,start[2]-cz*16:end[2]-cz*16,start[0]-cx*16:end[0]-cx*16]
        key=plot['id'].replace('/','_');bes=list(iter_block_entities(a.world,'projectseele:geofront',tuple(lo),tuple(hi),selected_chunks=set(selected)))
        np.savez_compressed(a.out/f'{key}.npz',origin=np.asarray(lo),blocks=voxels,palette=np.asarray(palette))
        nbtlib.File({'BlockEntities':nbtlib.List[nbtlib.Compound]([copy.deepcopy(t)for p,t in bes])}).save(a.out/f'{key}.dat',gzipped=True)
        rows.append(dict(plot,source_bounds_xyz=lo+hi,block_entities=len(bes),inventories=sum(bool(t.get('Items'))for p,t in bes),snapshot=key,actors=[]))
    regions=set()
    for r in rows:
        x0,_,z0,x1,_,z1=r['source_bounds_xyz']
        regions.update((rx,rz)for rx in range(x0//512,x1//512+1)for rz in range(z0//512,z1//512+1))
    for rx,rz in regions:
        file=dimension_dir(a.world,'projectseele:geofront')/'entities'/f'r.{rx}.{rz}.mca'
        if not file.exists()or not file.stat().st_size:continue
        for raw in read_region(file)[1]:
            if raw is None:continue
            for entity in parse_chunk(raw).get('Entities',[]):
                pos=list(map(float,entity.get('Pos',[])))
                if len(pos)!=3:continue
                for row in rows:
                    b=row['source_bounds_xyz']
                    if all(b[i]<=pos[i]<b[i+3]+1 for i in range(3)):row['actors'].append(dict(id=str(entity.get('id')),position=pos,nbt=entity.snbt()))
    report=dict(world=str(a.world),world_written=False,status='whole original parcels captured; replacement authoring required',plots=rows)
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print([(r['id'],r['block_entities'],r['inventories'],len(r['actors']))for r in rows],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('world','plan','catalogue','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--already-retired',type=Path,action='append',default=[])
    p.add_argument('--resume',action='store_true',help='Reuse completed parcel snapshots after an interrupted read-only capture')
    a=p.parse_args()
    with stopped_world(a.world):capture(a)
