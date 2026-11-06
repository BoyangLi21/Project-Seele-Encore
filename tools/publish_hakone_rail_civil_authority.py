"""Publish a verified installed civil/road frame without changing building identities."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from install_r53_carrier_trays import stopped_world
from native_transit_additions import assert_preserved
from map_pipeline.native_geometry_patch import expected


def publish(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed' or not receipt['changed_section_readback']:raise ValueError('Verified installation required')
    if [a.candidate.resolve()]!=[Path(p).resolve() for p in receipt['candidates']]:raise ValueError('Installation belongs to a different composed candidate')
    if json.loads((a.candidate/'independent-check.json').read_text('utf8'))['errors']:raise ValueError('Independent geometry check failed')
    final,native=expected(a.candidate)
    with stopped_world(Path(receipt['world'])):assert_preserved(Path(receipt['world']),final)
    with np.load(a.previous/'network.npz') as f:g={k:f[k] for k in f.files}
    with np.load(a.candidate/'plan/network.npz') as f:d={k:f[k] for k in f.files}
    gx,gz,gX,gZ=map(int,g['bounds']);x,z,X,Z=map(int,d['bounds'])
    if not(gx<=x<=X<=gX and gz<=z<=Z<=gZ):raise ValueError('Civil planning crop outside authority')
    area=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    for key in g:
        if key!='bounds' and key in d:g[key][area]=d[key]
    shutil.copytree(a.previous,a.out)
    np.savez_compressed(a.out/'network.npz',**g)
    shutil.copy2(a.candidate/'plan/native-curves.json',a.out/'native-curves.json')
    report=dict(previous=str(a.previous),candidate=str(a.candidate),installation=str(a.installation),
                catalog_and_building_positions_unchanged=True,native_geometry=native,public_columns=int(d['walk'].sum()),
                whole_map_complete=False,global_legacy_connectivity_report_requires_refresh=True)
    (a.out/'rail-civil-authority.json').write_text(json.dumps(report,indent=2),'utf8')
    print('Published installed railway and road planning frame; building catalog unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('previous','candidate','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    publish(p.parse_args())
