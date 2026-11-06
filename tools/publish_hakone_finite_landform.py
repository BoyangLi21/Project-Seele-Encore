"""Publish installed finite soil heights while preserving every route and parcel."""
import argparse,json,shutil
from pathlib import Path
import numpy as np


def publish(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed'or not receipt['changed_section_readback']or a.candidate.resolve()not in[Path(v).resolve()for v in receipt['candidates']]:raise ValueError('Matching installed receipt required')
    for name in('functional-check.json','independent-check.json'):
        if json.loads((a.candidate/name).read_text('utf8'))['errors']:raise ValueError('Unverified terrain')
    with np.load(a.previous/'network.npz')as f:g={k:f[k]for k in f.files}
    with np.load(a.candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    with np.load(a.candidate/'finite-landform-authority.npz')as f:v={k:f[k]for k in f.files}
    if not np.array_equal(d['bounds'],v['bounds']):raise ValueError('Finite extent differs')
    x,z,X,Z=map(int,d['bounds']);gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    if not np.array_equal(g['ground'][ar],v['before_ground']):raise ValueError('Current authority ground changed')
    for key in g:
        if key=='bounds':continue
        if key=='old_ground':
            if not np.array_equal(d[key],g['ground'][ar]):raise ValueError('Candidate before ground differs')
            continue
        if key!='ground':
            if not np.array_equal(g[key][ar],d[key]):raise ValueError(('Route or parcel authority changed',key))
            continue
        if not np.array_equal(g[key][ar][~v['editable']],d[key][~v['editable']]):raise ValueError('Unrelated ground changed')
        g[key][ar]=d[key]
    shutil.copytree(a.previous,a.out);np.savez_compressed(a.out/'network.npz',**g)
    report=dict(candidate=str(a.candidate),installation=str(a.installation),previous=str(a.previous),ground_columns=int(v['editable'].sum()),roads_catalog_and_native_geometry_unchanged=True,whole_map_complete=False)
    (a.out/'finite-landform-authority.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('previous','candidate','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    publish(p.parse_args())
