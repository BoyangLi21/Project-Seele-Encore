"""Bounded index-finger fit to the actual trigger, keeping thumb pose authored."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
from scipy.optimize import least_squares
from eva_hand_rig_math_r45 import controls,matrices

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text(encoding='utf8'));name=f"eva_unit0{c['rig']}";geo=json.loads((a.candidate/(name+'.geo.json')).read_text(encoding='utf8'));rows=[];parts={}
for line in a.witness.open(encoding='utf8'):
 r=json.loads(line)
 if r['kind']=='final_named_palette'and r['actual_owner_inputs'].get('weapon')==4 and r['stance']==0:rows.append(r)
 elif r['kind']=='actual_cpu_submitted_part':parts.setdefault(r['tick'],{})[r['bone']]=r
sample=rows[-1];sample_parts=parts[sample['tick']];gun=np.asarray(sample_parts['cannon']['mesh_to_world_column_major']).reshape(4,4).T;pc=np.asarray(sample_parts['cannon']['part_pivot_authored'])*[-1,1,1]/16
def frame(along,across):
 y=np.asarray(along)/np.linalg.norm(along);x=np.asarray(across)-y*np.dot(across,y);x/=np.linalg.norm(x);return np.column_stack([x,y,np.cross(x,y)])
right=gun[:3,0]/np.linalg.norm(gun[:3,0]);forward=-gun[:3,1]/np.linalg.norm(gun[:3,1]);up=-gun[:3,2]/np.linalg.norm(gun[:3,2]);grip=c['weapon_grip_frames']['r'];rotation=frame(forward-.56*up,up+.56*forward)@frame(grip['along_bind'],grip['across_bind']).T;pad=(gun@np.r_[pc,1])[:3]+right*.573097-up*.324-forward*1.584
hand=np.eye(4);hand[:3,:3]=rotation*5;hand[:3,3]=pad-hand[:3,:3]@np.asarray(grip['palm_bind'])
source_target=np.array([0.,36.,8.]);gun_target=pc+np.array([-source_target[0]*.9,(source_target[2]-18)*.32,-(source_target[1]-36)*.24])/16;target=(gun@np.r_[gun_target,1])[:3]
pose=controls(c,'rifle_right','r');joints=c['hands']['r']['digits']['index']['joints'];names=[j['name']for j in joints];base=matrices(geo,c,'r');inv_hand=np.linalg.inv(base['hand_r']);last=joints[-1];inv=np.asarray(last['inverse_bind_column_major']).reshape(4,4).T
def evaluate(x):
 v={k:y.copy()for k,y in pose.items()}
 for i,n in enumerate(names):v[n]=np.array([x[i],0,x[3]if i==0 else 0])
 m=matrices(geo,c,'r',v);return (hand@inv_hand@m[names[-1]]@inv@np.r_[last['tip_bind'],1])[:3]
comfort=np.array([30,70,25,-20.])
def residual(x):return np.r_[(evaluate(x)-target)*10,(x-comfort)*.001]
fit=least_squares(residual,comfort,bounds=([-15,15,0,-25],[70,100,55,10]),max_nfev=120)
record=dict(source_trigger_target=source_target.tolist(),actual_native_input_tick=sample['tick'],angles=fit.x.tolist(),bone_tip_error_world_blocks=float(np.linalg.norm(evaluate(fit.x)-target)),thumb_changed=False,actual_skin_contact_verified=False,visual_accepted=False)
if record['bone_tip_error_world_blocks']>.25:
 (a.out/'rejected_fit.json').write_text(json.dumps(record,indent=2),encoding='utf8');raise SystemExit('Index contact is unreachable within natural limits; candidate was not exported')
table=c['pose_controls']['rifle_right'].setdefault('bone_angles',{})
for i,n in enumerate(names):table[n]=[float(fit.x[i]),0,float(fit.x[3])if i==0 else 0]
c['trigger_finger_contact_candidate']=record
for f in a.candidate.iterdir():
 if f.is_file():shutil.copy2(f,a.out/f.name)
(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),encoding='utf8');print(json.dumps(record))
