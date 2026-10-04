"""Diagnostic whole-chain contact fit. Never promotes a pose or installs assets."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.optimize import least_squares
from eva_hand_rig_math_r45 import controls,joint_points
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--diagnose-cmc-bounds',action='store_true');a=p.parse_args()
c=json.loads((a.candidate/'hand_rig_contract.json').read_text());g=json.loads((a.candidate/f"eva_unit0{c['rig']}.geo.json").read_text())
initial=controls(c,'fist','l');points=joint_points(g,c,'l',initial);joints=c['hands']['l']['digits']['thumb']['joints'];names=[j['name']for j in joints]
normal=np.asarray(c['hands']['l']['palmar_normal_bind']);across=points['middle'][2]-points['index'][2];across/=np.linalg.norm(across)
limits=np.array(joints[0]['anatomical_limits_degrees']);lo=np.r_[limits[:,0],10,5];hi=np.r_[limits[:,1],42,32]
if a.diagnose_cmc_bounds:lo=np.array([-120.,-85.,-120.,10.,5.]);hi=np.array([120.,85.,120.,60.,65.])
def pose(x):
 v={k:z.copy()for k,z in initial.items()};v[names[0]]=x[:3];v[names[1]]=np.array([x[3],0,0]);v[names[2]]=np.array([x[4],0,0]);return v
result={};reports=[]
for gap in [.08,.12,.16]:
 # Contact is on the outside of the folded index/middle phalanges.
 target=(points['index'][2]+points['middle'][2])*.5+normal*gap
 direction=across
 target_ip=target-direction*joints[2]['length']
 def residual(x):
  p=joint_points(g,c,'l',pose(x))['thumb']
  return np.r_[(p[-1]-target)*10,(p[-2]-target_ip)*5,(x[3:]-[25,18])*.003]
 fits=[least_squares(residual,start,bounds=(lo,hi),max_nfev=100)for start in [[30,0,0,25,18],[0,25,30,25,18],[60,25,30,25,18]]]
 fit=min(fits,key=lambda x:np.linalg.norm(x.fun));x=fit.x;key=f'contact{round(gap*100)}';result[key]=[x[:3].tolist(),[float(x[3]),0,0],[float(x[4]),0,0]]
 reports.append(dict(case=key,angles=x.tolist(),residual=float(np.linalg.norm(fit.fun)),surface_pass=False,visual_pass=False))
a.out.write_text(json.dumps(result,indent=2),encoding='utf8');a.out.with_suffix('.report.json').write_text(json.dumps(reports,indent=2),encoding='utf8');print(json.dumps(reports))
