"""Private anatomical binding candidate for the two observed rear elbow spurs.

The regions follow the actually viewed hard spurs, not nearest-pivot guessing.
Original topology, position, UV, normals, and production resources are kept.
"""
from pathlib import Path
import argparse,hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13'
ap=argparse.ArgumentParser();ap.add_argument('--baseline',choices=('sole','canonical'),default='sole');args=ap.parse_args()
OUT=BASE/('bind_region/elbow_forearm_candidate' if args.baseline=='sole' else 'bind_region/elbow_forearm_canonical_candidate')
OUT.mkdir(exist_ok=True)
fixture=json.loads((BASE/'fixture.json').read_text('utf8'));data=fixture['actors'][1]
asset=BASE/'sachiel_sole_bind_r44.mesh.json' if args.baseline=='sole' else ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele/mesh/sachiel.mesh.json'
source=json.loads(asset.read_text('utf8'))
if args.baseline=='canonical':
    data['influences']=np.asarray(source['skin']['indices']).reshape(-1,4).tolist();data['weights']=np.asarray(source['skin']['weights']).reshape(-1,4).tolist()
indices=np.asarray(data['influences']);weights=np.asarray(data['weights']);points=np.asarray(data['vertices'])
if not np.array_equal(np.asarray(source['skin']['indices']).reshape(-1,4),indices) or not np.allclose(np.asarray(source['skin']['weights']).reshape(-1,4),weights,atol=0,rtol=0):
    raise ValueError('Actual source mesh and viewed fixture decoded binding identities disagree')
new_ids=indices.copy();new_weights=weights.copy();changes=[]
for side in ('l','r'):
    joint=np.asarray(data['joints']['arm_'+side]['joint']);delta=points-joint
    # Behind the measured elbow, narrow in lateral/vertical extent. Both
    # marked tips (4184/15592) lie 14.73 blocks rearward and 3.25 below it.
    # The strip at 4--6 blocks is an explicitly authored attachment transition.
    mask=(delta[:,1]<-4)&(np.abs(delta[:,0])<3)&(np.abs(delta[:,2])<6)
    ids=np.flatnonzero(mask)
    forearm=next(i for i,b in enumerate(data['bones']) if b['name']=='forearm_'+side)
    for vertex in ids:
        u=min(1.,max(0.,(-delta[vertex,1]-4)/2));u=u*u*(3-2*u)
        effective={int(b):float(w)*(1-u) for b,w in zip(indices[vertex],weights[vertex]) if w>0}
        effective[forearm]=effective.get(forearm,0.)+u
        values=sorted(effective.items(),key=lambda pair:(-pair[1],pair[0]))[:4]
        chosen=[b for b,w in values];ws=[w for b,w in values]
        while len(chosen)<4:chosen.append(0);ws.append(0.)
        new_ids[vertex]=chosen;new_weights[vertex]=ws
        changes.append(dict(vertex=int(vertex),side=side,neutral_world=points[vertex].tolist(),
                            forearm_ownership_blend=u,old_indices=indices[vertex].tolist(),old_weights=weights[vertex].tolist(),
                            new_indices=chosen,new_weights=ws))
data['influences']=new_ids.tolist();data['weights']=new_weights.tolist()
data['skin_scope']+=' Private candidate: measured rear hard elbow spurs follow forearm with explicit 4--6 block root transition; artistic/native validation unverified.'
source['skin']['indices']=new_ids.reshape(-1).tolist();source['skin']['weights']=new_weights.reshape(-1).tolist()
target=OUT/'sachiel_elbow_forearm_r44.mesh.json';target.write_text(json.dumps(source,separators=(',',':')),'utf8')
overlay=OUT/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
(OUT/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
report=dict(source_mesh_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),candidate_mesh_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    exact_baseline=args.baseline,baseline_path=str(asset),temporary_native_overlay=str((OUT/'overlay').resolve()),
    changed_vertices=len(changes),tip_vertices=[r for r in changes if r['vertex'] in (4184,15592)],changes=changes,
    inspected_reference='counter_v13/bind_region/neutral_elbow_spikes.png (actually viewed); these are rear elbow hard spurs, not hands',
    method='Private ownership candidate only. Hard spur forearm binding plus explicit base transition, positive influences sorted by weight/stable identity; actual RiggedAngel first-slot rule still needs native A/B.',
    preserved=['topology','decoded positions/normals/UVs','bone list','original sole binding','production resources'],
    native_validated=False,artistic_acceptance=False)
(OUT/'elbow_binding_receipt.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2))
