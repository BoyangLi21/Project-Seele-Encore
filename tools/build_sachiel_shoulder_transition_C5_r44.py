"""C5 inspected shoulder seam keeps only its true torso/upper-arm pair."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'
source=BASE/'joint_transitions_canonical_C4/sachiel_joint_transitions_C4.mesh.json'
out=BASE/'shoulder_transitions_canonical_C5';out.mkdir(exist_ok=True)
mesh=json.loads(source.read_text('utf8'));fixture=json.loads((BASE.parent/'fixture.json').read_text('utf8'))['actors'][1]
points=np.asarray(fixture['vertices']);ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4);names=mesh['skin']['bones'];changes=[]
for side in('l','r'):
    offset=points-np.asarray(fixture['joints']['arm_'+side]['upper'])
    adjacent={names.index('torso_upper'),names.index('arm_'+side)}
    ownership=np.where(np.isin(ids,list(adjacent)),weights,0).sum(axis=1)
    region=(np.abs(offset[:,0])<6)&(np.abs(offset[:,1])<6)&(np.abs(offset[:,2])<6)&(ownership>.97)
    for vertex in np.flatnonzero(region):
        effective={int(b):float(w)for b,w in zip(ids[vertex],weights[vertex])if b in adjacent and w>0}
        total=sum(effective.values());values=sorted(((b,w/total)for b,w in effective.items()),key=lambda item:(-item[1],item[0]))
        chosen=[b for b,w in values];ws=[w for b,w in values]
        while len(chosen)<4:chosen.append(chosen[0]);ws.append(0.)
        if np.array_equal(ids[vertex],chosen)and np.allclose(weights[vertex],ws,atol=0,rtol=0):continue
        changes.append(dict(vertex=int(vertex),side=side,actual_shoulder_offset=offset[vertex].tolist(),removed_distal_forearm_hand_weight=float(1-total),old_indices=ids[vertex].tolist(),old_weights=weights[vertex].tolist(),new_indices=chosen,new_weights=ws))
        ids[vertex]=chosen;weights[vertex]=ws
mesh['skin']['indices']=ids.reshape(-1).tolist();mesh['skin']['weights']=weights.reshape(-1).tolist()
target=out/'sachiel_shoulder_transitions_C5.mesh.json';target.write_text(json.dumps(mesh,separators=(',',':')),'utf8')
overlay=out/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=dict(source_C4_sha256=sha(source),candidate_C5_sha256=sha(target),changed_vertices=len(changes),changes=changes,
    actually_viewed_shoulder_reference=str((BASE/'shoulder_actual_reference/actual_neutral_joint_13256.png').resolve()),
    focus=[r for r in changes if r['vertex']==13256],scope='Actual shoulder cap/torso transition, within6 blocks of the real shoulder socket and existing torso_upper+arm ownership>97%. Preserves their ratio, removes distal hand/forearm contamination and names adjacent dominant owner in zero pads.',
    preserved=['C4 unchanged','geometry','normals','UV','topology','bone palette','bindings outside inspected shoulder transition'],
    native_renderer_changed=False,native_candidate_run=False,artistic_acceptance=False)
(out/'shoulder_transition_binding_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items()if k!='changes'},indent=2))
