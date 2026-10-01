"""C6 extends the inspected wrist transition into its actual distal palm."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'
source=BASE/'shoulder_transitions_canonical_C5/sachiel_shoulder_transitions_C5.mesh.json'
out=BASE/'palm_transitions_canonical_C6';out.mkdir(exist_ok=True)
mesh=json.loads(source.read_text('utf8'));fixture=json.loads((BASE.parent/'fixture.json').read_text('utf8'))['actors'][1]
points=np.asarray(fixture['vertices']);ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4);names=mesh['skin']['bones'];changes=[]
for side in('l','r'):
    delta=points-np.asarray(fixture['hands'][side]['pivot']);adjacent={names.index('forearm_'+side),names.index('hand_'+side)}
    ownership=np.where(np.isin(ids,list(adjacent)),weights,0).sum(axis=1)
    region=(np.abs(delta[:,0])<5)&(delta[:,1]>=6)&(delta[:,1]<9)&(np.abs(delta[:,2])<5)&(ownership>.97)
    for vertex in np.flatnonzero(region):
        effective={int(b):float(w)for b,w in zip(ids[vertex],weights[vertex])if b in adjacent and w>0};total=sum(effective.values())
        values=sorted(((b,w/total)for b,w in effective.items()),key=lambda item:(-item[1],item[0]));chosen=[b for b,w in values];ws=[w for b,w in values]
        while len(chosen)<4:chosen.append(chosen[0]);ws.append(0.)
        changes.append(dict(vertex=int(vertex),side=side,actual_palm_offset=delta[vertex].tolist(),removed_remote_weight=float(1-total),old_indices=ids[vertex].tolist(),old_weights=weights[vertex].tolist(),new_indices=chosen,new_weights=ws))
        ids[vertex]=chosen;weights[vertex]=ws
mesh['skin']['indices']=ids.reshape(-1).tolist();mesh['skin']['weights']=weights.reshape(-1).tolist()
target=out/'sachiel_palm_transitions_C6.mesh.json';target.write_text(json.dumps(mesh,separators=(',',':')),'utf8')
overlay=out/'overlay/assets/projectseele/mesh/sachiel.mesh.json';overlay.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,overlay)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=dict(source_C5_sha256=sha(source),candidate_C6_sha256=sha(target),changed_vertices=len(changes),changes=changes,
    reference='Actual viewed whole wrist/palm/claw image wrist_actual_reference/actual_neutral_wrist_11388.png; remaining vertex10697 lies6.83m forward of this same measured wrist in the actual palm.',
    focus=[r for r in changes if r['vertex']==10697],preserved=['C5 unchanged','geometry','UV','normals','topology','positive hand/forearm ratio','bindings outside actual distal palm'],
    native_candidate_run=False,artistic_acceptance=False)
(out/'palm_transition_binding_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items()if k!='changes'},indent=2))
