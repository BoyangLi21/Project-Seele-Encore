"""Diagnostic reference-pose retarget; no installation and no quality claim."""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh
from eva_hand_rig_math_r45 import matrices
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--pose',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--source-side',choices=['L','R'],default='L');a=p.parse_args();shutil.copytree(a.candidate,a.out)
cpath=a.out/'hand_rig_contract.json';c=json.loads(cpath.read_text());g=json.loads((a.out/f"eva_unit0{c['rig']}.geo.json").read_text());skel=json.loads((a.reference/'default.mhskel').read_text());v=np.array([[float(x)for x in s.split()[1:4]]for s in(a.reference/'base.obj').read_text().splitlines()if s.startswith('v ')])
def point(n):return v[skel['joints'][n]].mean(0)
def unit(x):return x/np.linalg.norm(x)
sw=point('wrist.L____head');sy=unit(point('finger3-1.L____head')-sw);sx=point('finger2-1.L____head')-point('finger5-1.L____head');sx=unit(sx-sy*np.dot(sx,sy));sz=unit(np.cross(sx,sy));S=np.column_stack([sx,sy,sz])
h=c['hands']['l'];ty=unit(np.asarray(h['longitudinal_bind']));tx=np.asarray(h['digits']['index']['joints'][0]['head_bind'])-h['digits']['little']['joints'][0]['head_bind'];tx=unit(tx-ty*(tx@ty));T=np.column_stack([tx,ty,unit(np.cross(tx,ty))]);A=T@S.T
data=load_bvh(a.pose,translation_mode='offset');ix={s:i for i,s in enumerate(data['names'])}
# BVH exporter coordinates are not the base OBJ coordinates. Calibrate on its
# own zero-channel hierarchy before transporting rotations into the EVA palm.
rest=data['offsets'].copy()
for i,parent in enumerate(data['parents']):
 if parent>=0:rest[i]+=rest[parent]
suffix='.'+a.source_side;w=rest[ix['wrist'+suffix]];sy=unit(rest[ix['finger3-1'+suffix]]-w);sx=rest[ix['finger2-1'+suffix]]-rest[ix['finger5-1'+suffix]];sx=unit(sx-sy*(sx@sy));sz=unit(np.cross(sx,sy));S=np.column_stack([sx,sy,sz]);A=T@S.T
if a.source_side=='R':A=T@np.diag([1.,1,-1])@S.T
wrist=R.from_quat(data['rotations'][0,ix['wrist.'+a.source_side]]);bind=matrices(g,c,'l');bones={b['name']:b for b in g['minecraft:geometry'][0]['bones']};posed={'hand_l':bind['hand_l'][:3,:3]};angles={};report=[]
for digit,number in [('thumb',1),('index',2),('middle',3),('ring',4),('little',5)]:
 for j in h['digits'][digit]['joints']:
  n=j['name'];source=f"finger{number}-{j['index']+1}.{a.source_side}";delta=(wrist.inv()*R.from_quat(data['rotations'][0,ix[source]])).as_matrix();world=A@delta@A.T@bind[n][:3,:3];parent=bones[n]['parent'];local=posed[parent].T@world;neutral=R.from_quat(j['neutral_local_quaternion_xyzw']).as_matrix();e=R.from_matrix(neutral.T@local).as_euler('xyz',degrees=True);values=e*[-1,1,1];angles[n]=values.tolist();posed[n]=world
  report.append(dict(bone=n,controls=values.tolist()))
  # Diagnostic imported reference is retained exactly; do not silently clamp.
  lim=np.asarray(j['anatomical_limits_degrees'],float);lim[:,0]=np.minimum(lim[:,0],values-1e-5);lim[:,1]=np.maximum(lim[:,1],values+1e-5);j['anatomical_limits_degrees']=lim.tolist()
c['pose_controls']['reference_fist']={**c['pose_controls']['fist'],'bone_angles':angles}
c['reference_pose_diagnostic']=dict(source=str(a.pose),license='CC0',verified_anatomical_limits=False,visual_accepted=False,angles=report)
cpath.write_text(json.dumps(c,indent=2),encoding='utf8');print(json.dumps(report[:3]))
