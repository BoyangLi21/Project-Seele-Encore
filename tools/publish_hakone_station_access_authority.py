"""Record an installed, measured station access and its explicit retired roads."""
import argparse,json,shutil
from pathlib import Path
import numpy as np


def publish(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed' or not receipt['changed_section_readback'] or a.candidate.resolve()not in [Path(p).resolve()for p in receipt['candidates']]:raise ValueError('Matching installed-world receipt required')
    for name in ('functional-check.json','independent-check.json','station-access-check.json'):
        if json.loads((a.candidate/name).read_text('utf8'))['errors']:raise ValueError('Unverified station access')
    with np.load(a.previous/'network.npz')as f:g={k:f[k]for k in f.files}
    with np.load(a.candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    with np.load(a.candidate/'retired-western-approach.npz')as f:r={k:f[k]for k in f.files}
    if not np.array_equal(d['bounds'],r['bounds']):raise ValueError('Retirement extent mismatch')
    x,z,X,Z=map(int,d['bounds']);gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1];retired=r['retired']
    if not np.array_equal(g['grade2'][ar][retired],r['grade2'][retired]) or not g['walk'][ar][retired].all():raise ValueError('Retired street authority changed')
    editable=retired|(~g['walk'][ar]&d['walk'])
    for key in g:
        if key=='bounds':continue
        if key=='old_ground':
            # The candidate records the current terrain as its before image;
            # retain the larger authority's historical diagnostic baseline.
            if not np.array_equal(d[key],g['ground'][ar]):raise ValueError('Unexpected before-terrain reference')
            continue
        if not np.array_equal(g[key][ar][~editable],d[key][~editable]):raise ValueError(('Unrelated planning cell changed',key))
        g[key][ar]=d[key]
    shutil.copytree(a.previous,a.out);np.savez_compressed(a.out/'network.npz',**g)
    access=json.loads((a.candidate/'access-design.json').read_text('utf8'));row=access['station']
    catalog=json.loads((a.previous/'catalog.json').read_text('utf8'))
    if any(c['id']==row['id']for c in catalog):raise ValueError('Station access already registered')
    catalog.append(dict(id=row['id'],kind='station_access',use=row['station_id'],occupied_bounds=row['occupied_bounds'],door=[151,161,777],approach=row['approach'],destination=row['platform'],destination_type=row['destination_type'],installed_station_access=str(a.candidate)))
    (a.out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),'utf8')
    volumes=json.loads((a.previous/'station-volumes.json').read_text('utf8'));volumes.append(row['occupied_bounds'])
    (a.out/'station-volumes.json').write_text(json.dumps(volumes,indent=2),'utf8')
    report=dict(candidate=str(a.candidate),installation=str(a.installation),previous=str(a.previous),retired_disconnected_road_columns=int(retired.sum()),station_access=row,stacked_path_record=str(a.candidate/'station-access-check.json'),whole_map_complete=False)
    (a.out/'station-access-authority.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Registered installed station entrance and',int(retired.sum()),'physically superseded road columns')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('previous','candidate','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    publish(p.parse_args())
