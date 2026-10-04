"""Strict triangle crossings between actual submitted hands and cannon."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);rows=[json.loads(l)for l in a.witness.open(encoding='utf8')]
geometry={r['resource_part']:r for r in rows if r['kind']=='actual_static_part_geometry'}
def surface(row):
 pts=np.asarray(geometry[row['resource_part']]['original_part_xyz']).reshape(-1,3)
 for change in np.asarray(row['submitted_position_changes_index_xyz']).reshape(-1,4):pts[int(change[0])]=change[1:]
 pts=(pts+row['part_pivot_authored'])*[-1,1,1]/16
 m=np.asarray(row['mesh_to_world_column_major']).reshape(4,4).T;pts=pts@m[:3,:3].T+m[:3,3]
 idx=np.asarray(row['actual_world_sample_vertex_indices'],int)
 assert np.abs(pts[idx]-np.asarray(row['actual_world_sample_xyz']).reshape(-1,3)).max()<.01
 return pts
def crosses(A,B):
 for tri,other in ((A,B),(B,A)):
  for i in range(3):
   start=tri[i];direction=tri[(i+1)%3]-start;squared=direction.length_squared
   if squared<1e-20:continue
   hit=intersect_ray_tri(*other,direction,start,True)
   if hit is not None and 1e-5<(hit-start).dot(direction)/squared<1-1e-5:return True
 return False
result=[]
for palette in (r for r in rows if r['kind']=='final_named_palette'):
 samples=[r for r in rows if r['kind']=='actual_cpu_submitted_part'and r['tick']==palette['tick']]
 weapon=next((r for r in samples if r['bone']=='cannon'),None)
 if weapon is None:continue
 origin=np.asarray(weapon['mesh_to_world_column_major'])[12:15]
 w=surface(weapon)-origin;wv=[Vector(x)for x in w];wf=np.arange(len(w)).reshape(-1,3);wt=BVHTree.FromPolygons(wv,wf.tolist(),all_triangles=True)
 for side in ('l','r'):
  row=next((r for r in samples if r['bone']=='hand_'+side and 'anatomical_hands'in r['resource']),None)
  if row is None:continue
  h=surface(row)-origin;hv=[Vector(x)for x in h];hf=np.arange(len(h)).reshape(-1,3);ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True)
  hits=[]
  for x,y in ht.overlap(wt):
   if crosses([hv[i]for i in hf[x]],[wv[i]for i in wf[y]]):hits.append([int(x),int(y)])
  result.append(dict(tick=palette['tick'],side=side,stance=palette['stance'],triangle_crossings=len(hits),first_pairs=hits[:20],hand_faces=sorted({h[0]for h in hits})))
a.out.write_text(json.dumps(dict(actual_submitted_surfaces=True,results=result,visual_accepted=False),indent=2),'utf8');print(json.dumps(result))
