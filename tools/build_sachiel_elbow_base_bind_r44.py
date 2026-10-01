"""Independent C2: posterior elbow attachment uses only its adjacent arm bones.

C1 stays frozen. The inspected bases retain upper/forearm proportions; distant
hand and torso contamination is removed only inside the measured attachment.
"""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'
SOURCE=BASE/'elbow_forearm_canonical_candidate/sachiel_elbow_forearm_r44.mesh.json'
OUT=BASE/'elbow_base_adjacent_canonical_C2';OUT.mkdir(exist_ok=True)
mesh=json.loads(SOURCE.read_text('utf8'));fixture=json.loads((BASE.parent/'fixture.json').read_text('utf8'))['actors'][1]
points=np.asarray(fixture['vertices']);ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4)
names=mesh['skin']['bones'];changes=[]
for side in ('l','r'):
    delta=points-np.asarray(fixture['joints']['arm_'+side]['joint'])
    adjacent={names.index('arm_'+side),names.index('forearm_'+side)}
    ownership=np.where(np.isin(ids,list(adjacent)),weights,0).sum(1)
    region=(delta[:,1]<-1)&(delta[:,1]>-6)&(np.abs(delta[:,0])<3)&(np.abs(delta[:,2])<6)&(ownership>.97)
    for vertex in np.flatnonzero(region):
        effective={int(b):float(w) for b,w in zip(ids[vertex],weights[vertex]) if b in adjacent and w>0}
        total=sum(effective.values());values=sorted(((b,w/total)for b,w in effective.items()),key=lambda item:(-item[1],item[0]))
        chosen=[b for b,w in values];ws=[w for b,w in values]
        while len(chosen)<4:chosen.append(0);ws.append(0.)
        if np.array_equal(ids[vertex],chosen) and np.allclose(weights[vertex],ws,atol=0,rtol=0):continue
        changes.append(dict(vertex=int(vertex),side=side,neutral_offset_from_elbow=delta[vertex].tolist(),removed_remote_weight=float(1-total),
                            before_indices=ids[vertex].tolist(),before_weights=weights[vertex].tolist(),after_indices=chosen,after_weights=ws))
        ids[vertex]=chosen;weights[vertex]=ws
mesh['skin']['indices']=ids.reshape(-1).tolist();mesh['skin']['weights']=weights.reshape(-1).tolist()
target=OUT/'sachiel_elbow_base_r44.mesh.json';target.write_text(json.dumps(mesh,separators=(',',':')),'utf8')
overlay=OUT/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
report=dict(source_C1_sha256=sha(SOURCE),candidate_C2_sha256=sha(target),changed_vertices=len(changes),changes=changes,
            actual_viewed_reference=str((BASE/'base_boundary/actual_neutral_elbow_base_3305_13745.png').resolve()),
            inspected_error_points=[r for r in changes if r['vertex'] in (3305,13745)],
            boundary='Posterior 1--6m attachment strip, lateral <3m, vertical <6m, existing adjacent upper+forearm ownership >97%; preserves their ratio, no global tiny-weight cutoff.',
            preserved=['C1 immutable','geometry','normals','UV','topology','bone palette','weights outside inspected attachment'],
            artistic_acceptance=False,native_validated=False)
(OUT/'elbow_base_binding_receipt.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items()if k!='changes'},indent=2))
