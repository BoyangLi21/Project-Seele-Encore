"""C4 front elbow ring and valid adjacent-owner zero padding, data only."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'
source=BASE/'wrist_adjacent_canonical_C3/sachiel_wrist_adjacent_r44.mesh.json'
out=BASE/'joint_transitions_canonical_C4';out.mkdir(exist_ok=True)
mesh=json.loads(source.read_text('utf8'));fixture=json.loads((BASE.parent/'fixture.json').read_text('utf8'))['actors'][1]
points=np.asarray(fixture['vertices']);ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4);names=mesh['skin']['bones'];changes=[]
for side in('l','r'):
    elbow=points-np.asarray(fixture['joints']['arm_'+side]['joint']);wrist=points-np.asarray(fixture['hands'][side]['pivot'])
    for label,adjacent,region in(
        ('elbow',{'arm_'+side,'forearm_'+side},(elbow[:,1]>-6)&(elbow[:,1]<2)&(np.abs(elbow[:,0])<3)&(np.abs(elbow[:,2])<6)),
        ('wrist',{'forearm_'+side,'hand_'+side},(np.abs(wrist[:,0])<5)&(np.abs(wrist[:,1])<6)&(np.abs(wrist[:,2])<5))):
        group={names.index(n)for n in adjacent};ownership=np.where(np.isin(ids,list(group)),weights,0).sum(axis=1)
        for vertex in np.flatnonzero(region&(ownership>.97)):
            effective={int(b):float(w)for b,w in zip(ids[vertex],weights[vertex])if b in group and w>0}
            total=sum(effective.values());values=sorted(((b,w/total)for b,w in effective.items()),key=lambda item:(-item[1],item[0]))
            chosen=[b for b,w in values];ws=[w for b,w in values]
            # The renderer's stored first slot owns its hemisphere even when
            # that slot is zero. Padding this inspected two-bone region with
            # torso/root selected an unrelated reference after permutation.
            # Zero weights now name the region's existing dominant owner;
            # they still contribute exactly zero to geometry and normals.
            while len(chosen)<4:chosen.append(chosen[0]);ws.append(0.)
            if np.array_equal(ids[vertex],chosen)and np.allclose(weights[vertex],ws,atol=0,rtol=0):continue
            changes.append(dict(vertex=int(vertex),side=side,region=label,removed_remote_weight=float(1-total),old_indices=ids[vertex].tolist(),old_weights=weights[vertex].tolist(),new_indices=chosen,new_weights=ws))
            ids[vertex]=chosen;weights[vertex]=ws
mesh['skin']['indices']=ids.reshape(-1).tolist();mesh['skin']['weights']=weights.reshape(-1).tolist()
target=out/'sachiel_joint_transitions_C4.mesh.json';target.write_text(json.dumps(mesh,separators=(',',':')),'utf8')
overlay=out/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=dict(source_C3_sha256=sha(source),candidate_C4_sha256=sha(target),changed_vertices=len(changes),changes=changes,
    actually_viewed_front_elbow_reference=str((BASE/'elbow_front_actual_reference/actual_neutral_joint_1442.png').resolve()),
    focus=[c for c in changes if c['vertex']in(1442,11388,17952)],
    scope='Complete inspected 6m posterior to 2m anterior elbow ring and existing inspected wrist transition; existing adjacent ownership>97%. Positive ratios preserved. Zero padding names an adjacent dominant owner; no renderer or quaternion gain changed.',
    preserved=['C3 unchanged','topology','positions','UV','normals','bone palette','bindings outside inspected joint transition'],
    native_candidate_run=False,artistic_acceptance=False)
(out/'joint_transition_binding_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items()if k!='changes'},indent=2))
