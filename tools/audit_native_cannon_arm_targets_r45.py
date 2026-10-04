"""Compare requested cannon palm-fit wrists to actual final arm submissions."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation as R
p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--left-pad',type=float,nargs=3,default=[.31,-15,4.8]);a=p.parse_args()
rows=[json.loads(l)for l in a.witness.open(encoding='utf8')];c=json.loads(a.contract.read_text('utf8'));result=[]
def frame(along,across):
 y=np.asarray(along)/np.linalg.norm(along);x=np.asarray(across)-y*(across@y);x/=np.linalg.norm(x);return np.column_stack((x,y,np.cross(x,y)))
for palette in (r for r in rows if r['kind']=='final_named_palette'):
 gun=next((r for r in rows if r['kind']=='actual_cpu_submitted_part'and r['tick']==palette['tick']and r['bone']=='cannon'),None)
 if gun is None:continue
 M=np.asarray(gun['mesh_to_world_column_major']).reshape(4,4).T;W=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T;b={v['name']:v for v in palette['bones']}
 right=M[:3,0]/np.linalg.norm(M[:3,0]);forward=-M[:3,1]/np.linalg.norm(M[:3,1]);up=-M[:3,2]/np.linalg.norm(M[:3,2])
 def point(name,pivot=None):return(W@np.asarray(b[name]['final_model_column_major']).reshape(4,4).T@np.r_[b[name]['pivot_model']if pivot is None else pivot,1])[:3]
 for side in ('r','l'):
  g=c.get('cannon_grip_frames',c['weapon_grip_frames'])[side];old=g.get('pose_adjustment_r45',{});pivot=np.asarray(b['hand_'+side]['pivot_model']);raw=np.array([-1.1,5.5,5.5]if side=='r'else a.left_pad);pad=(M@np.r_[(raw+gun['part_pivot_authored'])*[-1,1,1]/16,1])[:3]
  goal=frame(forward-.56*up,up+.56*forward)if side=='r'else frame(right,forward);q=goal@frame(g['along_bind'],g['across_bind']).T;pad+=q@np.array(old.get('translation_native',[0,0,0]))*5;rot=q@R.from_quat(old.get('rotation_xyzw',[0,0,0,1])).as_matrix();wanted=pad-rot@(np.asarray(g['palm_bind'])-pivot)*5
  actual=point('hand_'+side);shoulder=point('arm_'+side);socket=b.get('r30_elbow_socket_'+side,{}).get('pivot_model',np.array([-23.489652 if side=='l'else 23.489652,123.435069,7.737214])/16)
  elbow=point('forearm_'+side,socket)
  result.append(dict(tick=palette['tick'],stance=palette['stance'],side=side,wrist_target_error_blocks=float(np.linalg.norm(wanted-actual)),shoulder_to_target=float(np.linalg.norm(wanted-shoulder)),actual_segment_sum=float(np.linalg.norm(elbow-shoulder)+np.linalg.norm(actual-elbow))))
a.out.write_text(json.dumps(dict(scope='Actual common-frame cannon candidate pads and current rig elbow convention; no visual approval',measurements=result),indent=2),'utf8')
print({s:max(r['wrist_target_error_blocks']for r in result if r['side']==s)for s in ('l','r')})
