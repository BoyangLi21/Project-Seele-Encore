"""Exact offline hand/handle crossing checks through a closure sequence."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--against',default='hand_r');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);d=np.load(a.input/'surfaces.npz');rows=[]
surfaces=d['hands']if a.against=='hand_r'else np.load(a.input/(a.against+'_surfaces.npz'))['vertices']
for index,hand in enumerate(surfaces):
    knife=d['knives'][index]if 'knives'in d else d['knife'];kv=[Vector(x)for x in knife];kf=np.arange(len(kv)).reshape(-1,3);kt=BVHTree.FromPolygons(kv,kf.tolist(),all_triangles=True)
    hv=[Vector(x)for x in hand];hf=np.arange(len(hv)).reshape(-1,3);ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True)
    hits=[(h,k)for h,k in ht.overlap(kt)if crossing([hv[i]for i in hf[h]],[kv[i]for i in kf[k]])]
    rows.append(dict(index=index,phase=index/(len(d['hands'])-1),crossings=len(hits),examples=hits[:8]));print(index,len(hits),flush=True)
(a.input/('intersections.json'if a.against=='hand_r'else a.against+'_intersections.json')).write_text(json.dumps(rows,indent=2),encoding='utf8')
