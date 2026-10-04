"""Construct the right hand by exact geometric reflection, not a 180deg turn.

World reflection M and local reflection L are both diag(-1,1,1). M*R*L
keeps every bone frame right-handed; flex keeps its sign, splay/twist reverse.
"""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_anatomical_hand_rig_r45 import model_matrix

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text());name=f"eva_unit0{c['rig']}";geo=json.loads((a.candidate/(name+'.geo.json')).read_text());mesh=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text());bs=geo['minecraft:geometry'][0]['bones'];bs[:]=[b for b in bs if not b['name'].startswith('r45_hand_r_')];bones={b['name']:b for b in bs};cache={};M=np.diag([-1.,1,1]);c['hands']['r']=copy.deepcopy(c['hands']['l']);c['hands']['r']['parent']='hand_r';c['new_bones']=[b for b in c['new_bones']if not b['name'].startswith('r45_hand_r_')]
for key in ['palmar_normal_bind','longitudinal_bind']:c['hands']['r'][key]=(M@np.asarray(c['hands']['l'][key])).tolist()
for digit,d in sorted(c['hands']['l']['digits'].items(),key=lambda item:(not item[0].startswith('cup_'),item[0])):
 parent=bones[d['joints'][0]['name']]['parent'].replace('r45_hand_l_','r45_hand_r_').replace('hand_l','hand_r');records=[]
 for left in d['joints']:
  n=left['name'].replace('r45_hand_l_','r45_hand_r_');head=M@np.asarray(left['head_bind']);tail=M@np.asarray(left['tip_bind']);frame=M@model_matrix(bones,left['name'],cache)[:3,:3]@M;pm=model_matrix(bones,parent,cache);pivot=(np.linalg.inv(pm)@np.r_[head,1])[:3];local=pm[:3,:3].T@frame;q=R.from_matrix(local)
  spec=dict(name=n,parent=parent,pivot=(pivot*[-1,1,1]*16).tolist(),rotation=(q.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist());bs.append(spec);bones[n]=spec;bind=model_matrix(bones,n,cache);c['new_bones'].append(spec)
  record=copy.deepcopy(left);record.update(name=n,head_bind=head.tolist(),tip_bind=tail.tolist(),local_bind_quaternion_xyzw=q.as_quat().tolist(),neutral_local_quaternion_xyzw=q.as_quat().tolist(),inverse_bind_column_major=np.linalg.inv(bind).T.reshape(-1).tolist());records.append(record);parent=n
 c['hands']['r']['digits'][digit]['joints']=records
left=mesh['parts']['hand_l'];raw=np.asarray(left['vertices']).reshape(-1,8);lp=np.asarray(left['pivot']);rp=np.asarray(bones['hand_r']['pivot']);points=(raw[:,:3]+lp)*[-1,1,1]/16;points=points@M.T;normals=(raw[:,5:8]*[-1,1,1])@M.T;result=raw.copy();result[:,:3]=points*[-1,1,1]*16-rp;result[:,5:8]=normals*[-1,1,1];order=np.arange(len(raw)).reshape(-1,3)[:,[0,2,1]].reshape(-1)
mesh['parts']['hand_r']=dict(pivot=rp.tolist(),vertices=np.round(result[order],7).reshape(-1).tolist())
rename=lambda n:n.replace('r45_hand_l_','r45_hand_r_').replace('hand_l','hand_r').replace('forearm_l','forearm_r')
influences={rename(n):np.asarray(w)[order].tolist()for n,w in mesh['jointSkins']['hand_l']['influences'].items()};mesh['jointSkins']['hand_r']=dict(influences=influences,inverseBindColumnMajor={n:np.linalg.inv(model_matrix(bones,n,cache)).T.reshape(-1).tolist()for n in influences})
for pose in c['pose_controls'].values():
 table=pose.get('bone_angles',{})
 for n,angles in list(table.items()):
  if n.startswith('r45_hand_l_'):table[rename(n)]=angles.copy()
c['construction']['mirror_contract']='Exact X reflection of left mesh and joint centres. World/frame reflection M*R*M preserves proper rotations. Runtime mirrors twist/splay, not flex.'
for f,data in [(name+'.geo.json',geo),(name+'_anatomical_hands_r45.mesh.json',mesh),('hand_rig_contract.json',c)]:
 (a.out/f).write_text(json.dumps(data,indent=2 if not f.endswith('.mesh.json')else None),'utf8')
print('Right hand reflected from exact left geometry,15joint frames and skin weights; winding corrected')
