"""Measure a separate sword grip on Unit-02's actual posed anatomical hand."""
from pathlib import Path
import argparse,json,shutil,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices
from rebind_anatomical_hand_r45 import dq_pose

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--sword',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    shutil.copytree(a.candidate,a.out);file=a.out/'hand_rig_contract.json';c=json.loads(file.read_text());assert c['rig']==2
    h=c['hands']['r'];roots=np.array([h['digits'][n]['joints'][0]['head_bind']for n in ['index','middle','ring','little']])
    normal=np.array(h['palmar_normal_bind']);along=np.array(h['longitudinal_bind']);across=roots[0]-roots[-1];across-=normal*(normal@across);across/=np.linalg.norm(across)
    y=-across;z=np.cross(normal,y);z/=np.linalg.norm(z);x=np.cross(y,z);rotation=np.column_stack([x,y,z]);assert np.linalg.det(rotation)>.999
    sword=json.loads(a.sword.read_text());part=sword['parts']['lance'];vertices=np.array(part['vertices']).reshape(-1,8)
    source=(np.array(part['pivot'])+[0,3.5,0])*[-1,1,1]/16;target=roots.mean(0)-along*.06+normal*.18
    blade_base=(np.array(part['pivot'])+[0,-12,0])*[-1,1,1]/16;blade_tip=(np.array(part['pivot'])+[0,-98,0])*[-1,1,1]/16
    c['sword_attachment_r45']=dict(rotation_xyzw=R.from_matrix(rotation).as_quat().tolist(),source_handle_centre=source.tolist(),target_handle_centre=target.tolist(),
        source_mesh=str(a.sword),source_mesh_sha256=hashlib.sha256(a.sword.read_bytes()).hexdigest(),mesh_part='lance',grip_side='r',intended_variant=2,
        blade_base_bind=blade_base.tolist(),blade_tip_bind=blade_tip.tolist(),blade_radius_native=.30,
        blade_points_to_index_in_forward_grip=True,native_passed=False,skin_contact_passed=False)
    file.write_text(json.dumps(c,indent=2));name='eva_unit02';g=json.loads((a.out/(name+'.geo.json')).read_text());mesh=json.loads((a.out/(name+'_anatomical_hands_r45.mesh.json')).read_text())
    handpart=mesh['parts']['hand_r'];skin=mesh['jointSkins']['hand_r'];raw=np.array(handpart['vertices']).reshape(-1,8);points=(raw[:,:3]+handpart['pivot'])*[-1,1,1]/16
    palette=list(skin['influences']);weights=np.array([skin['influences'][n]for n in palette]).T;ms=matrices(g,c,'r',controls(c,'knife','r'))
    posed=dq_pose(points,weights,[ms[n]@np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette])
    weapon=((vertices[:,:3]+part['pivot'])*[-1,1,1]/16-source)@rotation.T+target
    np.savez_compressed(a.out/'sword_grip_preview.npz',hand=posed,sword=weapon,normal=normal,along=along)
    print(json.dumps(c['sword_attachment_r45']))

if __name__=='__main__':main()
