"""Structural mesh/rig preflight with historical negative controls; not art QA."""
from pathlib import Path
import argparse,json
import numpy as np
from author_anatomical_hand_rig_r45 import model_matrix
from eva_hand_rig_math_r45 import controls,joint_points

def validate(path):
 path=Path(path);c=json.loads((path/'hand_rig_contract.json').read_text(encoding='utf8'));name=f"eva_unit0{c['rig']}";g=json.loads((path/(name+'.geo.json')).read_text(encoding='utf8'));m=json.loads((path/(name+'_anatomical_hands_r45.mesh.json')).read_text(encoding='utf8'));bones={b['name']:b for b in g['minecraft:geometry'][0]['bones']};cache={};issues=[];maximum_frame_error=0;maximum_plane_error=0
 for side,h in c['hands'].items():
  n=np.asarray(h['palmar_normal_bind']);along=np.asarray(h['longitudinal_bind']);across=np.asarray(h['digits']['index']['joints'][0]['head_bind'])-h['digits']['little']['joints'][0]['head_bind'];across-=along*(across@along);across/=np.linalg.norm(across);plane=abs(float(n@across));maximum_plane_error=max(maximum_plane_error,plane)
  if plane>1e-4:issues.append(f'{side}: finger flexion normal differs from the actual knuckle plane, dot={plane}')
  for digit,d in h['digits'].items():
   for j in d['joints']:
    b=bones[j['name']];pivot=np.asarray(b['pivot'])*[-1,1,1]/16;bind=model_matrix(bones,j['name'],cache);actual=(bind@np.r_[pivot,1])[:3];error=float(np.linalg.norm(actual-j['head_bind']));maximum_frame_error=max(maximum_frame_error,error)
    if error>1e-5:issues.append(j['name']+': declared joint does not match actual geometry pivot')
    if abs(np.linalg.norm(np.asarray(j['tip_bind'])-j['head_bind'])-j['length'])>1e-5:issues.append(j['name']+': length mismatch')
 for part,skin in m['jointSkins'].items():
  raw=np.asarray(m['parts'][part]['vertices']);assert np.isfinite(raw).all()and raw.size%24==0
  w=np.asarray(list(skin['influences'].values()))
  if not np.isfinite(w).all()or np.min(w)<0 or np.max(w)>1:issues.append(part+': influence outside renderer0..1 bounds')
  if np.max(np.abs(w.sum(0)-1))>.0002:issues.append(part+': influence total differs from1')
  for name,values in skin['inverseBindColumnMajor'].items():
   if name not in bones:issues.append(part+': unknown bone '+name);continue
   bind=model_matrix(bones,name,cache);inv=np.asarray(values).reshape(4,4).T
   if np.abs(bind@inv-np.eye(4)).max()>1e-5:issues.append(part+': inverse bind mismatch '+name)
 mirror_error=0
 for pose in ['relaxed','open','spread','fist','grab','support']:
  l=joint_points(g,c,'l',controls(c,pose,'l'));r=joint_points(g,c,'r',controls(c,pose,'r'))
  mirror_error=max(mirror_error,max(float(np.abs(l[d]*[-1,1,1]-r[d]).max())for d in l))
 if mirror_error>1e-5:issues.append('Common hand gestures are not geometric mirrors')
 return dict(candidate=str(path),structural_passed=not issues,issues=issues,maximum_pivot_error=maximum_frame_error,maximum_normal_dot_knuckle_axis=maximum_plane_error,common_pose_mirror_error=mirror_error,visual_approved=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expect-failure',action='store_true');a=p.parse_args();r=validate(a.candidate);a.out.write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r));assert r['structural_passed']!=a.expect_failure
