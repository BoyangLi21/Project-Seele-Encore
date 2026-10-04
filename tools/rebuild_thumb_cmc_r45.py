"""Move the thumb saddle toward the carpal end while preserving the rest mesh."""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import matrices
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--proximal',type=float,default=.11);a=p.parse_args();shutil.copytree(a.candidate,a.out)
f=a.out/'hand_rig_contract.json';c=json.loads(f.read_text());name=f"eva_unit0{c['rig']}";gp=a.out/(name+'.geo.json');g=json.loads(gp.read_text());mp=a.out/(name+'_anatomical_hands_r45.mesh.json');m=json.loads(mp.read_text());bones={b['name']:b for b in g['minecraft:geometry'][0]['bones']};reports=[]
for side in ['l','r']:
 h=c['hands'][side];js=h['digits']['thumb']['joints'];original=matrices(g,c,side);before=np.array(js[0]['head_bind']);js[0]['head_bind']=(before-np.array(h['longitudinal_bind'])*a.proximal).tolist()
 for i,j in enumerate(js):
  b=bones[j['name']];pmat=matrices(g,c,side)[b['parent']];head=np.array(j['head_bind']);tip=np.array(j['tip_bind']);world=original[j['name']][:3,:3].copy()
  if i==0:
   y=tip-head;y/=np.linalg.norm(y);x=world[:,0]-y*(world[:,0]@y);x/=np.linalg.norm(x);world=np.column_stack([x,y,np.cross(x,y)])
  local=pmat[:3,:3].T@world;q=R.from_matrix(local);b['pivot']=((np.linalg.inv(pmat)@np.r_[head,1])[:3]*[-1,1,1]*16).tolist();b['rotation']=(q.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist();inv=np.linalg.inv(matrices(g,c,side)[j['name']]).T.reshape(-1).tolist();j.update(local_bind_quaternion_xyzw=q.as_quat().tolist(),neutral_local_quaternion_xyzw=q.as_quat().tolist(),inverse_bind_column_major=inv,length=float(np.linalg.norm(tip-head)))
  for skin in m['jointSkins'].values():
   if j['name']in skin['inverseBindColumnMajor']:skin['inverseBindColumnMajor'][j['name']]=inv
 reports.append(dict(side=side,old_cmc=before.tolist(),new_cmc=js[0]['head_bind'],new_metacarpal_length=js[0]['length']))
c['new_bones']=[copy.deepcopy(b)for b in g['minecraft:geometry'][0]['bones']if b['name'].startswith('r45_hand_')];c['cmc_diagnostic_r45']=dict(reports=reports,native_passed=False,visual_accepted=False)
f.write_text(json.dumps(c,indent=2),encoding='utf8');gp.write_text(json.dumps(g,indent=2),encoding='utf8');mp.write_text(json.dumps(m,separators=(',',':')),encoding='utf8');print(json.dumps(reports))
