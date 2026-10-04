"""Sculpt a small thumb-pad clearance in bind space, retaining continuous skin.

The thumb rests along the outside of the folded index. A bounded bind-space
correction removes the remaining skin contact; no joint translation or runtime
finger shortening is used. The untouched source remains the negative control.
"""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--clearance',type=float,default=.018);p.add_argument('--splay',type=float,default=-45);p.add_argument('--radial',type=float,default=0);a=p.parse_args();assert 0<=a.clearance<=.04;shutil.copytree(a.candidate,a.out)
cpath=a.out/'hand_rig_contract.json';c=json.loads(cpath.read_text());name=f"eva_unit0{c['rig']}";g=json.loads((a.out/(name+'.geo.json')).read_text());mpath=a.out/(name+'_anatomical_hands_r45.mesh.json');m=json.loads(mpath.read_text());c['pose_controls']['fist']['thumb']=[[55,18,a.splay],[18,0,0],[12,0,0]];report=[]
for side in ['l','r']:
 part=m['parts']['hand_'+side];skin=m['jointSkins']['hand_'+side];raw=np.asarray(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T;ms=matrices(g,c,side,controls(c,'fist',side));qs=[]
 for n in palette:
  transform=ms[n]@np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T;qs.append(R.from_matrix(transform[:3,:3]).as_quat())
 qs=np.asarray(qs);reference=qs[np.argmax(weights,axis=1)];signed=weights*np.where(reference@qs.T<0,-1,1);blend=signed@qs;blend/=np.linalg.norm(blend,axis=1)[:,None]
 influence=sum(weights[:,palette.index(j['name'])]for j in c['hands'][side]['digits']['thumb']['joints'])
 h=c['hands'][side];radial=np.asarray(h['digits']['index']['joints'][0]['head_bind'])-h['digits']['little']['joints'][0]['head_bind'];radial/=np.linalg.norm(radial)
 direction=np.asarray(h['palmar_normal_bind'])+radial*a.radial;direction/=np.linalg.norm(direction)
 delta=influence[:,None]*direction*a.clearance
 correction=R.from_quat(blend).inv().apply(delta);points+=correction
 raw[:,:3]=points*[-1,1,1]*16-part['pivot']
 # Recompute smooth normals after sculpting, welding duplicate seam vertices.
 _,unique,inverse=np.unique(np.round(points,7),axis=0,return_index=True,return_inverse=True);normals=np.zeros((len(unique),3));faces=inverse.reshape(-1,3);v=points[unique]
 face_normals=np.cross(v[faces[:,1]]-v[faces[:,0]],v[faces[:,2]]-v[faces[:,0]])
 for i in range(3):np.add.at(normals,faces[:,i],face_normals)
 normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12);raw[:,5:8]=normals[inverse]*[-1,1,1];part['vertices']=np.round(raw,7).reshape(-1).tolist()
 report.append(dict(side=side,max_bind_sculpt_native=float(np.linalg.norm(correction,axis=1).max()),max_world_blocks=float(np.linalg.norm(correction,axis=1).max()*5)))
c['fist_contact_sculpt_r45']=dict(method='Outside-index thumb contact, inverse-DQ bind sculpt',clearance_native=a.clearance,changes=report,collision_passed=False,native_passed=False,user_accepted=False)
mpath.write_text(json.dumps(m,separators=(',',':')),encoding='utf8');cpath.write_text(json.dumps(c,indent=2),encoding='utf8');print(json.dumps(report))
