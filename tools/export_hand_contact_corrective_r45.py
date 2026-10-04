"""Export a bounded private fist skin corrective with explicit local-bone drivers."""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--sculpt',type=Path,required=True);p.add_argument('--original-pose',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'));name=f"eva_unit0{c['rig']}"
g=json.loads((a.candidate/(name+'.geo.json')).read_text('utf8'))
m=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
old=np.load(a.original_pose);fixed=np.load(a.sculpt/'fist_pad_corrected.npz');assert np.array_equal(old['rest'],fixed['rest'])
assert np.array_equal(old['faces'],fixed['faces'])
clearance=json.loads((a.sculpt/'digit_and_palm_intersections.json').read_text('utf8'));assert len(clearance)==1 and clearance[0]['total']==0
delta=fixed['vertices']-old['vertices'];faces=old['faces'];_,weld=np.unique(np.round(old['rest'],7),axis=0,return_inverse=True)
def normals(points):
 values=np.zeros((int(weld.max())+1,3));face=np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]])
 for j in range(3):np.add.at(values,weld[faces[:,j]],face)
 values/=np.maximum(np.linalg.norm(values,axis=1,keepdims=True),1e-12)
 return values[weld]
normal_delta=normals(fixed['vertices'])-normals(old['vertices'])
tree=cKDTree(old['rest']);records=[]
for side in ('r','l'):
 part=m['parts']['hand_'+side];raw=np.asarray(part['vertices']).reshape(-1,8)
 rest=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
 if side=='l':
  error,index=tree.query(rest*[-1,1,1]);assert error.max()<1e-6,('Mirrored topology mismatch',error.max())
  movement=delta[index]*[-1,1,1];norm=normal_delta[index]*[-1,1,1]
 else:movement=delta;norm=normal_delta
 ms=matrices(g,c,side,controls(c,'fist',side));rotation=ms['hand_'+side][:3,:3]
 local_movement=(movement@rotation)*[-1,1,1]*16;local_normal=(norm@rotation)*[-1,1,1]
 selected=np.flatnonzero(np.linalg.norm(local_movement,axis=1)>1e-8)
 targets={}
 parents={b['name']:b.get('parent')for b in g['minecraft:geometry'][0]['bones']}
 for digit in ('index','middle','ring','little'):
  for j in c['hands'][side]['digits'][digit]['joints']:
   bone=j['name'];targets[bone]=R.from_matrix(ms[parents[bone]][:3,:3].T@ms[bone][:3,:3]).as_quat().tolist()
 sparse=np.column_stack((selected,local_movement[selected],local_normal[selected])).tolist()
 assert np.abs(np.asarray(sparse)[:,1:]).max()<2
 m['jointSkins']['hand_'+side]['contactCorrectiveR45']=dict(activation_degrees=45,
     local_quaternion_xyzw=targets,vertex_index_position_normal_delta=sparse,
     source='Root-authored continuous pad compression; existing topology/bones retained; private native validation pending')
 records.append(dict(side=side,corrected_vertices=len(selected),maximum_model_delta=float(np.linalg.norm(movement,axis=1).max())))
(a.out/(name+'.geo.json')).write_bytes((a.candidate/(name+'.geo.json')).read_bytes())
(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(m,separators=(',',':')),'utf8')
# The measured rest hand and inverse binds have not changed. Preserve the
# existing firearm calibration while binding it to the new additive metadata.
old_mesh=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'));check=copy.deepcopy(m)
for skin in check['jointSkins'].values():skin.pop('contactCorrectiveR45',None)
assert check==old_mesh
for file in (name+'.geo.json',name+'_anatomical_hands_r45.mesh.json'):
 c['weapon_grip_source_r45'][file]=hashlib.sha256((a.out/file).read_bytes()).hexdigest()
c['contact_corrective_r45']=dict(records=records,rest_geometry_weights_bones_unchanged=True,
 source_sculpt=str(a.sculpt.resolve()),transitions_accepted=False,native_accepted=False)
(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8')
print('Private additive contact asset exported',records)
