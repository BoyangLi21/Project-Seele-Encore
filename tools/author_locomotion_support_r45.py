"""Bind NERV gait contact paths and runtime strides into one candidate asset."""
from pathlib import Path
import argparse,hashlib,json
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from warp_locomotion_r44 import warp
p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--profiles',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--rigs',default='0,1,2');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
d=json.loads(a.body.read_text(encoding='utf8'));common.BODY=d;rows=[]
for key in map(int,a.rigs.split(',')):
 actor=Actor(key);doc=d['stance_clips_by_rig'][str(key)]
 files=[a.profiles/f'eva_gameplay_r{rev}_{key}.json'for rev in [44,43,42,32]];profile=next(x for x in files if x.is_file());toes=json.loads(profile.read_text())['support_toes']
 for label,target in [('walk',33.3),('run',40.5)]:
  contract=d['locomotion_contract_r43'][str(key)][label];gain=contract['stride_blocks']/target
  candidate,report=warp(actor,doc,label,gain,contract,toes,4);doc['clips'][label]=candidate
  contract.update(runtime_stride_blocks_r44=target,support_mask_r44=[f['foot_contact']for f in candidate['frames']],forefoot_curves_r44=candidate['forefoot_curves_r44'],forefoot_offsets_r44=toes)
  rows.append(dict(rig=key,clip=label,**report));print(key,label,report['metrics'],flush=True)
d['locomotion_support_r45']=dict(source_sha256=hashlib.sha256(a.body.read_bytes()).hexdigest(),reason='Cadence-only gain shortened entity stride without shortening contact paths',rigs=a.rigs,visual_accepted=False,native_passed=False)
(a.out/'eva_body_r45.json').write_text(json.dumps(d,separators=(',',':')),encoding='utf8');(a.out/'authoring_report.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
