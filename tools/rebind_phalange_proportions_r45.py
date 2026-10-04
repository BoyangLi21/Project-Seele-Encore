"""Place finger hinges at EVA source proportions and rebind the glove.

Keep the continuous surface, total length, MCP and tip. The three visible
phalanges use48/29/23 percent instead of the donor rig's nearly equal thirds.
"""
from pathlib import Path
import argparse,copy,json,shutil
import numpy as np
from author_anatomical_hand_rig_r45 import model_matrix

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text(encoding='utf8'));name=f"eva_unit0{c['rig']}";geo=json.loads((a.candidate/(name+'.geo.json')).read_text(encoding='utf8'));mesh=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text(encoding='utf8'));bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};cache={};reports=[]
for side in ['l','r']:
 hand='hand_'+side;part=mesh['parts'][hand];raw=np.asarray(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;skin=mesh['jointSkins'][hand]
 for digit in ['index','middle','ring','little']:
  joints=c['hands'][side]['digits'][digit]['joints'];p0=np.asarray(joints[0]['head_bind']);p3=np.asarray(joints[-1]['tip_bind']);direction=p3-p0;length=np.linalg.norm(direction);direction/=length;positions=[p0+direction*length*t for t in [0,.48,.77,1]];old_lengths=[j['length']for j in joints]
  for i,j in enumerate(joints):
   spec=bones[j['name']];parent=model_matrix(bones,spec['parent'],cache);local=(np.linalg.inv(parent)@np.r_[positions[i],1])[:3];spec['pivot']=(local*[-1,1,1]*16).tolist();cache.clear();bind=model_matrix(bones,j['name'],cache);j.update(head_bind=positions[i].tolist(),tip_bind=positions[i+1].tolist(),length=float(np.linalg.norm(positions[i+1]-positions[i])),inverse_bind_column_major=np.linalg.inv(bind).T.reshape(-1).tolist());skin['inverseBindColumnMajor'][j['name']]=j['inverse_bind_column_major']
  names=[j['name']for j in joints];mass=sum(np.asarray(skin['influences'][n])for n in names);t=(points-p0)@direction/length
  def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
  at_pip=smooth((t-.48+.055)/.11);at_dip=smooth((t-.77+.045)/.09);weights=[1-at_pip,at_pip-at_dip,at_dip]
  for n,w in zip(names,weights):skin['influences'][n]=np.round(mass*np.maximum(w,0),7).tolist()
  reports.append(dict(side=side,digit=digit,before=old_lengths,after=[j['length']for j in joints],total_length_preserved=True,palm_digit_weight_mass_preserved=True))
for skin in mesh['jointSkins'].values():
 names=list(skin['influences']);w=np.clip(np.asarray([skin['influences'][n]for n in names]),0,1);w/=w.sum(0)[None,:];w=np.round(w,7)
 assert np.isfinite(w).all()and np.min(w)>=0 and np.max(w)<=1 and np.max(np.abs(w.sum(0)-1))<.0001
 for n,row in zip(names,w):skin['influences'][n]=row.tolist()
c['new_bones']=[copy.deepcopy(bones[b['name']])for b in c['new_bones']];c['construction']['phalange_rebind']=reports;c['construction']['phalange_weight_author']='New continuous DQ hinge bands; donor digit membership retained, phalanx weights reauthored and normalized after export quantization'
for file,data in [(name+'.geo.json',geo),(name+'_anatomical_hands_r45.mesh.json',mesh),('hand_rig_contract.json',c)]:
 (a.out/file).write_text(json.dumps(data,indent=2 if not file.endswith('.mesh.json')else None),encoding='utf8')
print('Rebuilt8finger chains at48/29/23 length proportions, with new matching skin weights')
