"""Expand an immutable planning frame without inventing public-road claims.

New cells have unknown soil height and no public surface. Only a supplied
complete current FULL capture contributes measured soil, and overlap retains
all previously installed route ownership until a separately verified release.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np


def extend(a):
    if a.out.exists(): raise ValueError('Use a fresh planning frame')
    capture=json.loads((a.source/'capture.json').read_text('utf8'))
    if capture['unavailable_chunks']: raise ValueError('Complete current FULL source required')
    with np.load(a.previous/'network.npz') as f: old={k:f[k] for k in f.files}
    x,z,X,Z=map(int,old['bounds']); a0,b0,A0,B0=capture['bounds_xz']
    bounds=[min(x,a0),min(z,b0),max(X,A0),max(Z,B0)]
    l,t,r,b=bounds; shape=(b-t+1,r-l+1); original=np.s_[z-t:Z-t+1,x-l:X-l+1]
    revised={}
    for key,value in old.items():
        if key=='bounds': continue
        if value.shape!=(Z-z+1,X-x+1): raise ValueError(('Unsupported planning field',key,value.shape))
        fill=-129 if key in ('ground','old_ground') else 0
        result=np.full(shape,fill,dtype=value.dtype); result[original]=value; revised[key]=result
    with np.load(a.source/'measured.npz') as f:
        measured=f['top']; full=f['full']
    if not full.all(): raise ValueError('Unknown terrain cannot seed the expanded frame')
    target=np.s_[b0-t:B0-t+1,a0-l:A0-l+1]
    zz,xx=np.mgrid[b0:B0+1,a0:A0+1]; extension=(xx<x)|(xx>X)|(zz<z)|(zz>Z)
    for key in ('ground','old_ground'): revised[key][target][extension]=measured[extension]
    revised['bounds']=np.asarray(bounds)
    for key,value in old.items():
        if key!='bounds' and not np.array_equal(revised[key][original],value): raise ValueError(('Original field changed',key))
    if int(revised['walk'].sum())!=int(old['walk'].sum()): raise ValueError('Expanded frame invented public pavement')
    shutil.copytree(a.previous,a.out)
    np.savez_compressed(a.out/'network.npz',**revised)
    report=dict(previous=str(a.previous),current_full_source=str(a.source),bounds=bounds,
                all_original_fields_exact=True,new_public_surface_claims=0,source_ground_columns=int(extension.sum()),
                planning_only=True,installed_authority=False,world_written=False)
    (a.out/'frame-extension.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('previous','source','out'): p.add_argument('--'+name,type=Path,required=True)
    extend(p.parse_args())
