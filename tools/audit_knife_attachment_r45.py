"""Exact hand/weapon triangle crossings in an offline attachment candidate."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--radial-study',action='store_true');p.add_argument('--kind',choices=['knife','sword'],default='knife');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);d=np.load(a.input);hand=d['hand'];knife=d[a.kind];normal=d['normal'];along=d['along'];contract=json.loads((a.input.parent/'hand_rig_contract.json').read_text());q=contract[a.kind+'_attachment_r45']['rotation_xyzw'];from mathutils import Quaternion
across=-np.asarray(Quaternion((q[3],q[0],q[1],q[2])).to_matrix())[:,1]
mesh=json.loads((a.input.parent/f"eva_unit0{contract['rig']}_anatomical_hands_r45.mesh.json").read_text());skin=mesh['jointSkins']['hand_r']['influences'];families=['thumb','index','middle','ring','little'];mass=np.array([sum(np.asarray(skin[j['name']])for j in contract['hands']['r']['digits'][name]['joints']).reshape(-1,3).mean(1)for name in families]);labels=[families[i]if mass[i,k]>.5 else'palm'for k,i in enumerate(mass.argmax(0))]
def crosses(A,B):
 for tri,other in [(A,B),(B,A)]:
  for i in range(3):
   start=tri[i];direction=tri[(i+1)%3]-start;length=direction.length
   if length<1e-10:continue
   hit=intersect_ray_tri(*other,direction,start,True)
   if hit is not None:
    t=(hit-start).dot(direction)/(length*length)
    if 1e-5<t<1-1e-5:return True
 return False
hv=[Vector(p)for p in hand];hf=np.arange(len(hand)).reshape(-1,3);kf=np.arange(len(knife)).reshape(-1,3);ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True);rows=[]
cases=[(l,n,0)for l,n in [(0,0),(-.04,0),(.04,0),(0,-.04),(0,.04),(-.04,-.04),(.04,-.04),(-.04,.04),(.04,.04)]]
if a.radial_study:cases=[(l,n,r)for r in [0,.06,.12]for l in [0,-.04]for n in [0,-.025]]
for along_shift,normal_shift,radial_shift in cases:
 kv=[Vector(p)for p in knife+along*along_shift+normal*normal_shift+across*radial_shift];kt=BVHTree.FromPolygons(kv,kf.tolist(),all_triangles=True);hits=[]
 for hi,ki in ht.overlap(kt):
  if crosses([hv[i]for i in hf[hi]],[kv[i]for i in kf[ki]]):hits.append([hi,ki])
 from collections import Counter
 row=dict(along_shift=along_shift,normal_shift=normal_shift,radial_shift=radial_shift,triangle_crossings=len(hits),by_hand_region=dict(Counter(labels[h]for h,k in hits)),examples=hits[:12]);rows.append(row);print(along_shift,normal_shift,radial_shift,len(hits),row['by_hand_region'],flush=True)
a.out.write_text(json.dumps(rows,indent=2),encoding='utf8')
