"""Reuse the retained Unit-01 hand as a complete wrist-local module on Units00/02.

Skeleton, surface, inverse binds, controls and grip frames travel together.
Copying only angle tables between independently regenerated hands was invalid.
"""
from pathlib import Path
import copy,json
import numpy as np
from scipy.spatial.transform import Rotation
from author_anatomical_hand_rig_r45 import model_matrix

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'
OUT=ROOT/'artifacts/rebuild_r47/motion/coherent_hand_modules'

def point(m,p):return (m@np.r_[p,1])[:3].tolist()
def vector(m,p):return (m[:3,:3]@np.asarray(p)).tolist()

def main():
    source=json.loads((ASSETS/'hand_rigs/unit01/hand_rig_contract.json').read_text())
    source_geo=json.loads((ASSETS/'geo/eva_unit01.geo.json').read_text())
    source_mesh=json.loads((ASSETS/'mesh/eva_unit01_anatomical_hands_r45.mesh.json').read_text())
    sb={b['name']:b for b in source_geo['minecraft:geometry'][0]['bones']};reports=[]
    for rig in (0,2):
        out=OUT/f'unit0{rig}';out.mkdir(parents=True,exist_ok=True)
        path=ASSETS/f'hand_rigs/unit0{rig}/hand_rig_contract.json';old=json.loads(path.read_text())
        if old.get('coherent_wrist_module_r47',{}).get('complete_skeleton_skin_controls_and_grips_transferred'):
            reports.append(dict(rig=rig,already_coherent=True,existing_module_preserved=True))
            continue
        gp=ASSETS/f'geo/eva_unit0{rig}.geo.json';geo=json.loads(gp.read_text())
        mp=ASSETS/f'mesh/eva_unit0{rig}_anatomical_hands_r45.mesh.json';mesh=json.loads(mp.read_text())
        for name,data in [('before_contract.json',old),('before_geo.json',geo),('before_mesh.json',mesh)]:
            if not (out/name).exists():(out/name).write_text(json.dumps(data))
        bones=geo['minecraft:geometry'][0]['bones'];bones[:]=[b for b in bones if not b['name'].startswith('r45_hand_')]
        tb={b['name']:b for b in bones};c=copy.deepcopy(source);c['rig']=rig;c['new_bones']=[]
        transforms={}
        for side in ('l','r'):
            parent='hand_'+side;sp=np.asarray(sb[parent]['pivot'])*[-1,1,1]/16;tp=np.asarray(tb[parent]['pivot'])*[-1,1,1]/16
            delta=tp-sp;shift=np.eye(4);shift[:3,3]=delta
            sf=model_matrix(sb,parent,{});tf=model_matrix(tb,parent,{})
            transform=tf@shift@np.linalg.inv(sf);transforms[side]=transform
            for b in source['new_bones']:
                if not b['name'].startswith('r45_hand_'+side+'_'):continue
                new=copy.deepcopy(b);new['pivot']=(np.asarray(b['pivot'])+delta*[-1,1,1]*16).tolist()
                bones.append(new);tb[new['name']]=new;c['new_bones'].append(new)
            hand=c['hands'][side]
            for key in ('palmar_normal_bind','longitudinal_bind'):hand[key]=vector(transform,hand[key])
            for digit in hand['digits'].values():
                for joint in digit['joints']:
                    for key in ('head_bind','tip_bind'):joint[key]=point(transform,joint[key])
                    bind=model_matrix(tb,joint['name'],{});joint['inverse_bind_column_major']=np.linalg.inv(bind).T.reshape(-1).tolist()
            name='hand_'+side;part=copy.deepcopy(source_mesh['parts'][name]);raw=np.asarray(part['vertices']).reshape(-1,source_mesh['stride'])
            vertices=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
            vertices=vertices@transform[:3,:3].T+transform[:3,3]
            pivot=np.asarray(tb[parent]['pivot']);raw[:,:3]=vertices*[-1,1,1]*16-pivot
            normals=(raw[:,5:8]*[-1,1,1])@transform[:3,:3].T;raw[:,5:8]=normals*[-1,1,1]
            part['pivot']=pivot.tolist();part['vertices']=raw.reshape(-1).tolist();mesh['parts'][name]=part
            skin=copy.deepcopy(source_mesh['jointSkins'][name])
            skin['inverseBindColumnMajor']={n:np.linalg.inv(model_matrix(tb,n,{})).T.reshape(-1).tolist()for n in skin['influences']}
            corrective=skin.get('contactCorrectiveR45')
            if corrective:
                rows=np.asarray(corrective['vertex_index_position_normal_delta']);rows[:,1:4]=rows[:,1:4]@transform[:3,:3].T;rows[:,4:7]=rows[:,4:7]@transform[:3,:3].T
                corrective['vertex_index_position_normal_delta']=rows.tolist()
            mesh['jointSkins'][name]=skin
            for channel in ('weapon_grip_frames','cannon_grip_frames'):
                grip=c[channel][side];grip['palm_bind']=point(transform,grip['palm_bind'])
                for key in ('along_bind','across_bind'):grip[key]=vector(transform,grip[key])
                adjustment=grip.get('pose_adjustment_r45')
                if adjustment:
                    tr=Rotation.from_matrix(transform[:3,:3]);adjustment['rotation_xyzw']=(tr*Rotation.from_quat(adjustment['rotation_xyzw'])*tr.inv()).as_quat().tolist()
                    adjustment['translation_native']=vector(transform,adjustment['translation_native'])
        transform=transforms['r'];knife=c['knife_attachment_r45'];knife['target_handle_centre']=point(transform,knife['target_handle_centre'])
        knife['rotation_xyzw']=(Rotation.from_matrix(transform[:3,:3])*Rotation.from_quat(knife['rotation_xyzw'])).as_quat().tolist()
        knife['source_mesh']='progressive_knife_anatomical_r45.mesh.json'
        if rig==2:
            # The retained long sword is rebound separately against this same
            # master module; never inherit an old hand's prop coordinates.
            c['pose_controls']['sword_right']=copy.deepcopy(old['pose_controls']['sword_right'])
            c['pose_controls']['sword_right']['thumb']=copy.deepcopy(source['pose_controls']['knife']['thumb'])
            c['sword_attachment_r45']=copy.deepcopy(old['sword_attachment_r45'])
            c['sword_attachment_r45']['rotation_xyzw']=copy.deepcopy(knife['rotation_xyzw'])
            c['sword_attachment_r45']['target_handle_centre']=(np.asarray(knife['target_handle_centre'])+np.asarray(c['hands']['r']['palmar_normal_bind'])*.04).tolist()
        c['coherent_wrist_module_r47']=dict(source_unit=1,geometry_triangles_preserved=True,complete_skeleton_skin_controls_and_grips_transferred=True,knife_existing_asset_reused=True,visual_accepted=False)
        for name,data,target in [('hand_rig_contract.json',c,path),(f'eva_unit0{rig}.geo.json',geo,gp),(f'eva_unit0{rig}_anatomical_hands_r45.mesh.json',mesh,mp)]:
            payload=json.dumps(data,indent=2 if not name.endswith('.mesh.json')else None);(out/name).write_text(payload);target.write_text(payload)
        reports.append(dict(rig=rig,joints=len(c['new_bones']),source_hand_triangles=sum(len(v['vertices'])//source_mesh['stride']//3 for v in source_mesh['parts'].values()),body_bones_changed=False,hand_topology_changed=False))
    report_path=OUT/('latest_prepare.json' if all(r.get('already_coherent') for r in reports) else 'report.json')
    report_path.write_text(json.dumps(reports,indent=2));print(json.dumps(reports))

if __name__=='__main__':main()
