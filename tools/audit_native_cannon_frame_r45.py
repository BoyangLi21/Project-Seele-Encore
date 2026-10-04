"""Read the actual submitted cannon mesh in a documented zero-pitch review.

Checks geometry and coordinate agreement only. It is not a fired-projectile,
hand contact, animation, or artistic acceptance test.
"""
from pathlib import Path
import argparse, json, hashlib
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rows=[json.loads(l)for l in a.witness.open(encoding='utf8')]
geometry={r['resource_part']:r for r in rows if r['kind']=='actual_static_part_geometry'}
palettes={r['tick']:r for r in rows if r['kind']=='final_named_palette'}
tip=np.array([.311045,-90.93669,-3.629085]);stock=np.array([.31,31,4.5]);result=[]
for r in rows:
 if r['kind']!='actual_cpu_submitted_part' or r['bone']!='cannon':continue
 palette=palettes[r['tick']];original=np.asarray(geometry[r['resource_part']]['original_part_xyz']).reshape(-1,3)
 changed=np.asarray(r['submitted_position_changes_index_xyz']).reshape(-1,4)
 for change in changed:original[int(change[0])]=change[1:]
 pivot=np.asarray(r['part_pivot_authored']);local=(original+pivot)*[-1,1,1]/16
 matrix=np.asarray(r['mesh_to_world_column_major']).reshape(4,4).T
 actual=local@matrix[:3,:3].T+matrix[:3,3]
 indexes=np.asarray(r['actual_world_sample_vertex_indices'],int)
 discrepancy=float(abs(actual[indexes]-np.asarray(r['actual_world_sample_xyz']).reshape(-1,3)).max())
 assert discrepancy<.01
 muzzle=matrix@np.r_[(tip+pivot)*[-1,1,1]/16,1]
 axis=matrix[:3,:3]@np.array([0,-1.,0]);axis/=np.linalg.norm(axis)
 world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T
 forward=-world[:3,2]/np.linalg.norm(world[:3,2]);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
 bone=next(b for b in palette['bones']if b['name']=='arm_r')
 shoulder=(world@np.asarray(bone['final_model_column_major']).reshape(4,4).T@np.r_[bone['pivot_model'],1])[:3]
 expected_stock=shoulder+.2*right+.5*forward+.5*up
 expected=expected_stock+np.column_stack((right,-forward,-up))@((tip-stock)*[-1,1,1]/16)*5
 result.append(dict(tick=r['tick'],stance=palette['stance'],
     reconstruction_error_blocks=discrepancy,
     barrel_to_zero_pitch_body_forward_degrees=float(np.degrees(np.arccos(np.clip(axis@forward,-1,1)))),
     geometric_common_frame_tip_error_blocks=float(np.linalg.norm(muzzle[:3]-expected))))
assert result
a.out.write_text(json.dumps(dict(witness=str(a.witness.resolve()),witness_sha256=hashlib.sha256(a.witness.read_bytes()).hexdigest(),
 measurements=result,actual_projectile_test=False,hand_contacts_accepted=False,visual_accepted=False,
 scope='Zero-pitch existing cannon review, actual submitted mesh samples; common-frame formula independently reconstructed from actual shoulder'),indent=2),'utf8')
print(json.dumps({'samples':len(result),'max_axis_error_degrees':max(r['barrel_to_zero_pitch_body_forward_degrees']for r in result),
 'max_common_frame_tip_error_blocks':max(r['geometric_common_frame_tip_error_blocks']for r in result)}))
