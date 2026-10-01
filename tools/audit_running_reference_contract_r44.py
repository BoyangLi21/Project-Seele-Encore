"""Actual native pose: ordering, zero padding, and independent quaternion signs."""
from pathlib import Path
import itertools,json
import numpy as np
from replay_rigged_angel_witness_r44 import skin

ROOT=Path(__file__).resolve().parents[1];out=ROOT/'artifacts/rebuild_r44/combat/native_skin_witness/actual_first_slot_v1'
comparisons=json.loads((out/'same_pose_float32_comparisons.json').read_text('utf8'))
selected=max(comparisons['samples'],key=lambda r:max(c['same_native_palette_world_max_delta_blocks'] for c in r['same_pose_reference_comparisons']))['frame']
identity=sample=None
for line in (out/'actual_rigged_skin.jsonl').open('r',encoding='utf8'):
    row=json.loads(line)
    if row['kind']=='actual-parsed-weighted-resource':identity=row
    if row['kind']=='actual-weighted-emit-vertices' and row['frame']==selected:sample=row;break
source=np.asarray(identity['decoded_vertices'],np.float32).reshape(-1,8);points=source[:,:3].astype(float)*[-1/16,1/16,1/16]
ids=np.asarray(identity['parsed_indices']).reshape(-1,4);weights=np.asarray(identity['parsed_weights'],np.float32).reshape(-1,4).astype(float)
palette=sample['actual_palette'];real=np.asarray([r['actual_real_quaternion_xyzw'] for r in palette])[:,[3,0,1,2]];dual=np.asarray([r['actual_dual_quaternion_xyzw'] for r in palette])[:,[3,0,1,2]]
matrices=np.asarray([r['actual_root_relative_matrix_column_major'] for r in palette]).reshape(-1,4,4).transpose(0,2,1);scaled=np.asarray([r['scaled_lbs_branch'] for r in palette],bool)
chosen=np.unique(np.r_[4184,15592,np.flatnonzero(weights[:,0]==0)])
p,j,w=points[chosen],ids[chosen],weights[chosen];baseline=skin(p,j,w,real,dual,matrices,scaled,'running-sum')[0]
permutation=[]
for order in itertools.permutations(range(4)):
    value=skin(p,j[:,order],w[:,order],real,dual,matrices,scaled,'running-sum')[0];error=np.linalg.norm(value-baseline,axis=1);worst=int(error.argmax())
    permutation.append(dict(order=order,maximum_emit_space_delta=float(error[worst]),actual_vertex=int(chosen[worst])))
sign_max=0.;sign_cases=0
for signs in itertools.product((-1.,1.),repeat=4):
    # Change each selected vertex's own four palette quaternion signs in a
    # tiny local palette; real+dual always change together (same rigid pose).
    for point,bones,ws,want in zip(p,j,w,baseline):
        q=real[bones]*np.asarray(signs)[:,None];d=dual[bones]*np.asarray(signs)[:,None]
        value=skin(point[None],np.arange(4)[None],ws[None],q,d,matrices[bones],scaled[bones],'running-sum')[0][0]
        sign_max=max(sign_max,float(np.linalg.norm(value-want)));sign_cases+=1
padding=[]
for at,vertex in enumerate(chosen):
    if not (w[at]==0).any():continue
    positive=np.flatnonzero(w[at]>0);effective_ids=j[at,positive];effective_weights=w[at,positive]
    for hole in range(4):
        order=[k for k in range(4) if k!=hole];test_ids=np.zeros((1,4),int);test_weights=np.zeros((1,4));test_ids[0,order]=effective_ids;test_weights[0,order]=effective_weights
        value=skin(p[at:at+1],test_ids,test_weights,real,dual,matrices,scaled,'running-sum')[0][0]
        padding.append(dict(actual_vertex=int(vertex),zero_slot=hole,maximum_emit_space_delta=float(np.linalg.norm(value-baseline[at]))))
report=dict(actual_native_frame=selected,actual_source_sha256=identity['source_bytes_sha256'],selected_actual_vertices=chosen.tolist(),
    weight_order_permutation=permutation,maximum_permutation_emit_delta=max(r['maximum_emit_space_delta'] for r in permutation),
    padding_cases=padding,maximum_padding_emit_delta=max(r['maximum_emit_space_delta'] for r in padding),
    independent_palette_quaternion_sign_cases=sign_cases,maximum_independent_sign_emit_delta=sign_max,
    contract='Running sum preserves exactly the source four-slot order and skips zeros. Independently negating each real+dual pair represents the same pose. General slot permutation is not promised invariant; ambiguous cross-region bind must be repaired or a shared canonical ordering chosen and reverified in both DCC and engine.',
    scope='Actual captured native pose/decoded mesh, independent numerical contract tests only; actual float32 world reproduction is in the separate JOML bitmatch proof',artistic_acceptance=False)
(out/'running_order_padding_sign_contract.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k not in ('weight_order_permutation','padding_cases')},indent=2))
