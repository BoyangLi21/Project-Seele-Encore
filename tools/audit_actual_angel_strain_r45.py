"""Measure deformation in actual emitted Angel triangles, preserving failure evidence."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);p.add_argument('--original-triangles',type=int,default=10464)
a=p.parse_args();assert not a.out.exists();rows=[];identity=None;first=None
for line in a.witness.open(encoding='utf8'):
    r=json.loads(line)
    if r['kind']=='actual-parsed-weighted-resource':
        identity=r;bind=np.array(r['decoded_vertices'],float).reshape(-1,8)[:,:3]*[-1/16,1/16,1/16]
        triangles=bind.reshape(-1,3,3);edges=triangles[:,[1,2,0]]-triangles
        ids=np.array(r['decoded_indices']).reshape(-1,4)if 'decoded_indices'in r else None
        weights=np.array(r['decoded_weights']).reshape(-1,4)if 'decoded_weights'in r else None
    elif r['kind']=='actual-weighted-emit-vertices'and r['branch']!='wrap-cache':
        assert identity is not None
        actual=np.array(r['vertices_emit_xyz']).reshape(-1,3,3);assert actual.shape==triangles.shape
        linear=np.array(r['actual_emit_to_world_matrix_column_major']).reshape(4,4).T[:3,:3]
        before=np.linalg.norm(edges@linear.T,axis=2)
        after=np.linalg.norm((actual[:,[1,2,0]]-actual)@linear.T,axis=2)
        ratio=after/np.maximum(before,1e-12);valid=before>=.05
        severe=valid&(ratio>4)&(after-before>.5)
        tri=np.unique(np.where(severe)[0]);worst=np.unravel_index(np.where(valid,ratio,0).argmax(),ratio.shape)
        row=dict(game_time=r['game_time'],frame=r['frame'],branch=r['branch'],
                 max_nontrivial_edge_ratio=float(ratio[worst]),worst_triangle=int(worst[0]),
                 worst_before_m=float(before[worst]),worst_after_m=float(after[worst]),
                 severe_triangles=int(len(tri)),original_severe_triangles=int(np.sum(tri<a.original_triangles)),
                 added_severe_triangles=int(np.sum(tri>=a.original_triangles)))
        rows.append(row)
        if first is None and len(tri):
            samples=[]
            for face in tri[:12]:
                sample=dict(triangle=int(face),bind_emit=triangles[face].tolist(),actual_emit=actual[face].tolist(),
                            edge_ratio=ratio[face].tolist(),before_m=before[face].tolist(),after_m=after[face].tolist())
                if ids is not None and weights is not None:
                    sample['influences']=[[dict(bone=identity['bones'][b],weight=float(w))for b,w in zip(ids[v],weights[v])if w>0]for v in range(face*3,face*3+3)]
                samples.append(sample)
            first=dict(**row,triangles=samples)
assert rows,'No actually emitted weighted skin'
report=dict(actual_resource=identity['resource'],actual_pack=identity['source_pack_id'],
    actual_mesh_sha256=identity['source_bytes_sha256'],source_witness_sha256=hashlib.sha256(a.witness.read_bytes()).hexdigest(),
    threshold='Bind edge >=5cm, >4x stretch and >50cm growth; a defect locator, not an artistic pass/fail rule',
    frames=rows,first_observed_severe=first,artistic_acceptance=False,
    scope='Actual submitted skin only; no rig/mesh edits and no claim that changing quaternion signs solves binding defects')
a.out.write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(dict(samples=len(rows),
    worst_ratio=max(r['max_nontrivial_edge_ratio']for r in rows),first_observed_severe=None if first is None else {k:v for k,v in first.items()if k!='triangles'})))
