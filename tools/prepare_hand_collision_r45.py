"""Pose actual DQ surfaces for independent triangle-intersection inspection."""
from pathlib import Path
import argparse,copy,json
import numpy as np
from eva_hand_rig_math_r45 import controls,matrices,contact_corrective
from rebind_anatomical_hand_r45 import dq_pose

p=argparse.ArgumentParser()
p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--cases',type=Path);p.add_argument('--poses',default='');p.add_argument('--side',choices=['l','r'],default='l')
p.add_argument('--pose-controls',type=Path,help='Offline proposed bone controls; does not edit the candidate')
p.add_argument('--transition',action='store_true');p.add_argument('--staged',action='store_true');p.add_argument('--side-tuck',action='store_true')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text(encoding='utf8'));name=f"eva_unit0{c['rig']}"
if a.pose_controls:
 assert a.poses and ','not in a.poses,'An offline override must name exactly one pose'
 proposal=json.loads(a.pose_controls.read_text('utf8'))
 assert proposal.get('side',a.side)==a.side,'Offline control side mismatch'
 c['pose_controls'][a.poses]['bone_angles']=proposal.get('controls',proposal)
g=json.loads((a.candidate/(name+'.geo.json')).read_text(encoding='utf8'))
m=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text(encoding='utf8'))
side=a.side;part=m['parts']['hand_'+side];raw=np.asarray(part['vertices']).reshape(-1,8)
points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;skin=m['jointSkins']['hand_'+side]
palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T
digits=['thumb','index','middle','ring','little']
mass=np.array([sum(weights[:,palette.index(j['name'])]for j in c['hands'][side]['digits'][d]['joints'])for d in digits])
face_mass=np.array([row.reshape(-1,3).mean(1)for row in mass]);labels=np.argmax(face_mass,axis=0)
labels[np.max(face_mass,axis=0)<.65]=-1;faces=np.arange(len(points)).reshape(-1,3)
cases={'before':c['pose_controls']['fist']['thumb'],'open':None}
if a.side_tuck:
 for f in [0,15,30,45]:
  for t in [-25,-10,5]:
   for s in [-30,-10,10]:cases[f'f{f}_t{t}_s{s}']=[[f,t,s],[18,0,0],[12,0,0]]
if a.cases:cases.update(json.loads(a.cases.read_text(encoding='utf8')))
if a.poses:cases={f'pose_{n}':dict(pose=n)for n in a.poses.split(',')}
if a.transition:cases={f'{start}_fist_{i:02}':dict(start=start,weight=i/20)for start in ['open','relaxed','support']for i in range(21)}
records=[]
for case,definition in cases.items():
 cc=copy.deepcopy(c)
 if isinstance(definition,dict)and 'pose'in definition:
  cc['pose_controls'][definition['pose']].update(definition.get('overrides',{}));values=controls(cc,definition['pose'],side)
 elif isinstance(definition,dict):
  first=controls(cc,definition['start'],side);last=controls(cc,definition.get('end','fist'),side);values={}
  for n in first:
   t=definition['weight']
   if definition.get('finger_first'):
    t=float(np.clip((t-.25)/.75 if '_thumb_'in n else t/.7,0,1));t=t*t*(3-2*t)
   if a.staged:
    t=float(np.clip(t/.8 if '_thumb_'in n else(t-.2)/.8,0,1));t=t*t*t*(10+t*(-15+6*t))
   values[n]=first[n]*(1-t)+last[n]*t
   if n.endswith('_thumb_1') and definition.get('thumb_clearance'):
    values[n][2]+=float(definition['thumb_clearance'])*np.sin(np.pi*definition['weight'])
 else:
  pose='open'if definition is None else'fist'
  if definition is not None:cc['pose_controls'][pose]['thumb']=definition;cc['pose_controls'][pose].pop('bone_angles',None)
  values=controls(cc,pose,side)
 ms=matrices(g,cc,side,values)
 transforms=[ms[n]@np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
 posed=dq_pose(points,weights,transforms)
 posed=contact_corrective(g,skin,posed,ms,'hand_'+side)
 np.savez_compressed(a.out/(case+'.npz'),vertices=posed,faces=faces,labels=labels,rest=points)
 records.append(dict(case=case,side=side,definition=definition))
(a.out/'cases.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print('Prepared',len(records),'actual skinned surface cases')
