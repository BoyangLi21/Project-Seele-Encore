"""Sample only the current delivered rigid attachments and anatomical skin."""
from pathlib import Path
import json,shutil
import numpy as np
from scipy.spatial.transform import Rotation
from eva_hand_rig_math_r45 import controls,matrices
from rebind_anatomical_hand_r45 import dq_pose

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'
OUT=ROOT/'artifacts/rebuild_r47/motion/current_weapon_contacts'

def main():
    for rig,kind,weapon in [(0,'knife','progressive_knife.mesh.json'),(1,'knife','progressive_knife_anatomical_r45.mesh.json'),(2,'knife','eva02_knife.mesh.json'),(2,'sword','eva02_longsword.mesh.json')]:
        base=OUT/f'unit0{rig}_{kind}';base.mkdir(parents=True,exist_ok=True)
        contract=json.loads((ASSETS/f'hand_rigs/unit0{rig}/hand_rig_contract.json').read_text())
        weapon=Path(contract[kind+'_attachment_r45']['source_mesh']).name
        geo=json.loads((ASSETS/f'geo/eva_unit0{rig}.geo.json').read_text())
        hand=json.loads((ASSETS/f'mesh/eva_unit0{rig}_anatomical_hands_r45.mesh.json').read_text())
        skin=hand['jointSkins']['hand_r'];part=hand['parts']['hand_r']
        raw=np.asarray(part['vertices']).reshape(-1,hand['stride'])
        vertices=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
        names=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in names]).T
        pose=controls(contract,'knife' if kind=='knife' else 'sword_right','r')
        ms=matrices(geo,contract,'r',pose)
        transforms=[ms[n]@np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
        posed=dq_pose(vertices,weights,transforms)
        mesh=json.loads((ASSETS/'mesh'/weapon).read_text());wp=mesh['parts']['knife' if kind=='knife' else 'lance']
        points=(np.asarray(wp['vertices']).reshape(-1,mesh['stride'])[:,:3]+wp['pivot'])*[-1,1,1]/16
        attachment=contract[kind+'_attachment_r45']
        q=Rotation.from_quat(attachment['rotation_xyzw']).as_matrix()
        points=(points-attachment['source_handle_centre'])@q.T+attachment['target_handle_centre']
        (base/'hand_rig_contract.json').write_text(json.dumps(contract,indent=2))
        (base/f'eva_unit0{rig}.geo.json').write_text(json.dumps(geo))
        (base/f'eva_unit0{rig}_anatomical_hands_r45.mesh.json').write_text(json.dumps(hand))
        np.savez_compressed(base/'attachment.npz',hand=posed,normal=contract['hands']['r']['palmar_normal_bind'],along=contract['hands']['r']['longitudinal_bind'],**{kind:points})
        print(f'unit0{rig} {kind}: {len(posed)//3} hand triangles, {len(points)//3} unchanged weapon triangles')

if __name__=='__main__':main()
