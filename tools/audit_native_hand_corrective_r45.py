"""Independently reconstruct final native DQ skin and optional contact morph.

Only positions sampled by the native submitter are compared. This proves the
asset's deformation entered rendering; it is not whole-surface clearance or
visual acceptance.
"""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from rebind_anatomical_hand_r45 import dq_pose

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'));name=f"eva_unit0{c['rig']}"
m=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
rows=[json.loads(l)for l in a.witness.open(encoding='utf8')]
palettes={(r['tick'],r['frame']):r for r in rows if r['kind']=='final_named_palette'};reports=[]
for row in rows:
 if row['kind']!='actual_cpu_submitted_part' or 'anatomical_hands'not in row['resource']:continue
 palette=palettes[(row['tick'],row['frame'])];bone_rows={b['name']:b for b in palette['bones']}
 ms={n:np.asarray(b['final_model_column_major']).reshape(4,4).T for n,b in bone_rows.items()}
 hand=row['bone'];part=m['parts'][hand];skin=m['jointSkins'][hand];indexes=np.asarray(row['actual_world_sample_vertex_indices'],int)
 rest=(np.asarray(part['vertices']).reshape(-1,8)[indexes,:3]+part['pivot'])*[-1,1,1]/16
 names=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in names]).T[indexes]
 transforms=[ms[n]@np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
 expected=dq_pose(rest,weights,transforms);unmodified=expected.copy();weight=0
 corrective=skin.get('contactCorrectiveR45')
 if corrective:
  distance=0.
  for n,target in corrective['local_quaternion_xyzw'].items():
   actual=R.from_euler('xyz',bone_rows[n]['local_euler_radians']).as_quat()
   distance=max(distance,2*np.arccos(np.clip(abs(actual@np.asarray(target)),0,1)))
  weight=float(np.clip(1-distance/np.radians(corrective['activation_degrees']),0,1));weight=weight*weight*(3-2*weight)
  sparse={int(r[0]):np.asarray(r[1:4])for r in corrective['vertex_index_position_normal_delta']}
  delta=np.asarray([sparse.get(int(i),np.zeros(3))for i in indexes])*[-1,1,1]/16
  expected+=weight*(delta@ms[hand][:3,:3].T)
 world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T
 expected=expected@world[:3,:3].T+world[:3,3];unmodified=unmodified@world[:3,:3].T+world[:3,3]
 submitted=np.asarray(row['actual_world_sample_xyz']).reshape(-1,3)
 reports.append(dict(tick=row['tick'],side=hand[-1],corrective_weight=weight,
     final_position_error_blocks=float(abs(expected-submitted).max()),
     uncorrected_position_error_blocks=float(abs(unmodified-submitted).max())))
assert reports
report=dict(samples=reports,compared_vertices=len(reports)*len(indexes),maximum_final_error_blocks=max(r['final_position_error_blocks']for r in reports),
 active_corrective_frames=sum(r['corrective_weight']>.9 for r in reports),
 scope='Actual captured sampled submitted vertices; no whole-mesh collision or visual approval',visual_accepted=False)
a.out.write_text(json.dumps(report,indent=2),'utf8')
print({k:v for k,v in report.items()if k!='samples'})
assert report['maximum_final_error_blocks']<.01,'Corrective actual emission differs from independent reconstruction'
