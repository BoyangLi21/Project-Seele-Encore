"""Contact-fit individual fingers around a measured rigid handle, candidate only."""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices,joint_points
from rebind_anatomical_hand_r45 import dq_pose
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--kind',choices=['knife','sword'],default='knife');p.add_argument('--normal-shift',type=float,default=0);p.add_argument('--natural-contact',action='store_true');a=p.parse_args();shutil.copytree(a.candidate,a.out)
f=a.out/'hand_rig_contract.json';c=json.loads(f.read_text());name=f"eva_unit0{c['rig']}";g=json.loads((a.out/(name+'.geo.json')).read_text());m=json.loads((a.out/(name+'_anatomical_hands_r45.mesh.json')).read_text());side='r';h=c['hands'][side];part=m['parts']['hand_r'];skin=m['jointSkins']['hand_r'];raw=np.array(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;palette=list(skin['influences']);weights=np.array([skin['influences'][n]for n in palette]).T;inv=[np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette];N=np.array(h['palmar_normal_bind']);L=np.array(h['longitudinal_bind']);pose_name='knife'if a.kind=='knife'else'sword_right';c['pose_controls'][pose_name]=copy.deepcopy(c['pose_controls'].get(pose_name,c['pose_controls']['knife']));attachment=c[a.kind+'_attachment_r45'];rot=R.from_quat(attachment['rotation_xyzw']).as_matrix();A=-rot[:,1];centre=np.array(attachment['target_handle_centre'])+N*a.normal_shift;attachment['target_handle_centre']=centre.tolist();preview_name='knife_preview.npz'if a.kind=='knife'else'sword_grip_preview.npz';preview_file=a.out/preview_name
if not preview_file.exists():preview_file=a.out/'attachment.npz'
data=np.load(preview_file);knife=data[a.kind]+N*a.normal_shift;posed=controls(c,pose_name,side);reports=[]
for digit in ['index','middle','ring','little']:
 js=h['digits'][digit]['joints'];names=[j['name']for j in js];mass=sum(weights[:,palette.index(n)]for n in names);ids=np.flatnonzero(mass>.65);w=weights[ids];v=points[ids];at=joint_points(g,c,side,posed)[digit][0];radial=(at-centre)@A;selected=knife[abs((knife-centre)@A-radial)<.10];assert len(selected)>30;
 if np.linalg.matrix_rank(selected-selected.mean(0),tol=1e-8)<3:
  # A two-sided thin imported hilt has no signed interior. Use an explicit
  # 4mm native contact shell for fitting; rendered knife vertices stay intact.
  axis=np.linalg.svd(selected-selected.mean(0),full_matrices=False)[2][-1]
  hull_points=np.vstack([selected+axis*.004,selected-axis*.004])
 else:hull_points=selected
 hull=ConvexHull(hull_points);eq=hull.equations;proximal=float(((selected-centre)@L).min());target=centre+A*radial+L*(proximal-.035)+N*.025
 cup=h['digits'].get('cup_'+digit,{}).get('joints',[])
 fit_joints=js+cup
 fit_names=names+[j['name']for j in cup]
 x0=np.array([posed[n][0]for n in fit_names]);lo=np.array([max(0,j['anatomical_limits_degrees'][0][0])for j in fit_joints]);hi=np.array([j['anatomical_limits_degrees'][0][1]for j in fit_joints])
 def sample(x):
  values={k:q.copy()for k,q in posed.items()}
  for i,n in enumerate(fit_names):values[n][0]=x[i]
  ms=matrices(g,c,side,values);transforms=[ms[n]@iv for n,iv in zip(palette,inv)];surface=dq_pose(v,w,transforms);last=js[-1];tip=(ms[last['name']]@np.asarray(last['inverse_bind_column_major']).reshape(4,4).T@np.r_[last['tip_bind'],1])[:3]
  return surface,tip
 if a.natural_contact:target=sample(x0)[1]
 def residual(x):
  surface,tip=sample(x);signed=(surface@eq[:,:3].T+eq[:,3]).max(1);penetration=np.maximum(.006-signed,0)
  return np.r_[penetration*60,(tip-target)*(8 if a.natural_contact else 4),(x-x0)*(.006 if a.natural_contact else .0007)]
 starts=[x0,np.r_[[85,95,75.],x0[3:]]];fits=[least_squares(residual,np.clip(start,lo+1e-6,hi-1e-6),bounds=(lo,hi),max_nfev=120,diff_step=1e-4)for start in starts];fit=min(fits,key=lambda fit:np.linalg.norm(fit.fun));surface,tip=sample(fit.x);signed=(surface@eq[:,:3].T+eq[:,3]).max(1)
 for i,n in enumerate(fit_names):posed[n][0]=fit.x[i]
 c['pose_controls'][pose_name][digit]=fit.x[:3].tolist()
 if cup:c['pose_controls'][pose_name]['cup_'+digit]=fit.x[3:].tolist()
 reports.append(dict(digit=digit,angles=fit.x.tolist(),maximum_sampled_penetration_native=float(max(0,-signed.min())),tip_error_native=float(np.linalg.norm(tip-target)),visual_accepted=False));print(reports[-1],flush=True)
assert all(np.allclose(controls(c,pose_name,side)[n],v)for n,v in posed.items()),'Serialized runtime controls differ from the fitted pose';c[a.kind+'_finger_contact_fit_r45']=reports;f.write_text(json.dumps(c,indent=2),encoding='utf8')
ms=matrices(g,c,side,posed);hand=dq_pose(points,weights,[ms[n]@iv for n,iv in zip(palette,inv)]);np.savez_compressed(a.out/preview_name,hand=hand,normal=N,along=L,**{a.kind:knife})
