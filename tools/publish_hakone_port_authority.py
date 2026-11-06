"""Publish the installed port's finite roads without treating ship decks as terrain."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from compose_hakone_port_relocation import field
from prepare_hakone_main_terrain import sample_grid
from hakone_earthworks import road_blocks
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR


def run(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    check=json.loads((a.candidate/'port-independent-check.json').read_text('utf8'))
    if receipt['status']!='installed' or not receipt['changed_section_readback'] or check['errors']:
        raise ValueError('Verified installed port required')
    if a.candidate.resolve() not in {Path(p).resolve() for p in receipt['candidates']}:
        raise ValueError('Candidate does not match installation')
    with np.load(a.previous/'network.npz') as f:old={k:f[k] for k in f.files}
    x,z,X,Z=map(int,old['bounds']);newX=max(X,3391);shape=(Z-z+1,newX-x+1)
    d={k:np.zeros(shape,v.dtype) for k,v in old.items() if k!='bounds'}
    for k in d:d[k][:,:X-x+1]=old[k]
    # The sampled terrain field is only a base for the newly extended frame.
    # Explicit earthwork targets below are the installed local authority.
    terrain=field(a.resource)
    zz,xx=np.mgrid[z:Z+1,X+1:newX+1]
    heights=np.floor(sample_grid(terrain,'height',xx,zz)).astype(np.int16)
    for k in ('ground','old_ground'):d[k][:,X-x+1:]=heights
    d['bounds']=np.asarray([x,z,newX,Z]);e=Editor(a.candidate);retired=0
    box=json.loads((a.candidate/'plan/relocation.json').read_text('utf8'))['source_bounds']
    for j,i in np.argwhere(d['walk'][box[2]-z:box[5]-z+1,box[0]-x:box[3]-x+1]):
        px,pz=int(i+box[0]),int(j+box[2]);iz,ix=pz-z,px-x
        h,half=road_blocks(d['grade2'][iz,ix]);h=int(h);s=e.state(px,h,pz)
        if s.split('[')[0] in PAVEMENT and ('type=bottom' in s)==bool(half) and all(e.state(px,Y,pz).split('[')[0] in AIR|{'minecraft:light','minecraft:grass','minecraft:fern'} for Y in (h+1,h+2)):
            continue
        for k in ('walk','road','marking','tunnel'):d[k][iz,ix]=False
        retired+=1
    paths=[a.candidate/'plan/port-coast-earthworks.npz',a.candidate/'plan/former-port-earthworks.npz']+sorted((a.candidate/'earthworks').glob('*.npz'))
    public=0
    for p in paths:
        with np.load(p) as f:
            ox,oz,oX,oZ=map(int,f['bounds']);area=np.s_[oz-z:oZ-z+1,ox-x:oX-x+1]
            active=f['active']
            for k in ('ground','old_ground'):d[k][area][active]=f['target'][active]
            if 'walk' not in f.files:continue
            mask=f['walk'];public+=int(mask.sum())
            for k in ('walk','road','grade2'):d[k][area][mask]=f[k][mask]
            for k in ('marking','tunnel'):d[k][area][mask]=False
    # Later corridor refinements are authoritative at their finite overlaps.
    with np.load(a.candidate/'plan/port-access.npz') as f:
        ox,oz,oX,oZ=map(int,f['bounds']);area=np.s_[oz-z:oZ-z+1,ox-x:oX-x+1];mask=f['walk']
        for k in ('walk','road','grade2'):d[k][area][mask]=f[k][mask]
    e.regions.clear()
    shutil.copytree(a.previous,a.out)
    np.savez_compressed(a.out/'network.npz',**d)
    # The harbour contains vertically overlapping ship decks and gangways.
    # Retain its independently checked 3-D graph as a separate public space,
    # rather than flattening it into the one-height-per-column street frame.
    report=dict(installation=str(a.installation),candidate=str(a.candidate),previous=str(a.previous),bounds_xz=d['bounds'].tolist(),retired_old_port_columns=retired,corridor_columns=public,port_destinations=check['destinations'],port_3d_graph=dict(public_nodes=check['public_nodes'],reachable_public_nodes=check['reachable_public_nodes'],check=str(a.candidate/'port-independent-check.json')),terrain_uses_explicit_earthworks=True,ship_decks_not_terrain=True,native_curves_unchanged=True,whole_map_acceptance=False)
    (a.out/'port-authority.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('port_destinations','port_3d_graph')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('previous','candidate','installation','resource','out'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
