"""Author thumb opposition by whole phalanx directions, then derive fixed hinge rolls."""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import matrices
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();shutil.copytree(a.candidate,a.out)
f=a.out/'hand_rig_contract.json';c=json.loads(f.read_text());name=f"eva_unit0{c['rig']}";gp=a.out/(name+'.geo.json');g=json.loads(gp.read_text());mp=a.out/(name+'_anatomical_hands_r45.mesh.json');m=json.loads(mp.read_text());bones={b['name']:b for b in g['minecraft:geometry'][0]['bones']};h=c['hands']['l'];js=h['digits']['thumb']['joints'];old=matrices(g,c,'l')
def unit(x):return x/np.linalg.norm(x)
def arc(a,b):
 axis=np.cross(a,b);length=np.linalg.norm(axis)
 return R.identity()if length<1e-10 else R.from_rotvec(axis/length*np.arctan2(length,a@b))
L=np.asarray(h['longitudinal_bind']);N=np.asarray(h['palmar_normal_bind']);A=unit(np.asarray(h['digits']['index']['joints'][0]['head_bind'])-h['digits']['little']['joints'][0]['head_bind'])
directions=[unit(.25*L+.60*N+.75*A),unit(.15*L+.95*N-.10*A),unit(.05*L+.30*N-.95*A)]
first=js[0];parent=bones[first['name']]['parent'];roll=R.from_euler('y',45,degrees=True).as_matrix();rest_first=old[first['name']][:3,:3]@roll;restq=R.from_matrix(old[parent][:3,:3].T@rest_first);bones[first['name']]['rotation']=(restq.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist();inverse=np.linalg.inv(matrices(g,c,'l')[first['name']]).T.reshape(-1).tolist();first.update(local_bind_quaternion_xyzw=restq.as_quat().tolist(),neutral_local_quaternion_xyzw=restq.as_quat().tolist(),inverse_bind_column_major=inverse)
for skin in m['jointSkins'].values():
 if first['name']in skin['inverseBindColumnMajor']:skin['inverseBindColumnMajor'][first['name']]=inverse
world=arc(old[first['name']][:3,1],directions[0]).as_matrix()@rest_first;local=old[parent][:3,:3].T@world;neutral=restq.as_matrix();control=R.from_matrix(neutral.T@local).as_euler('xyz',degrees=True)*[-1,1,1];angles=[control.tolist()];posed_parent=world
for i,j in enumerate(js[1:],1):
 parent=bones[j['name']]['parent'];rest_parent=matrices(g,c,'l')[parent];neutral_world=posed_parent@rest_parent[:3,:3].T@old[j['name']][:3,:3];y=unit(neutral_world[:,1]);target=directions[i];x=-unit(np.cross(y,target));neutral_frame=np.column_stack([x,y,np.cross(x,y)]);flex=float(np.degrees(np.arccos(np.clip(y@target,-1,1))));assert flex<85
 rest_world=rest_parent[:3,:3]@posed_parent.T@neutral_frame;local=rest_parent[:3,:3].T@rest_world;restq=R.from_matrix(local);b=bones[j['name']];b['pivot']=((np.linalg.inv(rest_parent)@np.r_[j['head_bind'],1])[:3]*[-1,1,1]*16).tolist();b['rotation']=(restq.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist();inverse=np.linalg.inv(matrices(g,c,'l')[j['name']]).T.reshape(-1).tolist();j.update(local_bind_quaternion_xyzw=restq.as_quat().tolist(),neutral_local_quaternion_xyzw=restq.as_quat().tolist(),inverse_bind_column_major=inverse);j['anatomical_limits_degrees']=[[0,max(65,flex+1)],[0,0],[0,0]]
 for skin in m['jointSkins'].values():
  if j['name']in skin['inverseBindColumnMajor']:skin['inverseBindColumnMajor'][j['name']]=inverse
 posed_parent=neutral_frame@R.from_euler('x',-flex,degrees=True).as_matrix();assert np.linalg.norm(posed_parent[:,1]-target)<1e-7;angles.append([flex,0,0])
for pose in ['fist','knife']:c['pose_controls'][pose]['thumb']=angles
# Report rather than silently clamp a saddle rotation that exceeds its authoring range.
lim=np.asarray(first['anatomical_limits_degrees']);assert np.all(control>=lim[:,0])and np.all(control<=lim[:,1]),('CMC authoring range',control)
c['new_bones']=[copy.deepcopy(b)for b in g['minecraft:geometry'][0]['bones']if b['name'].startswith('r45_hand_')];c['thumb_opposition_frames_r45']=dict(controls=angles,hinge_direction_source='Authored metacarpal-to-distal contact chain; fixed hinge rolls, no runtime stretching',native_passed=False,visual_accepted=False)
f.write_text(json.dumps(c,indent=2),encoding='utf8');gp.write_text(json.dumps(g,indent=2),encoding='utf8');mp.write_text(json.dumps(m,separators=(',',':')),encoding='utf8');print(json.dumps(angles))
