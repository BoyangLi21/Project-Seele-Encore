"""Refine an existing bounded corrective from a measured transition crease.

The source skin/rig is unchanged. Dividing by the actual current driver weight
transfers a small residual sculpt to the same existing shape; all transitions
and the endpoint must then be checked again. No new runtime animation owner.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from eva_hand_rig_math_r45 import controls,matrices
from rebind_anatomical_hand_r45 import dq_pose
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--posed',type=Path,required=True);p.add_argument('--sculpt',type=Path,required=True)
p.add_argument('--side',choices=['l','r'],required=True);p.add_argument('--start',required=True)
p.add_argument('--weight',type=float,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'));name=f"eva_unit0{c['rig']}"
g=json.loads((a.candidate/(name+'.geo.json')).read_text('utf8'))
m=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'));before=copy.deepcopy(m)
old=np.load(a.posed);fixed=np.load(a.sculpt/'fist_pad_corrected.npz')
assert np.array_equal(old['rest'],fixed['rest'])and np.array_equal(old['faces'],fixed['faces'])
first=controls(c,a.start,a.side);last=controls(c,'fist',a.side)
ms=matrices(g,c,a.side,{n:first[n]*(1-a.weight)+last[n]*a.weight for n in first})
parents={b['name']:b.get('parent')for b in g['minecraft:geometry'][0]['bones']}
corrective=m['jointSkins']['hand_'+a.side]['contactCorrectiveR45'];distance=0
for n,q in corrective['local_quaternion_xyzw'].items():
    actual=Rotation.from_matrix(ms[parents[n]][:3,:3].T@ms[n][:3,:3]).as_quat()
    distance=max(distance,2*np.arccos(np.clip(abs(actual@np.asarray(q)),0,1)))
w=float(np.clip(1-distance/np.radians(corrective['activation_degrees']),0,1));w=w*w*(3-2*w)
assert w>.3,'Do not amplify a residual outside the corrective support'
delta=(fixed['vertices']-old['vertices'])/w
assert np.linalg.norm(delta,axis=1).max()<.025,'Residual is too large for a crease refinement'
faces=old['faces'];_,weld=np.unique(np.round(old['rest'],7),axis=0,return_inverse=True)
def normals(v):
    n=np.zeros((int(weld.max())+1,3));f=np.cross(v[faces[:,1]]-v[faces[:,0]],v[faces[:,2]]-v[faces[:,0]])
    for i in range(3):np.add.at(n,weld[faces[:,i]],f)
    n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
    return n[weld]
dn=(normals(fixed['vertices'])-normals(old['vertices']))/w;tree=cKDTree(old['rest']);records=[]
for side in ['l','r']:
    part=m['parts']['hand_'+side];rest=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
    mirror=np.array([-1,1,1])if side!=a.side else np.ones(3)
    error,index=tree.query(rest*mirror);assert error.max()<1e-6
    pose=matrices(g,c,side,controls(c,'fist',side));rotation=pose['hand_'+side][:3,:3]
    dp=(delta[index]*mirror@rotation)*[-1,1,1]*16;normal=(dn[index]*mirror@rotation)*[-1,1,1]
    cor=m['jointSkins']['hand_'+side]['contactCorrectiveR45'];rows={int(r[0]):np.asarray(r[1:])for r in cor['vertex_index_position_normal_delta']}
    for i in np.flatnonzero(np.linalg.norm(dp,axis=1)>1e-8):rows[int(i)]=rows.get(int(i),np.zeros(6))+np.r_[dp[i],normal[i]]
    # Rebuild bounded endpoint normals from the corrected surface. Summing
    # intermediate normal differences divided by a driver weight can exceed
    # the difference of two unit normals even when geometry is valid.
    sk=m['jointSkins']['hand_'+side];names=list(sk['influences'])
    weights=np.asarray([sk['influences'][n]for n in names]).T
    transforms=[pose[n]@np.asarray(sk['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
    endpoint=dq_pose(rest,weights,transforms);corrected=endpoint.copy()
    for i,r in rows.items():corrected[i]+=(r[:3]*[-1,1,1]/16)@rotation.T
    _,side_weld=np.unique(np.round(rest,7),axis=0,return_inverse=True)
    def endpoint_normals(v):
        n=np.zeros((int(side_weld.max())+1,3));f=np.cross(v[faces[:,1]]-v[faces[:,0]],v[faces[:,2]]-v[faces[:,0]])
        for j in range(3):np.add.at(n,side_weld[faces[:,j]],f)
        n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
        return n[side_weld]
    n_delta=(endpoint_normals(corrected)-endpoint_normals(endpoint))@rotation*[-1,1,1]
    for i in rows:rows[i][3:]=n_delta[i]
    cor['vertex_index_position_normal_delta']=[[i,*rows[i].tolist()]for i in sorted(rows)]
    assert np.abs(np.asarray(cor['vertex_index_position_normal_delta'])[:,1:]).max()<2
    records.append(dict(side=side,residual_vertices=int(np.count_nonzero(np.linalg.norm(dp,axis=1)>1e-8))))
check=copy.deepcopy(m)
for n in check['jointSkins']:check['jointSkins'][n]['contactCorrectiveR45']=before['jointSkins'][n]['contactCorrectiveR45']
assert check==before
(a.out/(name+'.geo.json')).write_bytes((a.candidate/(name+'.geo.json')).read_bytes())
(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(m,separators=(',',':')),'utf8')
for file in [name+'.geo.json',name+'_anatomical_hands_r45.mesh.json']:c['weapon_grip_source_r45'][file]=hashlib.sha256((a.out/file).read_bytes()).hexdigest()
c['transition_crease_refinement_r45']=dict(source=str(a.candidate.resolve()),sculpt=str(a.sculpt.resolve()),driver_weight=w,records=records,
    topology_bones_rest_unchanged=True,transitions_rechecked=False,native_tested=False,art_accepted=False)
(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8');print('Refined existing corrective with actual weight',w)
