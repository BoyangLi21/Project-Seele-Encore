"""Measure actual final wrist/forearm alignment and joint continuity."""
from pathlib import Path
import argparse,json
import numpy as np
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--body',type=Path,required=True);p.add_argument('--hand',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
c=json.loads((a.hand/'hand_rig_contract.json').read_text());common.BODY=json.loads(a.body.read_text());actor=Actor(c['rig']);rows=[]
for line in a.witness.open(encoding='utf8'):
    r=json.loads(line)
    if r['kind']!='final_named_palette':continue
    b={x['name']:x for x in r['bones']};item=dict(tick=r['tick'],stance=r['stance'],gait=r['gait'],inputs=r['actual_owner_inputs'],hands={})
    for side in ['l','r']:
        hand=np.asarray(b['hand_'+side]['final_model_column_major']).reshape(4,4).T
        forearm=np.asarray(b['forearm_'+side]['final_model_column_major']).reshape(4,4).T
        pivot=np.asarray(b['hand_'+side]['pivot_model']);wrist=(hand@np.r_[pivot,1])[:3]
        elbow=(forearm@np.r_[actor.elbows[side]/16,1])[:3];direction=wrist-elbow;direction/=np.linalg.norm(direction)
        palm=hand[:3,:3]@np.asarray(c['hands'][side]['longitudinal_bind']);palm/=np.linalg.norm(palm)
        cuff=(forearm@np.r_[pivot,1])[:3]
        item['hands'][side]=dict(bend_degrees=float(np.degrees(np.arccos(np.clip(palm@direction,-1,1)))),joint_gap_blocks=float(np.linalg.norm(wrist-cuff)*5))
    rows.append(item)
assert rows
a.out.write_text(json.dumps(dict(scope='Final submitted bone matrices; not visual approval or skin cuff clearance',samples=rows),indent=2),encoding='utf8')
upright=[r for r in rows if r['stance']<.01 and r['inputs']['powered'] and not r['inputs']['locked'] and not r['inputs']['live_action']]
for side in ['l','r']:
    print(side,'upright_samples',len(upright),'bend_range',min(r['hands'][side]['bend_degrees']for r in upright),max(r['hands'][side]['bend_degrees']for r in upright),'max_joint_gap',max(r['hands'][side]['joint_gap_blocks']for r in rows))
