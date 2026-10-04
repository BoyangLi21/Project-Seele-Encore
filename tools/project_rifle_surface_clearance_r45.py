"""Resolve only a tiny rigid contact margin, then recheck every hand triangle.

This cannot repair an anatomically wrong pose and never installs its output.
"""
from pathlib import Path
import argparse,json,sys,itertools,hashlib
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing

p=argparse.ArgumentParser();p.add_argument('--proposal',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--jitter',type=float,default=0,help='Require all eight sub-voxel translation corners to clear too')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out.mkdir(parents=True,exist_ok=False)
d=np.load(a.proposal/'proposal.npz');hand=d['hand'];weapon=d['weapon'];baseline=d['baseline']
wv=[Vector(v)for v in weapon];wf=np.arange(len(weapon)).reshape(-1,3);hf=np.arange(len(hand)).reshape(-1,3)
wt=BVHTree.FromPolygons(wv,wf.tolist(),all_triangles=True)
def count(offset):
    hv=[Vector(v)for v in hand+offset];ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True)
    return sum(crossing([hv[i]for i in hf[h]],[wv[i]for i in wf[w]])for h,w in ht.overlap(wt))
assert 0<=a.jitter<=.001
def robust(offset):
    return a.jitter==0 or all(count(offset+np.asarray(v)*a.jitter)==0 for v in itertools.product([-1,1],repeat=3))
before=count(np.zeros(3));chosen=np.zeros(3)if before==0 and robust(np.zeros(3))else None;trials=[]
for step in [.001,.002,.004,.008]:
    if chosen is not None:break
    directions=sorted((v for v in itertools.product([-1,0,1],repeat=3)if any(v)),key=lambda x:sum(v*v for v in x))
    for direction in directions:
        offset=np.asarray(direction,dtype=float)*step;crossings=count(offset)
        trials.append(dict(offset=offset.tolist(),crossings=int(crossings)))
        if crossings==0 and robust(offset):chosen=offset;break
proof=dict(before_crossings=int(before),clear=chosen is not None,trials=trials,translation_jitter_native=a.jitter,visual_accepted=False,native_tested=False)
(a.out/'projection_report.json').write_text(json.dumps(proof,indent=2),'utf8')
if chosen is None:raise SystemExit('Small contact-margin projection could not clear this pose; do not install')
record=json.loads((a.proposal/'proposal.json').read_text('utf8'))
record['translation_native']=(np.asarray(record['translation_native'])+chosen).tolist()
record['margin_projection_r45']=dict(source=str(a.proposal.resolve()),source_sha256=hashlib.sha256((a.proposal/'proposal.json').read_bytes()).hexdigest(),offset=chosen.tolist(),exact_crossings_before=int(before),exact_crossings_after=0)
record['prior_solver_distance_metrics']={k:record.pop(k)for k in ['final_deepest_vertex_native','final_inside_vertices','ambiguous_parity_vertices']if k in record}
record['note']='Rigid margin correction against full triangles; signed distance and self-contact must be rechecked, then actual native runtime and art'
np.savez_compressed(a.out/'proposal.npz',hand=hand+chosen,weapon=weapon,baseline=baseline)
(a.out/'proposal.json').write_text(json.dumps(record,indent=2),'utf8')
print('Full-surface margin correction',before,'to 0; offset native',chosen.tolist(),flush=True)
