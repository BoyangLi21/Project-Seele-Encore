"""BVH broad phase plus finite segment/triangle tests on actual deformed skin."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--all-digits',action='store_true');p.add_argument('--palm',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);rows=[]
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
for case in json.loads((a.input/'cases.json').read_text(encoding='utf8')):
 d=np.load(a.input/(case['case']+'.npz'));vs=[Vector(x)for x in d['vertices']];faces=d['faces'];labels=d['labels'];selected=[np.flatnonzero(labels==i)for i in range(5)];trees=[BVHTree.FromPolygons(vs,faces[idx].tolist(),all_triangles=True,epsilon=1e-8)for idx in selected];counts={};examples=[]
 pairs=[(first,other)for first in (range(4)if a.all_digits else [0])for other in range(first+1,5)]
 if a.palm:
  selected.append(np.flatnonzero(labels==-1));trees.append(BVHTree.FromPolygons(vs,faces[selected[-1]].tolist(),all_triangles=True,epsilon=1e-8))
  pairs.extend((first,5)for first in range(5))
 for first,other in pairs:
  count=0
  for x,y in trees[first].overlap(trees[other]):
   ia,ib=int(selected[first][x]),int(selected[other][y]);fa,fb=faces[ia],faces[ib]
   # Shared source points at the natural web are topological neighbours.
   if np.min(np.linalg.norm(d['rest'][fa][:,None]-d['rest'][fb][None,:],axis=2))<1e-6:continue
   if crosses([vs[i]for i in fa],[vs[i]for i in fb]):
    count+=1
    if len(examples)<8:examples.append([ia,ib])
  digits=['thumb','index','middle','ring','little','palm'];counts[(digits[first]+'_'+digits[other])if a.all_digits or a.palm else digits[other]]=count
 row=dict(case,intersections=counts,total=sum(counts.values()),examples=examples);rows.append(row);print(case['case'],row['total'],flush=True)
(a.input/('digit_and_palm_intersections.json'if a.palm else 'all_digit_intersections.json'if a.all_digits else 'surface_intersections.json')).write_text(json.dumps(rows,indent=2),encoding='utf8')
