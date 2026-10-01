"""Cache exact rigid plane extrema, preserving original support subsets.

The actual render mesh is untouched. Convex hull vertices have the same
minimum against any plane as the original rigid vertices. The proximal and
forefoot subsets are selected on the original geometry before reduction.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial import ConvexHull


def extreme(points):
    values=np.unique(points,axis=0)
    if len(values)<4:return values
    centred=values-values.mean(axis=0);_,singular,basis=np.linalg.svd(centred,full_matrices=False)
    rank=int((singular>max(singular[0],1)*1e-10).sum())
    if rank==0:return values[:1]
    if rank==1:
        projected=centred@basis[0];return values[[int(projected.argmin()),int(projected.argmax())]]
    projected=centred@basis[:rank].T
    return values[ConvexHull(projected).vertices]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fixture',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    data=json.loads(args.fixture.read_text('utf8'))['actors'][0]
    points=np.asarray(data['vertices'],dtype=np.float64);ids=np.asarray(data['influences']);weights=np.asarray(data['weights'])
    owner=ids[np.arange(len(ids)),weights.argmax(axis=1)]
    cache={};report=[];rng=np.random.default_rng(44);directions=np.r_[np.eye(3),-np.eye(3),rng.normal(size=(32,3))]
    directions/=np.linalg.norm(directions,axis=1,keepdims=True)
    def save(key,shape):
        if not len(shape):return
        reduced=extreme(shape);error=float(np.max(np.abs((shape@directions.T).min(axis=0)-(reduced@directions.T).min(axis=0))))
        if error>1e-7:raise ValueError('Original rigid plane minimum changed: '+key+' '+str(error))
        cache[key]=reduced;report.append(dict(key=key,original_points=len(shape),extreme_points=len(reduced),sample_plane_minimum_error_blocks=error))
    for index,bone in enumerate(data['bones']):
        name=bone['name'];shape=points[owner==index]
        if name.startswith(('arm_','forearm_','leg_','shin_','hand_','foot_','finger_'))or name in('head','torso_lower','torso_upper','pylon_l','pylon_r'):
            save('full__'+name,shape)
    for side in('l','r'):
        for family,lower in(('arm','forearm_'),('leg','shin_')):
            index=next(i for i,b in enumerate(data['bones'])if b['name']==lower+side);shape=points[owner==index]
            joint=np.asarray(data['joints'][family+'_'+side]['joint']);tip=np.asarray(data['joints'][family+'_'+side]['end']);axis=tip-joint;length=np.linalg.norm(axis);axis/=length
            longitudinal=(shape-joint)@axis;subset=shape[(longitudinal>=-length*.1)&(longitudinal<=length*.25)]
            if not len(subset):subset=shape[np.argsort(np.linalg.norm(shape-joint,axis=1))[:max(3,len(shape)//10)]]
            save('proximal__'+lower+side,subset)
        boot=np.asarray(data['toes'][side]['vertices']);front=boot[boot[:,1]>=np.percentile(boot[:,1],85)]
        save('boot__'+side,boot);save('forefoot__'+side,front)
    args.out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.out/'rigid_floor_extrema.npz',**cache)
    receipt=dict(actor=data['name'],geo_sha256=data['geo_sha256'],mesh_sha256=data['mesh_sha256'],
        original_neutral_vertices_sha256=hashlib.sha256(points.tobytes()).hexdigest(),point_count=len(points),parts=report,
        actual_render_mesh_changed=False,scope='Exact rigid plane minima only. Proximal/forefoot subsets selected before reduction. No floor-contact or art acceptance inferred.')
    (args.out/'rigid_floor_extrema_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8')
    print(json.dumps(dict(actor=data['name'],parts=len(report),original_points=sum(r['original_points']for r in report),extreme_points=sum(r['extreme_points']for r in report))))


if __name__=='__main__':main()
