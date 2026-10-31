"""Capture saved post-surface protochunks without promoting their status."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from query_blocks import iter_selected_sections,AIR
from plan_ashi_landscape_r54 import SOIL,NATURAL

def capture(a):
    record=json.loads((a.complete/'capture.json').read_text('utf8'))
    chosen={(x,z):s for x,z,s in record['unavailable_chunks']if s in ('features','initialize_light','light','spawn')}
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    x0,z0,x1,z1=record['bounds_xz'];shape=(z1-z0+1,x1-x0+1)
    top=np.full(shape,-129,np.int16);high=top.copy();present=np.zeros(shape,bool)
    groups=defaultdict(dict)
    for p,s in chosen.items():groups[p[0]//32,p[1]//32][p]=set(range(-8,20))
    yy=np.arange(-128,320)[:,None,None]
    for i,((rx,rz),selected)in enumerate(sorted(groups.items())):
        coords=sorted(selected);index={p:i for i,p in enumerate(coords)};names=['minecraft:air'];ids={names[0]:0}
        b=np.zeros((len(coords),448,16,16),np.uint16)
        for cx,cz,sy,palette,values in iter_selected_sections(a.frozen,'projectseele:geofront',selected,expected_statuses=chosen):
            for s in palette:
                if s not in ids:ids[s]=len(names);names.append(s)
            remap=np.array([ids[s]for s in palette],np.uint16);b[index[cx,cz],sy*16+128:sy*16+144]=remap[values].reshape(16,16,16)
        soil=np.array([s.split('[')[0]in SOIL for s in names]);air=np.array([s in AIR for s in names])
        for (cx,cz),blocks in zip(coords,b):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            top[area]=np.where(soil[blocks],yy,-129).max(0);high[area]=np.where(~air[blocks],yy,-129).max(0);present[area]=True
        np.savez_compressed(a.out/'source'/f'r.{rx}.{rz}.npz',coordinates=coords,palette=names,blocks=b)
        print('Saved protochunk surfaces',i+1,'/',len(groups),flush=True)
    np.savez_compressed(a.out/'measured.npz',bounds=record['bounds_xz'],top=top,highest=high,full=present)
    report=dict(world=record['world'],regions=[],cells=0,bounds_xz=record['bounds_xz'],retired_stumps=[],
        preserved_generation_statuses=[[*p,s]for p,s in chosen.items()],world_written=False)
    (a.out/'manifest.json').write_text(json.dumps(report,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('frozen','complete','out'):p.add_argument('--'+n,type=Path,required=True)
    capture(p.parse_args())
