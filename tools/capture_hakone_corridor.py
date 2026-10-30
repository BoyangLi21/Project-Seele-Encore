"""Capture current FULL terrain and surface actors for an offline corridor pass."""
import argparse,json,math
from pathlib import Path
from collections import Counter
import numpy as np
from prepare_hakone_main_terrain import capture
from plan_ashi_landscape_r54 import SOIL,NATURAL
from transplant_s22_authority import read_region,parse_chunk
from query_blocks import dimension_dir,chunk_statuses,AIR
from install_r53_carrier_trays import stopped_world


def main(a):
    if a.out.exists()and not a.reuse_captured_arrays:raise ValueError('Choose a new source snapshot; installed baselines are immutable')
    if a.reuse_captured_arrays and(a.out/'capture.json').exists():raise ValueError('A completed capture is immutable')
    x0,z0,x1,z1=a.bounds
    if x0%16 or z0%16 or(x1+1)%16 or(z1+1)%16:raise ValueError('Bounds must contain full chunks')
    (a.out/'source').mkdir(parents=True,exist_ok=True);(a.out/'delta').mkdir(exist_ok=True)
    actors=[]
    with stopped_world(a.world):
        if a.reuse_captured_arrays:
            shape=(z1-z0+1,x1-x0+1);measured=dict(top=np.full(shape,-129,np.int16),highest=np.full(shape,-129,np.int16),protected=np.zeros(shape,bool),full=np.zeros(shape,bool))
            yy=np.arange(-128,320,dtype=np.int16)[:,None,None];files=[];status={}
            for source in sorted((a.out/'source').glob('*.npz')):
                with np.load(source)as data:coords=data['coordinates'];blocks=data['blocks'];names=[str(s).split('[')[0]for s in data['palette']]
                soil=np.asarray([s in SOIL for s in names]);natural=np.asarray([s in NATURAL for s in names]);air=np.asarray([s in AIR for s in names])
                for (cx,cz),b in zip(coords,blocks):
                    area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
                    measured['top'][area]=np.where(soil[b],yy,-129).max(0);measured['highest'][area]=np.where(~air[b],yy,-129).max(0)
                    measured['protected'][area]=((~natural[b])&(yy>=32)).any(0);measured['full'][area]=True;status[int(cx),int(cz)]='full'
                files.append(str(source.relative_to(a.out)))
            missing={(cx,cz)for cx in range(x0//16,x1//16+1)for cz in range(z0//16,z1//16+1)}-status.keys()
            if missing:status.update(chunk_statuses(a.world,'projectseele:geofront',missing))
        else:measured,files,status=capture(a.world,a.bounds,a.out)
        occupied=np.zeros(measured['top'].shape,bool)
        for rx in range(x0//512,x1//512+1):
            for rz in range(z0//512,z1//512+1):
                file=dimension_dir(a.world,'projectseele:geofront')/'entities'/f'r.{rx}.{rz}.mca'
                if not file.exists()or not file.stat().st_size:continue
                _,rows=read_region(file)
                for row in rows:
                    if row is None:continue
                    for actor in parse_chunk(row).get('Entities',[]):
                        p=list(map(float,actor.get('Pos',[])))
                        if len(p)!=3 or not(x0<=p[0]<=x1 and z0<=p[2]<=z1 and -128<=p[1]<320):continue
                        actors.append(dict(id=str(actor['id']),pos=p,uuid=list(map(int,actor.get('UUID',[])))))
                        x,z=math.floor(p[0]),math.floor(p[2]);radius=16 if 'aircraft'in str(actor['id'])or str(actor['id'])in('superbwarfare:j_16','superbwarfare:ac_130h')else 4
                        occupied[max(0,z-z0-radius):min(occupied.shape[0],z-z0+radius+1),max(0,x-x0-radius):min(occupied.shape[1],x-x0+radius+1)]=True
        np.savez_compressed(a.out/'measured.npz',bounds=a.bounds,**measured,actors=occupied)
    report=dict(world=str(a.world),bounds_xz=a.bounds,source_files=files,actors=actors,chunk_statuses=dict(Counter(status.values())),
                unavailable_chunks=[[*p,s]for p,s in status.items()if s!='full'],world_written=False)
    (a.out/'capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(chunk_statuses=report['chunk_statuses'],actors=len(actors),source=str(a.out))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--bounds',nargs=4,type=int,required=True)
    p.add_argument('--reuse-captured-arrays',action='store_true',help='Finish actor capture after a failed capture using already-written immutable arrays')
    main(p.parse_args())
