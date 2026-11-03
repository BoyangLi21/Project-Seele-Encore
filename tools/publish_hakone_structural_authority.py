"""Update finite installed structural deltas in the existing planning authority."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR
from hakone_earthworks import road_blocks
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed'or not receipt['changed_section_readback']:raise ValueError('Read-back installed map required')
    installed={Path(p).resolve()for p in receipt['candidates']}
    if not {p.resolve()for p in a.candidate}<=installed:raise ValueError('Wrong candidate receipt')
    shutil.copytree(a.previous,a.out)
    with np.load(a.previous/'network.npz')as f:g={k:f[k]for k in f.files}
    x,z,X,Z=map(int,g['bounds']);retired=0
    prior=a.previous/'structural-feedback-authority.json'
    spaces=json.loads(prior.read_text('utf8')).get('additional_supported_spaces',[])if prior.exists()else[]
    for C in a.candidate:
        e=Editor(C);cols=set()
        for file in (C/'delta').glob('*.npz'):
            with np.load(file)as f:
                for i,(cx,cz)in enumerate(f['coordinates']):
                    lo,hi=f['ranges'][i:i+2]
                    for off in np.unique(f['indices'][lo:hi]%256):cols.add((int(cx*16+off%16),int(cz*16+off//16)))
        for px,pz in cols:
            if not(x<=px<=X and z<=pz<=Z):continue
            iz,ix=pz-z,px-x
            if not g['walk'][iz,ix]:continue
            floor,_=road_blocks(g['grade2'][iz,ix]);floor=int(floor)
            if e.state(px,floor,pz).split('[')[0]in PAVEMENT and all(e.state(px,y,pz).split('[')[0]in AIR|{'minecraft:light','minecraft:grass','minecraft:fern'}for y in (floor+1,floor+2)):continue
            for k in ('road','walk','marking','tunnel'):g[k][iz,ix]=False
            retired+=1
        with np.load(C/'plan/network.npz')as f:
            ox,oz,oX,oZ=map(int,f['bounds']);l,t,r,b=max(x,ox),max(z,oz),min(X,oX),min(Z,oZ)
            if l<=r and t<=b:
                dst=np.s_[t-z:b-z+1,l-x:r-x+1];src=np.s_[t-oz:b-oz+1,l-ox:r-ox+1]
                for k in ('ground','old_ground'):g[k][dst]=f[k][src]
                # A verified public stair supplies its own finite elevations.
                # Do not reserve the rest of its vertical columns as structures.
                functional=json.loads((C/'functional-check.json').read_text('utf8'))
                if 'door_and_street_contacts'in functional:
                    if functional['errors']:raise ValueError('Unverified public stair')
                    public=f['walk'][src]
                    for k in ('walk','grade2'):
                        target=g[k][dst];target[public]=f[k][src][public]
                    for k in ('road','marking','tunnel'):g[k][dst][public]=False
                    spaces.append(dict(id='sounzan-connected-outdoor-stair',candidate=str(C),footprint_plan=str(C/'plan/network.npz'),contacts=functional['door_and_street_contacts']))
        if 'sniper'in C.name:spaces.append(dict(id='expanded-yashima-forecourt',candidate=str(C),floor=174,footprint_plan=str(C/'plan/network.npz'),mechanical_well_exclusions=json.loads((C/'design.json').read_text('utf8'))['well_volumes']))
    np.savez_compressed(a.out/'network.npz',**g)
    report=dict(installation=str(a.installation),retired_invalid_old_walk_columns=retired,additional_supported_spaces=spaces,whole_map_acceptance=False)
    (a.out/'structural-feedback-authority.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('previous','out','installation'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--candidate',type=Path,action='append',required=True)
    run(p.parse_args())
