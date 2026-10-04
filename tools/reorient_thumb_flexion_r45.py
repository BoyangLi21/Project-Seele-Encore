"""Rebind thumb roll to its own flexion plane without moving the rest surface."""
from pathlib import Path
import argparse, copy, json, shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import matrices

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--distal-only',action='store_true');p.add_argument('--roll-degrees',type=float);a=p.parse_args()
shutil.copytree(a.candidate,a.out)
cpath=a.out/'hand_rig_contract.json';c=json.loads(cpath.read_text());name=f"eva_unit0{c['rig']}"
gpath=a.out/(name+'.geo.json');g=json.loads(gpath.read_text());mpath=a.out/(name+'_anatomical_hands_r45.mesh.json');m=json.loads(mpath.read_text())
bones={b['name']:b for b in g['minecraft:geometry'][0]['bones']};audit=[]
def unit(x):return x/np.linalg.norm(x)
for side in ['l','r']:
 h=c['hands'][side];joints=h['digits']['thumb']['joints'];mirror=1 if side=='l'else -1
 # Thumb flexion closes toward the radial index, not toward the palm normal
 # used for the four parallel fingers. This defines roll from real bind joints.
 target=np.asarray(h['digits']['index']['joints'][0]['head_bind']);original_bind=matrices(g,c,side)
 for j in joints[1:] if a.distal_only else joints:
  before=matrices(g,c,side);b=bones[j['name']];parent=before[b['parent']]
  head=np.asarray(j['head_bind']);y=unit(np.asarray(j['tip_bind'])-head)
  toward=target-head;toward=unit(toward-y*np.dot(toward,y))
  x=unit(np.cross(toward,y));z=unit(np.cross(x,y));world=np.column_stack([x,y,z])
  if a.roll_degrees is not None:world=original_bind[j['name']][:3,:3]@R.from_euler('y',a.roll_degrees*mirror,degrees=True).as_matrix()
  local=parent[:3,:3].T@world;q=R.from_matrix(local)
  b['pivot']=((np.linalg.inv(parent)@np.r_[head,1])[:3]*[-1,1,1]*16).tolist()
  b['rotation']=(q.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist()
  old=before[j['name']][:3,:3]
  after=matrices(g,c,side)[j['name']];inverse=np.linalg.inv(after).T.reshape(-1).tolist()
  j.update(local_bind_quaternion_xyzw=q.as_quat().tolist(),neutral_local_quaternion_xyzw=q.as_quat().tolist(),inverse_bind_column_major=inverse)
  for skin in m['jointSkins'].values():
   if j['name'] in skin['inverseBindColumnMajor']:skin['inverseBindColumnMajor'][j['name']]=inverse
  audit.append(dict(bone=j['name'],roll_change_degrees=float(np.degrees(R.from_matrix(old.T@world).magnitude()))))
c['new_bones']=[copy.deepcopy(b)for b in g['minecraft:geometry'][0]['bones']if b['name'].startswith('r45_hand_')]
c['thumb_axis_rebind']=dict(method='Independent thumb flexion plane from radial-index anatomy; rest surface and joint centres preserved',audit=audit,visual_passed=False)
# Old thumb poses were authored against the wrong axes; do not call them valid.
for pose in c['pose_controls'].values():
 for n in list(pose.get('bone_angles',{})):
  if '_thumb_' in n:pose['bone_angles'].pop(n)
gpath.write_text(json.dumps(g,indent=2),encoding='utf8');mpath.write_text(json.dumps(m,separators=(',',':')),encoding='utf8');cpath.write_text(json.dumps(c,indent=2),encoding='utf8')
print(json.dumps(audit))
