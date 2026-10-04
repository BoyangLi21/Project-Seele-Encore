"""Refine one identified colliding finger; all other digits and the wrist stay fixed."""
from pathlib import Path
import argparse,json,time,shutil
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from eva_hand_rig_math_r45 import matrices,joint_points
from rebind_anatomical_hand_r45 import dq_pose
from mesh_distance_r45 import TriangleField

p=argparse.ArgumentParser();p.add_argument('--proposal',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--digit',choices=['index','middle','ring','little'],required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
record=json.loads((a.proposal/'proposal.json').read_text('utf8'));source=Path(record['native_source']['candidate']);side=record['side']
c=json.loads((source/'hand_rig_contract.json').read_text('utf8'));name=f"eva_unit0{c['rig']}"
geo=json.loads((source/(name+'.geo.json')).read_text('utf8'));mesh=json.loads((source/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
part=mesh['parts']['hand_'+side];skin=mesh['jointSkins']['hand_'+side]
rest=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T
inverse=[np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
seed={n:np.asarray(v)for n,v in record['controls'].items()};h=c['hands'][side]
joints=h['digits'][a.digit]['joints']+h['digits'].get('cup_'+a.digit,{}).get('joints',[])
variables=[(j['name'],0)for j in joints]+[(joints[0]['name'],2)]
lo=np.asarray([j['anatomical_limits_degrees'][0][0]for j in joints]+[-15.])
hi=np.asarray([j['anatomical_limits_degrees'][0][1]for j in joints]+[15.])
x0=np.asarray([seed[n][axis]for n,axis in variables])
_,unique=np.unique(np.round(rest,6),axis=0,return_index=True)
mass=sum(weights[:,palette.index(j['name'])]for j in joints)
ids=unique[mass[unique]>.0001]
data=np.load(a.proposal/'proposal.npz');weapon=data['weapon'];field=TriangleField(weapon.reshape(-1,3,3))
rotation=Rotation.from_quat(record['local_rotation_xyzw']).as_matrix();palm=np.asarray(record['palm_pivot_native']);shift=np.asarray(record['translation_native'])
def values(x):
    result={n:v.copy()for n,v in seed.items()}
    for (n,axis),v in zip(variables,x):result[n][axis]=v
    return result
def surface(x,full=False):
    ms=matrices(geo,c,side,values(x));transforms=[ms[n]@inv for n,inv in zip(palette,inverse)]
    result=dq_pose(rest if full else rest[ids],weights if full else weights[ids],transforms)
    return (result-palm)@rotation.T+palm+shift
assert np.max(np.abs(surface(x0,True)-data['hand']))<1e-5,'Proposal does not reproduce its complete skin'
tip=h['digits'][a.digit]['joints'][-1]['tip_bind'];near=np.flatnonzero(np.linalg.norm(rest[ids]-tip,axis=1)<.09)
assert len(near)>2
calls=0;began=time.monotonic()
def residual(x):
    global calls
    d,ambiguous=field.query(surface(x));calls+=1
    if calls%100==0:print('eval',calls,'penetration',round(float(max(0,-d.min())),5),flush=True)
    return np.r_[np.maximum(.008-d,0)*30,max(0,float(d[near].min())-.025)*2,(x-x0)*.0003]
starts=[x0.copy()]
for pip in [75.,105.]:
    start=x0.copy();start[1]=pip;start[2]=60;starts.append(start)
best=None
for i,start in enumerate(starts):
    fit=least_squares(residual,np.clip(start,lo+1e-7,hi-1e-7),bounds=(lo,hi),max_nfev=65,diff_step=1e-3,ftol=1e-6,xtol=1e-6)
    d,ambiguous=field.query(surface(fit.x));score=float(np.square(np.maximum(.004-d,0)).sum())
    print('start',i,'score',score,'angles',fit.x.tolist(),flush=True)
    if best is None or score<best[0]:best=(score,fit.x.copy())
final=surface(best[1],True);dist,ambiguous=field.query(final)
record['controls']={n:v.tolist()for n,v in values(best[1]).items()}
record['single_digit_refinement_r45']=dict(source=str(a.proposal.resolve()),digit=a.digit,variables=variables,angles=best[1].tolist(),fixed_other_digits_and_wrist=True,calls=calls,seconds=time.monotonic()-began)
record['final_deepest_vertex_native']=float(max(0,-dist.min()));record['final_inside_vertices']=int(sum(dist<-.003));record['ambiguous_parity_vertices']=int(ambiguous.sum())
record['native_tested']=False;record['visual_accepted']=False;record['installed']=False
np.savez_compressed(a.out/'proposal.npz',hand=final,weapon=weapon,baseline=data['baseline'])
(a.out/'proposal.json').write_text(json.dumps(record,indent=2),'utf8');shutil.copy2(__file__,a.out/'authoring_source.py')
print('Focused digit candidate',record['final_deepest_vertex_native'],record['final_inside_vertices'],flush=True)
