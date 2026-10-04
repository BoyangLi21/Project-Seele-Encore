"""Bounded anatomical thumb contact, using the new hand's real joint lengths."""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.optimize import least_squares
from eva_hand_rig_math_r45 import controls,joint_points

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--legacy-diagnostic',action='store_true');a=p.parse_args()
if not a.legacy_diagnostic:raise SystemExit('Retired: endpoint fit creates an unnatural hooked thumb. Use author_natural_thumb_r45.py; legacy flag is for reproducing the rejected result only.')
a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text());key=c['rig'];name=f'eva_unit0{key}';geo=json.loads((a.candidate/(name+'.geo.json')).read_text());reports=[]
for pose_name in ['fist','knife']:
    side='l';initial=controls(c,pose_name,side);points=joint_points(geo,c,side,initial);thumb=c['hands'][side]['digits']['thumb']['joints'];names=[j['name']for j in thumb]
    normal=np.asarray(c['hands'][side]['palmar_normal_bind']);target=points['index'][1]*.50+points['middle'][1]*.50+normal*.035
    pad_axis=points['middle'][1]-points['index'][1];pad_axis/=np.linalg.norm(pad_axis)
    x0=np.r_[initial[names[0]],initial[names[1]][0],initial[names[2]][0]];limits=np.asarray(thumb[0]['anatomical_limits_degrees']);lo=np.r_[limits[:,0],thumb[1]['anatomical_limits_degrees'][0][0],thumb[2]['anatomical_limits_degrees'][0][0]];hi=np.r_[limits[:,1],thumb[1]['anatomical_limits_degrees'][0][1],thumb[2]['anatomical_limits_degrees'][0][1]]
    def values(x):
        result={k:v.copy()for k,v in initial.items()};result[names[0]]=x[:3];result[names[1]]=np.array([x[3],0,0]);result[names[2]]=np.array([x[4],0,0]);return result
    def residual(x):
        at=joint_points(geo,c,side,values(x))['thumb'];axis=at[-1]-at[-2];axis/=np.linalg.norm(axis)
        return np.r_[(at[-1]-target)*20,(axis-pad_axis)*.45,(x-x0)*.0006]
    fits=[least_squares(residual,np.clip(start,lo+1e-6,hi-1e-6),bounds=(lo,hi),max_nfev=240,ftol=1e-10,xtol=1e-10,gtol=1e-10)for start in [x0,np.array([30,40,25,30,30]),np.array([15,-25,35,45,25])]]
    fit=min(fits,key=lambda f:np.linalg.norm(f.fun));fitted=values(fit.x);actual=joint_points(geo,c,side,fitted)['thumb'][-1];error=float(np.linalg.norm(actual-target)*5)
    table=c['pose_controls'][pose_name].setdefault('bone_angles',{})
    for left in names:
        table[left]=fitted[left].tolist();table[left.replace('r45_hand_l_','r45_hand_r_')]=fitted[left].tolist()
    reports.append(dict(pose=pose_name,target_native=target.tolist(),actual_native=actual.tolist(),error_world_blocks=error,angles=fit.x.tolist(),accepted_art=False))
c['thumb_opposition_solver']=dict(method='Bounded5DOF anatomical fit toward outside index/middle phalange support; original bone lengths remain fixed',results=reports,collision_verified=False,art_approved=False);c['angle_convention']='Desired local=neutral_local*Rz(side*splay)*Ry(side*twist)*Rx(-flexion), side=+1left/-1right; mesh inverse-bind refers to authored rest'
for f in a.candidate.iterdir():
    if f.is_file():shutil.copy2(f,a.out/f.name)
(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8');print(json.dumps(reports))
