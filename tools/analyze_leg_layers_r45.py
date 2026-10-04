"""First-error comparison of actual native leg matrices and same-call pose layers."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation
p=argparse.ArgumentParser();p.add_argument('trace',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',default='normal_moving');a=p.parse_args();data=json.loads(a.trace.read_text('utf8'));rows=[r for r in data['samples']if r['stage']==a.stage];chosen={}
for r in rows:
 key=r['tick']
 if key not in chosen or r['partial']<chosen[key]['partial']:chosen[key]=r
rows=sorted(chosen.values(),key=lambda r:r['tick']);bones=['leg_l','leg_r','shin_l','shin_r','ankle_l','ankle_r','foot_l','foot_r'];out=[]
def rot(m):
 x=np.asarray(m).reshape(4,4).T[:3,:3];x=x/np.linalg.norm(x,axis=0)[None,:];return Rotation.from_matrix(x)
for bone in bones:
 differences=[];changes=[]
 for i,r in enumerate(rows):
  wanted=r['layers']['final'][bone]['matrix'];actual=r['rendered'][bone];differences.append((rot(wanted).inv()*rot(actual)).magnitude()*180/np.pi)
  if i:
   prior=rows[i-1];dt=r['tick']-prior['tick'];change=(rot(prior['rendered'][bone]).inv()*rot(actual)).magnitude()*180/np.pi
   if change>20:
    layers={k:(rot(prior['layers'][k][bone]['matrix']).inv()*rot(r['layers'][k][bone]['matrix'])).magnitude()*180/np.pi for k in r['layers']}
    changes.append(dict(tick=r['tick'],review_tick=r['review_tick'],previous_review_tick=prior['review_tick'],delta_ticks=dt,rotation_change_deg=change,layer_changes_deg=layers,actual_owner=r['actual_support_ownership']))
 out.append(dict(bone=bone,renderer_vs_final_max_deg=float(max(differences,default=0)),first_over20deg=changes[:1],largest_change=sorted(changes,key=lambda r:r['rotation_change_deg'],reverse=True)[:1]))
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(dict(source=str(a.trace),same_tick_samples=len(rows),bones=out,scope='Actual submitted named leg palettes compared with same-call pose layers; angular events are findings, not generic quality pass or proof of deformation'),indent=2),'utf8')
print('Same-tick leg frames',len(rows));print([(r['bone'],round(r['renderer_vs_final_max_deg'],4),round(r['largest_change'][0]['rotation_change_deg'],2) if r['largest_change'] else 0) for r in out])
