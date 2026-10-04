"""Full triangle crossings for explicit support poses against the real cannon."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
p.add_argument('--labels',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
labels=np.load(a.labels)['labels'];rows=[]
for candidate in a.input.iterdir():
    if not(candidate/'proposal.npz').exists():continue
    d=np.load(candidate/'proposal.npz');h=d['hand'];w=d['weapon']
    hv=[Vector(v)for v in h];wv=[Vector(v)for v in w]
    hf=np.arange(len(h)).reshape(-1,3);wf=np.arange(len(w)).reshape(-1,3)
    ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True);wt=BVHTree.FromPolygons(wv,wf.tolist(),all_triangles=True)
    hits=[(int(x),int(y))for x,y in ht.overlap(wt)if crossing([hv[i]for i in hf[x]],[wv[i]for i in wf[y]])]
    row=dict(case=candidate.name,crossings=len(hits),by_region={str(k):sum(labels[x]==k for x,y in hits)for k in [-1,0,1,2,3,4]},
             nearest_surface_gap=float(min(wt.find_nearest(v)[3]for v in hv)),native=False,art_accepted=False)
    row['by_region']={k:int(v)for k,v in row['by_region'].items()};rows.append(row)
out=a.input/'complete_contacts.json';assert not out.exists();out.write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(rows))
