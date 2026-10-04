"""Compare explicit wide-foreend support poses in a frozen native gun frame.

No optimization, geometry replacement, or runtime installation. Each proposal
is independently surface-tested and visually reviewed before selection.
"""
from pathlib import Path
import argparse, copy, json
import numpy as np
from eva_hand_rig_math_r45 import controls, matrices, contact_corrective
from rebind_anatomical_hand_r45 import dq_pose

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--pad',type=float,nargs=3,help='Measured raw cannon-space palm contact')
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
provenance=json.loads((a.input/'provenance.json').read_text('utf8'))
source=Path(provenance['candidate']);c=json.loads((source/'hand_rig_contract.json').read_text('utf8'))
name=f"eva_unit0{c['rig']}";geo=json.loads((source/(name+'.geo.json')).read_text('utf8'))
mesh=json.loads((source/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
side='l';hand='hand_l';part=mesh['parts'][hand];skin=mesh['jointSkins'][hand]
rest=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T
inverse=[np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
data=np.load(a.input/'l_geometry.npz')
translation=np.zeros(3)
if a.pad:
    gun_path=Path(__file__).resolve().parents[1]/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/positron_cannon.mesh.json'
    import hashlib
    assert hashlib.sha256(gun_path.read_bytes()).hexdigest()==provenance['gun_sha256']
    raw=np.asarray(json.loads(gun_path.read_text('utf8'))['parts']['cannon']['vertices']).reshape(-1,8)[:,:3]
    raw_to_hand=np.linalg.lstsq(np.c_[raw,np.ones(len(raw))],data['weapon'],rcond=None)[0]
    assert np.abs(np.c_[raw,np.ones(len(raw))]@raw_to_hand-data['weapon']).max()<1e-5
    translation=np.r_[a.pad,1]@raw_to_hand-np.asarray(c['cannon_grip_frames']['l']['palm_bind'])
poses={n:copy.deepcopy(c['pose_controls'][n])for n in ['open','support','relaxed']}
poses['foreend_cradle']=dict(fingers=[5,25,15],thumb=[[0,0,18],[10,0,0],[5,0,0]],cup_ring=[0],cup_little=[0],splay=dict(index=-3,middle=0,ring=3,little=6))
poses['foreend_thumb_open']=dict(poses['foreend_cradle'],thumb=[[0,0,30],[4,0,0],[0,0,0]])
for label,pose in poses.items():
    cc=copy.deepcopy(c);cc['pose_controls']['support_proposal']=pose
    values=controls(cc,'support_proposal',side);ms=matrices(geo,cc,side,values)
    surface=dq_pose(rest,weights,[ms[n]@iv for n,iv in zip(palette,inverse)])
    surface=contact_corrective(geo,skin,surface,ms,hand)
    target=a.out/label;target.mkdir()
    np.savez_compressed(target/'proposal.npz',hand=surface+translation,weapon=data['weapon'],baseline=data['baseline'])
    (target/'proposal.json').write_text(json.dumps(dict(native_source=provenance,side=side,
        controls={k:v.tolist()for k,v in values.items()},pose=pose,
        translation_native=translation.tolist(),raw_cannon_pad=a.pad,local_rotation_xyzw=[0,0,0,1],
        unchanged_weapon=True,native_tested=False,visual_accepted=False),indent=2),'utf8')
print(len(poses),'explicit palm support comparisons written; none installed.')
