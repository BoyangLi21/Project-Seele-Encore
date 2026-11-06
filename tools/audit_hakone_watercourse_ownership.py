"""Measure saved water and finite 3-D ownership around proposed watercourses."""
import argparse,json
from pathlib import Path
from collections import Counter
import numpy as np
from plan_ashi_landscape_r54 import NATURAL

def audit(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'))
    with np.load(a.programme/'watercourse-reference.npz')as f:d={k:f[k]for k in f.files}
    if list(map(int,d['bounds']))!=cap['bounds_xz']:raise ValueError('Programme and saved source bounds differ')
    x,z,X,Z=map(int,d['bounds'])
    with np.load(a.source/'measured.npz')as f:ground=f['top'];full=f['full'];actors=f['actors']
    if not full.all():raise ValueError('Unknown saved terrain requires explicit generation-stage handling')
    water=np.full(ground.shape,-32768,np.int16);near=np.zeros(ground.shape,bool);overhead=near.copy();yy=np.arange(-128,320)[:,None,None];materials=Counter()
    for path in sorted((a.source/'source').glob('*.npz')):
        with np.load(path)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        wet=np.asarray([s.split('[')[0]=='minecraft:water'for s in names]);foreign=np.asarray([s.split('[')[0]not in NATURAL for s in names])
        for(cx,cz),v in zip(coords,blocks):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];g=ground[q]
            water[q]=np.where(wet[v]&(yy>g),yy,-32768).max(0)
            band=(yy>=g-8)&(yy<=g+4);near[q]=(foreign[v]&band).any(0);overhead[q]=(foreign[v]&(yy>g+4)).any(0)
            for k,n in zip(*np.unique(v[d['river'][q]&band&foreign[v]],return_counts=True)):materials[names[int(k)]]+=int(n)
        print('Measured watercourse ownership',path.name,flush=True)
    rows=json.loads((a.programme/'watercourse-programme.json').read_text('utf8'))['components'];observed=[]
    for row in rows:
        l,t,r,b=row['bounds'];q=np.s_[t-z:b-z+1,l-x:r-x+1];use=d['labels'][q]==row['id'];g=ground[q][use];w=water[q][use]
        observed.append(dict(id=row['id'],columns=len(g),bounds=row['bounds'],ground_range=[int(g.min()),int(g.max())],
            wet_columns=int((w>g).sum()),near_bed_foreign_columns=int(near[q][use].sum()),overhead_structure_columns=int(overhead[q][use].sum()),
            actor_columns=int(actors[q][use].sum()),regional_boundary=bool(row['open_regional_interface']),sea_outlet=bool(row['reaches_geographic_sea'])))
    a.out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(a.out/'measured-water.npz',bounds=d['bounds'],ground=ground,water=water,full=full,
        near_bed_foreign=near,overhead_structures=overhead,actors=actors)
    report=dict(source=str(a.source),programme=str(a.programme),full_chunks=cap['chunk_statuses']['full'],actors=len(cap['actors']),
        reference_water_columns=int(d['reference'].sum()),actual_wet_reference_columns=int((d['reference']&(water>ground)).sum()),
        proposed_channel_columns=int(d['river'].sum()),proposed_near_bed_foreign_columns=int((d['river']&near).sum()),
        proposed_actor_columns=int((d['river']&actors).sum()),near_bed_foreign_materials=dict(materials),components=observed,
        world_written=False,not_a_construction_authorization_mask=True,
        next_check='Actual changed XYZ cells, inventories, actor envelopes, existing public surfaces, water connectivity, upstream seams and future generation still require verification.')
    (a.out/'watercourse-ownership.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in ('components','near_bed_foreign_materials')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','programme','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(p.parse_args())
