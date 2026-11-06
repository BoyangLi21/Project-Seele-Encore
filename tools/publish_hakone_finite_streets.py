"""Publish only installed finite street retirements and measured forecourts."""
import argparse,json,shutil
from pathlib import Path
import numpy as np


def publish(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed'or not receipt['changed_section_readback']or a.candidate.resolve()not in[Path(v).resolve()for v in receipt['candidates']]:raise ValueError('Matching installed receipt required')
    for name in('functional-check.json','independent-check.json'):
        if json.loads((a.candidate/name).read_text('utf8'))['errors']:raise ValueError('Unverified streets')
    paths=json.loads((a.candidate/'street-journeys.json').read_text('utf8'))
    if not paths or any(not r['path']for r in paths):raise ValueError('Missing verified destination connection')
    native_curves=None
    if (a.candidate/'native-geometry/operations.json').exists():
        from verify_hakone_owakudani_release import require_verified
        from map_pipeline.native_geometry_patch import expected
        from native_transit_additions import assert_preserved
        from install_r53_carrier_trays import stopped_world
        require_verified(a.candidate)
        final,proof=expected(a.candidate)
        if receipt.get('native_geometry_migrations')!=[proof]:raise ValueError('Native installation receipt differs')
        with stopped_world(Path(receipt['world'])):assert_preserved(Path(receipt['world']),final)
        before=json.loads((a.previous/'native-curves.json').read_text('utf8'))
        native_curves=json.loads((a.candidate/'plan/native-curves.json').read_text('utf8'))
        verified=json.loads((a.candidate/'cable-station-independent-check.json').read_text('utf8'))
        if before['trains']!=native_curves['trains']or len(before['ropeway'])!=len(native_curves['ropeway']):raise ValueError('Unrelated native network changed')
        if [i for i,(p,q)in enumerate(zip(before['ropeway'],native_curves['ropeway']))if p!=q]!=verified['changed_native_curves']:raise ValueError('Unverified native curve change')
    with np.load(a.previous/'network.npz')as f:g={k:f[k]for k in f.files}
    with np.load(a.candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    with np.load(a.candidate/'finite-authority.npz')as f:v={k:f[k]for k in f.files}
    if not np.array_equal(d['bounds'],v['bounds']):raise ValueError('Finite extent differs')
    x,z,X,Z=map(int,d['bounds']);gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    if not np.array_equal(g['walk'][ar],v['before_walk'])or not np.array_equal(g['grade2'][ar],v['before_grade2']):raise ValueError('Current authority changed')
    retired,editable=v['retired'],v['editable']
    if not editable[retired].all()or d['walk'][retired].any():raise ValueError('Retirement remains public')
    for key in g:
        if key=='bounds':continue
        if key=='old_ground':
            if not np.array_equal(d[key],g['ground'][ar]):raise ValueError('Candidate before ground differs')
            continue
        if not np.array_equal(g[key][ar][~editable],d[key][~editable]):raise ValueError(('Unrelated authority cell changed',key))
        g[key][ar]=d[key]
    shutil.copytree(a.previous,a.out);np.savez_compressed(a.out/'network.npz',**g)
    if native_curves is not None:shutil.copy2(a.candidate/'plan/native-curves.json',a.out/'native-curves.json')
    report=dict(candidate=str(a.candidate),installation=str(a.installation),previous=str(a.previous),retired_columns=int(retired.sum()),finite_editable_columns=int(editable.sum()),journeys=[dict(name=r['name'],positions=len(r['path']),start=r['path'][0],end=r['path'][-1])for r in paths],whole_map_complete=False)
    (a.out/'finite-streets-authority.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('previous','candidate','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    publish(p.parse_args())
