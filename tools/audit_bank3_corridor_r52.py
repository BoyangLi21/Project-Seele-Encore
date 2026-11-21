"""Read-only diagnosis of the Root bank-three excavation candidate."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from collections import defaultdict
import numpy as np
from plan_bank3_outlet_r52 import OUT,design,contains


def main():
    parts,_=design();data=np.load(OUT/'SECTION_SOURCE.npz');shells=data['shell'];previous=data['before']
    lower=np.array([p['bounds'][0] for p in parts]);upper=np.array([p['bounds'][1] for p in parts])
    local=np.array([[x+.5,y+.5,z+.5]for y in range(16)for z in range(16)for x in range(16)])
    overlap={};foreign=defaultdict(list);palette=list(map(str,data['palette']))
    for index,(cx,cz,sy) in enumerate(data['section_keys']):
        base=np.array([cx*16,sy*16,cz*16]);selected=np.flatnonzero(np.all(upper>=base,axis=1)&np.all(lower<=base+16,axis=1))
        if len({parts[k]['lane']for k in selected})>1:
            points=local+base;lanes=np.zeros((3,4096),bool)
            for k in selected:lanes[parts[k]['lane']]|=contains(parts[k],points)
            for a,b in ((0,1),(0,2),(1,2)):
                hit=points[lanes[a]&lanes[b]]
                if not len(hit):continue
                key=f'{a}/{b}';lo=hit.min(0);hi=hit.max(0)
                if key not in overlap:overlap[key]=dict(count=0,lo=lo,hi=hi,sections=[])
                row=overlap[key];row['count']+=len(hit);row['lo']=np.minimum(row['lo'],lo);row['hi']=np.maximum(row['hi'],hi)
                row['sections'].append(dict(key=[int(cx),int(cz),int(sy)],count=len(hit)))
        touched=shells[index];before=previous[index]
        for value in np.unique(before[touched]):
            state=palette[int(value)]
            if state.startswith(('mtr:','projectseele:clear_glass')):
                q=local[touched&(before==value)]+base
                foreign[state].append(dict(count=len(q),lo=q.min(0).tolist(),hi=q.max(0).tolist()))
    for row in overlap.values():
        row['lo']=row['lo'].tolist();row['hi']=row['hi'].tolist()
        row['sections']=sorted(row['sections'],key=lambda x:-x['count'])[:12]
    report=dict(world_written=False,overlaps=overlap,retained_interface_material=foreign)
    (OUT/'OVERLAP_AUDIT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
