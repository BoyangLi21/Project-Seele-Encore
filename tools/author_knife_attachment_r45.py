"""Bind the handle across the knuckle row, using the actual new gripping hand."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices
from rebind_anatomical_hand_r45 import dq_pose
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--mesh',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--handle-y',nargs=2,type=float,default=[88,94]);p.add_argument('--source-handle-centre',nargs=3,type=float);p.add_argument('--along',type=float,default=-.06);p.add_argument('--normal',type=float,default=.18);p.add_argument('--radial',type=float,default=0);a=p.parse_args();shutil.copytree(a.candidate,a.out)
f=a.out/'hand_rig_contract.json';c=json.loads(f.read_text());h=c['hands']['r'];m=json.loads(a.mesh.read_text());part=m['parts']['knife'];raw=np.asarray(part['vertices']).reshape(-1,m['stride']);pts=raw[:,:3]+part['pivot'];handle=pts[(pts[:,1]>=a.handle_y[0])&(pts[:,1]<=a.handle_y[1])];assert len(handle)>100
source=(handle.min(0)+handle.max(0))*.5*[-1,1,1]/16
if a.source_handle_centre is not None:source=np.asarray(a.source_handle_centre)
roots=np.array([h['digits'][n]['joints'][0]['head_bind']for n in ['index','middle','ring','little']]);along=np.asarray(h['longitudinal_bind']);normal=np.asarray(h['palmar_normal_bind']);across=roots[0]-roots[-1];across-=normal*(normal@across);across/=np.linalg.norm(across)
x=normal;y=-across;z=np.cross(x,y);z/=np.linalg.norm(z);x=np.cross(y,z);rotation=np.column_stack([x,y,z]);assert np.linalg.det(rotation)>.999
target=roots.mean(0)+along*a.along+normal*a.normal+across*a.radial
c['knife_attachment_r45']=dict(rotation_xyzw=R.from_matrix(rotation).as_quat().tolist(),source_handle_centre=source.tolist(),target_handle_centre=target.tolist(),source_mesh=str(a.mesh),blade_points_to_index_in_forward_grip=True,source_handle_vertex_count=len(handle),native_passed=False,skin_contact_passed=False)
f.write_text(json.dumps(c,indent=2),encoding='utf8');print(json.dumps(c['knife_attachment_r45']))
name=f"eva_unit0{c['rig']}";g=json.loads((a.out/(name+'.geo.json')).read_text());handmesh=json.loads((a.out/(name+'_anatomical_hands_r45.mesh.json')).read_text());part=handmesh['parts']['hand_r'];handraw=np.asarray(part['vertices']).reshape(-1,8);hp=(handraw[:,:3]+part['pivot'])*[-1,1,1]/16;skin=handmesh['jointSkins']['hand_r'];palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T;ms=matrices(g,c,'r',controls(c,'knife','r'));transforms=[ms[n]@np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette];hand=dq_pose(hp,weights,transforms)
knife=(pts*[-1,1,1]/16-source)@rotation.T+target
np.savez_compressed(a.out/'knife_preview.npz',hand=hand,knife=knife,normal=normal,along=along)
