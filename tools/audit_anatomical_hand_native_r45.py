"""Read final game bone matrices, not a second authoring-only preview."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--witness',type=Path,required=True);p.add_argument('--pose',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
c=json.loads((a.candidate/'hand_rig_contract.json').read_text());key=c['rig'];name=f'eva_unit0{key}';geo=json.loads((a.candidate/(name+'.geo.json')).read_text());spec={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};joints={j['name']:j for h in c['hands'].values()for d in h['digits'].values()for j in d['joints']}
expected_geometry=hashlib.sha256((a.candidate/(name+'.geo.json')).read_bytes()).hexdigest();expected_mesh=hashlib.sha256((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_bytes()).hexdigest()
errors=[];alignment=[];meshes=set();geometry=set();poses=0;vertices=0;new=set();stance=[]
with a.witness.open(encoding='utf8')as stream:
 for line in stream:
  row=json.loads(line)
  if row['kind']=='actual_cpu_submitted_part'and'anatomical_hands'in row['resource']:
   meshes.add(row['loaded_resource_sha256']);vertices+=row['actual_part_vertex_count'];assert np.isfinite(row['actual_world_sample_xyz']).all()
  if row['kind']!='final_named_palette':continue
  poses+=1;geometry.add(row['loaded_geometry_sha256']);stance.append(row['stance']);actual={b['name']:np.asarray(b['final_model_column_major']).reshape(4,4).T for b in row['bones']}
  for side in ['l','r']:
   values=controls(c,a.pose,side);mirror=1 if side=='l'else -1
   for n,v in values.items():
    j=joints[n];b=spec[n];pivot=np.asarray(b['pivot'])*[-1,1,1]/16
    rot=R.from_quat(j['neutral_local_quaternion_xyzw']).as_matrix()@R.from_euler('xyz',[-v[0],v[1]*mirror,v[2]*mirror],degrees=True).as_matrix()
    local=np.eye(4);local[:3,:3]=rot;local[:3,3]=pivot-rot@pivot;expected=actual[b['parent']]@local
    error=float(np.abs(expected-actual[n]).max());errors.append((error,row['tick'],n));new.add(n)
   # Evaluate the bone-defined neutral phalanx direction relative to the
   # actual final hand, so body stance and camera orientation cannot hide skew.
   for digit in ['index','middle','ring','little']:
    points=[]
    for j in c['hands'][side]['digits'][digit]['joints']:
     inv=np.asarray(j['inverse_bind_column_major']).reshape(4,4).T
     points.append((np.linalg.inv(actual['hand_'+side])@actual[j['name']]@inv@np.r_[j['head_bind'],1])[:3])
    j=c['hands'][side]['digits'][digit]['joints'][-1];inv=np.asarray(j['inverse_bind_column_major']).reshape(4,4).T
    points.append((np.linalg.inv(actual['hand_'+side])@actual[j['name']]@inv@np.r_[j['tip_bind'],1])[:3])
    directions=np.diff(points,axis=0);directions/=np.linalg.norm(directions,axis=1)[:,None]
    alignment.append(float(np.degrees(np.arccos(np.clip(directions@directions[0],-1,1))).max()))
assert poses and len(new)==30 and vertices,'No submitted geometry/full named rig'
assert geometry=={expected_geometry}and meshes=={expected_mesh},'Actual selected resources differ from candidate'
maximum=max(errors)
report=dict(palette_samples=poses,submitted_vertices=vertices,stance_range=[min(stance),max(stance)],actual_all30_joints=True,actual_resource_match=True,maximum_local_matrix_error=maximum[0],worst_tick=maximum[1],worst_bone=maximum[2],pose=a.pose,maximum_chain_bend_degrees=max(alignment),functional_axis_passed=maximum[0]<.0001 and (a.pose!='open' or max(alignment)<.1),visual_accepted=False,scope='Actual final native bone palette and actual CPU hand submissions; no GPU/art verdict')
a.out.write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))
assert report['functional_axis_passed'],'Native axes differ or neutral digits bend unexpectedly'
