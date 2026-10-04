"""Retargeted MCO crouch cycle, closed and contact-warped for the real game stride."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from warp_locomotion_r44 import warp
from check_locomotion_warp_r44 import frame_between
p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
d=json.loads(a.body.read_text());source=json.loads(a.capture.read_text());key=source['rig_key'];assert source['rig_contract_r44']==d['rigs'][str(key)]
doc=d['stance_clips_by_rig'][str(key)];names=doc['bones'];indices=[source['bones'].index(n)for n in names];clip=copy.deepcopy(source['clips']['crouch_walk']);fs=[]
records=json.loads((a.capture.parent/'contact_pass_receipt.json').read_text())['records'];assert len(records)==len(clip['frames'])
for f,r in zip(clip['frames'],records):
 # The continuous sole IK weight is not a binary support label. Use the
 # recorded horizontal plant interval (derived from actual source velocity).
 v=dict(rotation_wxyz=[f['rotation_wxyz'][i]for i in indices],root_m=f['root_m'],bone_position_xyz=f['bone_position_xyz'],foot_contact=[r['source_horizontal_foot_plants'][s]for s in ['l','r']]);fs.append(v)
for i in range(len(fs)):
 t=i/(len(fs)-1);u=float(np.clip((t-.8)/.2,0,1));u=u*u*u*(10+u*(-15+6*u))
 if u>0:
  contacts=fs[i]['foot_contact'];fs[i]=frame_between(fs[i],fs[0],u);fs[i]['foot_contact']=contacts
fs[-1]=copy.deepcopy(fs[0]);doc['clips']['crouch_walk']=dict(duration_seconds=clip['duration_seconds'],loop=True,frames=fs)
contract=dict(stride_blocks=clip['cycle_travel_world_blocks'],source_duration_seconds=clip['duration_seconds'])
common.BODY=d;actor=Actor(key);toes=json.loads(a.profile.read_text())['support_toes'];candidate,report=warp(actor,doc,'crouch_walk',clip['cycle_travel_world_blocks']/15,contract,toes,4)
report['source']='MCO MOB1_CrouchWalk_F: actual source FK and source-velocity horizontal plant intervals, native rig-specific pose and contact warp'
doc['clips']['crouch_walk']=candidate;contract.update(runtime_stride_blocks_r44=15,support_mask_r44=[f['foot_contact']for f in candidate['frames']],forefoot_curves_r44=candidate['forefoot_curves_r44'],forefoot_offsets_r44=toes)
d['locomotion_contract_r43'][str(key)]['crouch_walk']=contract
d['crouch_source_r45']=dict(source_sha256=hashlib.sha256(a.capture.read_bytes()).hexdigest(),source_card=source['source_motion_card'],scope='Private evaluation; source rights unchanged; native/art review required',closure_interval=[.8,1],native_passed=False)
(a.out/'eva_body_r45.json').write_text(json.dumps(d,separators=(',',':')),encoding='utf8');(a.out/'authoring_report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
