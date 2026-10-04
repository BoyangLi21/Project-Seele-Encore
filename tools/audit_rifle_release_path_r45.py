"""Blender exact surface sweep for measured support-hand release proposals."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.input/'surface_sweep.json';assert not out.exists()
data=np.load(a.input/'geometry.npz');gun=[Vector(v)for v in data['weapon']]
gf=np.arange(len(gun)).reshape(-1,3);gt=BVHTree.FromPolygons(gun,gf.tolist(),all_triangles=True)
record=json.loads((a.input/'provenance.json').read_text('utf8'));rows=[]
for row in record['cases']:
    skin=np.load(a.input/f"open_{row['index']:02d}.npz")['hand'];hf=np.arange(len(skin)).reshape(-1,3)
    # This is a measured search, not an accepted animation offset.
    for amplitude in (0,.25,.5,.75,1.,1.25,1.5):
        delta=data['down_per_metre']*amplitude*row['opening']
        hand=[Vector(v)for v in skin+delta];ht=BVHTree.FromPolygons(hand,hf.tolist(),all_triangles=True)
        hits=[(int(h),int(g))for h,g in ht.overlap(gt)if crossing([hand[i]for i in hf[h]],[gun[i]for i in gf[g]])]
        rows.append(dict(**row,full_open_retreat_metres=amplitude,triangle_crossings=len(hits),examples=hits[:4]))
    print(row['index'],[r['triangle_crossings']for r in rows[-7:]],flush=True)
out.write_text(json.dumps(dict(samples=rows,native_tested=False,visual_accepted=False,
    scope='Full hand vs unchanged rifle, closed-to-support pose, measured fixed gun frame; excludes body/ground and wrist rotation'),indent=2),'utf8')
