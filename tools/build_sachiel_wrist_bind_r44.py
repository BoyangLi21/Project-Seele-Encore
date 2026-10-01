"""C3 actual wrist transition: preserve adjacent forearm/hand proportions."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'
source=BASE/'elbow_base_adjacent_canonical_C2/sachiel_elbow_base_r44.mesh.json'
out=BASE/'wrist_adjacent_canonical_C3';out.mkdir(exist_ok=True)
fixture=json.loads((BASE.parent/'fixture.json').read_text('utf8'))['actors'][1]
mesh=json.loads(source.read_text('utf8'));points=np.asarray(fixture['vertices'])
ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4)
names=mesh['skin']['bones'];changes=[]
for side in('l','r'):
    pivot=np.asarray(fixture['hands'][side]['pivot']);delta=points-pivot
    adjacent={names.index('forearm_'+side),names.index('hand_'+side)}
    ownership=np.where(np.isin(ids,list(adjacent)),weights,0).sum(axis=1)
    region=(np.abs(delta[:,0])<5)&(np.abs(delta[:,1])<6)&(np.abs(delta[:,2])<5)&(ownership>.97)
    for vertex in np.flatnonzero(region):
        effective={int(b):float(w)for b,w in zip(ids[vertex],weights[vertex])if b in adjacent and w>0}
        total=sum(effective.values());values=sorted(((b,w/total)for b,w in effective.items()),key=lambda item:(-item[1],item[0]))
        chosen=[b for b,w in values];ws=[w for b,w in values]
        while len(chosen)<4:chosen.append(0);ws.append(0.)
        if np.array_equal(ids[vertex],chosen)and np.allclose(weights[vertex],ws,atol=0,rtol=0):continue
        changes.append(dict(vertex=int(vertex),side=side,actual_wrist_offset_blocks=delta[vertex].tolist(),removed_remote_weight=float(1-total),
                            old_indices=ids[vertex].tolist(),old_weights=weights[vertex].tolist(),new_indices=chosen,new_weights=ws))
        ids[vertex]=chosen;weights[vertex]=ws
mesh['skin']['indices']=ids.reshape(-1).tolist();mesh['skin']['weights']=weights.reshape(-1).tolist()
target=out/'sachiel_wrist_adjacent_r44.mesh.json';target.write_text(json.dumps(mesh,separators=(',',':')),'utf8')
overlay=out/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=dict(source_C2_sha256=sha(source),candidate_C3_sha256=sha(target),changed_vertices=len(changes),changes=changes,
    actually_viewed_reference=str((BASE/'wrist_actual_reference/actual_neutral_wrist_11388.png').resolve()),
    focus=[c for c in changes if c['vertex']in(11388,17952)],
    region='Actual inspected wrist cuff around measured hand pivot: lateral<5, longitudinal<6, vertical<5 blocks; existing forearm+hand ownership>97%',
    preserved=['C2 unchanged','geometry','UV','normals','topology','palette','adjacent hand/forearm weight ratio','all weights outside inspected wrist transition'],
    native_renderer_reference_changed=False,artistic_acceptance=False,native_candidate_run=False)
(out/'wrist_binding_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items()if k!='changes'},indent=2))
