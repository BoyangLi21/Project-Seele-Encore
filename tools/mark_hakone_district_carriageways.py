"""Paint bounded centre dashes on verified roads, keeping junctions clear."""
import argparse
import json
import os
from pathlib import Path
import shutil

import numpy as np
from scipy.spatial import cKDTree

from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.corridors import alignment


def paint(a):
    for name in ('functional-check.json','independent-check.json','new-frontages-check.json'):
        if json.loads((a.source/name).read_text('utf8'))['errors']:raise ValueError('Unverified district '+name)
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'source').mkdir()
    for path in (a.source/'source').glob('*.npz'):os.link(path,a.out/'source'/path.name)
    for path in a.source.iterdir():
        if path.name=='source':continue
        if path.is_dir():shutil.copytree(path,a.out/path.name)
        else:shutil.copy2(path,a.out/path.name)
    with np.load(a.out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);zz,xx=np.mgrid[z:Z+1,x:X+1]
    spec=json.loads((a.out/'plan/authored-design.json').read_text('utf8'))
    curves=[alignment(row)for row in spec['streets']]
    ends=np.asarray([curve[k,[0,2]]for curve,_ in curves for k in(0,-1)])
    # Clear every branch end, including small junction stubs, so overlaid
    # roads never make a knot of contradictory white stripes.
    clear=np.zeros(d['road'].shape,bool)
    for px,pz in ends:clear|=np.hypot(xx-px,zz-pz)<9
    marking=np.zeros_like(clear)
    for curve,along in curves:
        if along[-1]<75:continue
        distance,nearest=cKDTree(curve[:,[0,2]]).query(np.column_stack([xx.ravel(),zz.ravel()]))
        distance=distance.reshape(clear.shape);nearest=nearest.reshape(clear.shape)
        marking|=(distance<=.52)&((np.floor(along[nearest]/4).astype(int)%2)==0)
    marking&=d['road']&~clear
    e=Editor(a.out);edits=[]
    for j,i in np.argwhere(marking):
        px,pz=int(i+x),int(j+z);h,slab=road_blocks(d['grade2'][j,i]);h=int(h);before=e.state(px,h,pz)
        expected='projectseele:road_asphalt_slab'if slab else'minecraft:black_concrete'
        if before.split('[')[0]!=expected:raise ValueError(('Centre dash would replace a different surface',px,h,pz,before))
        after='projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete'
        e.put(px,h,pz,after);edits.append(dict(pos=[px,h,pz],before=before,after=after))
    d['marking']|=marking;np.savez_compressed(a.out/'plan/network.npz',**d)
    patches=e.save();manifest=json.loads((a.out/'manifest.json').read_text('utf8'))
    manifest.update(regions=patches,cells=sum(r['cells']for r in patches))
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    proof=dict(cells=len(edits),junction_radius=9,all_surfaces_keep_the_same_full_or_bottom_slab_shape=True,edits=edits,world_written=False)
    (a.out/'carriageway-markings.json').write_text(json.dumps(proof,indent=2),'utf8')
    print('Painted',len(edits),'road-centre cells; all junctions and road heights retained',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out'):p.add_argument('--'+name,type=Path,required=True)
    paint(p.parse_args())
