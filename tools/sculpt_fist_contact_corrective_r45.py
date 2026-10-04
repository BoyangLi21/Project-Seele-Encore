"""Private pose-space fingertip-pad corrective on the actual continuous skin.

The bone pose and topology stay fixed. A directional palm contact surface
provides a bounded pad compression target, then welded-neighbour smoothing
removes hard deformation boundaries. This is an offline sculpt candidate;
no runtime or resource is installed, and clearance is audited separately.
"""
from pathlib import Path
import argparse, json, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--posed',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--side',choices=('l','r'),default='r')
p.add_argument('--crease-only',action='store_true',help='Only confirmed finite triangle crossings; retain existing pad compression')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
a.out.mkdir(parents=True,exist_ok=False)
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'))
m=json.loads((a.candidate/f"eva_unit0{c['rig']}_anatomical_hands_r45.mesh.json").read_text('utf8'))
d=np.load(a.posed);posed=d['vertices'];faces=d['faces'];rest=d['rest'];labels=d['labels']
skin=m['jointSkins']['hand_'+a.side]['influences'];normal=np.asarray(c['hands'][a.side]['palmar_normal_bind'])
palm=BVHTree.FromPolygons([Vector(x)for x in posed],faces[labels==-1].tolist(),all_triangles=True)
mass=sum(np.asarray(skin[j['name']])for digit,info in c['hands'][a.side]['digits'].items()
         if digit in ('index','middle','ring','little')for j in info['joints'])
_,inverse=np.unique(np.round(rest,7),axis=0,return_inverse=True)
count=int(inverse.max())+1;minimum=np.zeros(count);neighbors=[set()for _ in range(count)]
for tri in inverse[faces]:
 for x,y in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
  neighbors[x].add(y);neighbors[y].add(x)
eligible=np.zeros(count,dtype=bool)
for i in np.flatnonzero(mass>.5):
 key=inverse[i];eligible[key]=True
 if a.crease_only:continue
 at=Vector(posed[i]);hit,_,_,_=palm.ray_cast(at+Vector(normal),Vector(-normal),2)
 if hit is None:continue
 depth=float((np.asarray(hit)-posed[i])@normal)
 if 0<depth<.06:minimum[key]=max(minimum[key],depth+.002)
# A curved palm can cross the middle of a finger triangle even when its
# corners are outside. Include edge/face samples in the sculpt constraints.
for tri in ([] if a.crease_only else faces[(labels>=1)&(labels<=4)]):
 for bary in ((1/3,1/3,1/3),(.5,.5,0),(0,.5,.5),(.5,0,.5)):
  at=posed[tri].T@bary
  hit,_,_,_=palm.ray_cast(Vector(at+normal),Vector(-normal),2)
  if hit is None:continue
  depth=float((np.asarray(hit)-at)@normal)
  if 0<depth<.06:
   for key in inverse[tri]:
    if eligible[key]:minimum[key]=max(minimum[key],depth+.002)
assert minimum.max()<.06,'Contact requires rig reconstruction, not a large mesh correction'
displacement=minimum.copy()
for _ in range(8):
 updated=displacement.copy()
 for key in np.flatnonzero(eligible):
  if neighbors[key]:updated[key]=max(minimum[key],.5*displacement[key]+.5*np.mean(displacement[list(neighbors[key])]))
 displacement=updated
# Contact neighbours also move because this is one welded skin, not separate
# finger cylinders. Re-evaluate that deformed palm for the shallow crease
# corrections; do not pretend that the original contact surface stayed fixed.
for _ in range(0 if a.crease_only else 3):
 current=posed+displacement[inverse,None]*normal
 current_palm=BVHTree.FromPolygons([Vector(x)for x in current],faces[labels==-1].tolist(),all_triangles=True)
 updated=displacement.copy()
 for tri in faces[(labels>=1)&(labels<=4)]:
  for bary in ((1,0,0),(0,1,0),(0,0,1),(1/3,1/3,1/3),(.5,.5,0),(0,.5,.5),(.5,0,.5)):
   at=current[tri].T@bary
   hit,_,_,_=current_palm.ray_cast(Vector(at+normal),Vector(-normal),2)
   if hit is None:continue
   depth=float((np.asarray(hit)-at)@normal)
   if 0<depth<.01:
    for key in inverse[tri]:
     if eligible[key]:updated[key]=max(updated[key],displacement[key]+depth+.002)
 displacement=updated
# Resolve the remaining narrow crease intersections against actual triangle
# planes. Vertex/ray samples alone can miss a crossing close to an edge.
def intersects(A,B):
 for tri,other in ((A,B),(B,A)):
  for i in range(3):
   start=tri[i];direction=tri[(i+1)%3]-start;length=direction.length_squared
   if length<1e-20:continue
   hit=intersect_ray_tri(*other,direction,start,True)
   if hit is not None and 1e-5<(hit-start).dot(direction)/length<1-1e-5:return True
 return False
finger_faces=np.flatnonzero((labels>=1)&(labels<=4));palm_faces=np.flatnonzero(labels==-1)
crease=np.zeros((count,3))
for _ in range(6):
 current=posed+displacement[inverse,None]*normal+crease[inverse];vectors=[Vector(x)for x in current]
 ft=BVHTree.FromPolygons(vectors,faces[finger_faces].tolist(),all_triangles=True)
 pt=BVHTree.FromPolygons(vectors,faces[palm_faces].tolist(),all_triangles=True)
 updated=displacement.copy();updated_crease=crease.copy();crossings=0
 for x,y in ft.overlap(pt):
  ia,ib=faces[finger_faces[x]],faces[palm_faces[y]]
  if np.linalg.norm(rest[ia][:,None]-rest[ib][None,:],axis=2).min()<1e-6:continue
  if not intersects([vectors[i]for i in ia],[vectors[i]for i in ib]):continue
  A,B=current[ia],current[ib];n=np.cross(B[1]-B[0],B[2]-B[0]);n/=max(np.linalg.norm(n),1e-15)
  if n@normal<0:n=-n
  projection=float(n@normal)
  depth=max(0,.001-float(((A-B[0])@n).min()))
  required=depth/max(projection,1e-8)
  if required<=.015:
   for key in inverse[ia]:
    if eligible[key]:updated[key]=max(updated[key],displacement[key]+required)
  else:
   # At a nearly vertical crease, pushing along the global palm normal
   # magnifies a submillimetre crossing. Use its local contact normal.
   for key in inverse[ia]:
    candidate=crease[key]+depth*n
    if eligible[key] and np.linalg.norm(candidate)<.015 and np.linalg.norm(candidate)>np.linalg.norm(updated_crease[key]):updated_crease[key]=candidate
  crossings+=1
 displacement=updated;crease=updated_crease
 if crossings==0:break
assert displacement.max()<.065,'Contact correction exceeded the bounded pad region'
delta=displacement[inverse,None]*normal+crease[inverse]
assert np.linalg.norm(delta,axis=1).max()<.065
corrected=posed+delta
np.savez_compressed(a.out/'fist_pad_corrected.npz',vertices=corrected,faces=faces,labels=labels,rest=rest)
(a.out/'cases.json').write_text(json.dumps([dict(case='fist_pad_corrected',side=a.side,definition='Fixed skeleton plus contact corrective')]),'utf8')
np.savez_compressed(a.out/'corrective_model_space.npz',delta=delta,rest=rest)
(a.out/'sculpt_receipt.json').write_text(json.dumps(dict(side=a.side,
 changed_vertices=int(np.count_nonzero(np.linalg.norm(delta,axis=1))),maximum_delta_model=float(np.linalg.norm(delta,axis=1).max()),
 maximum_delta_world_blocks=float(np.linalg.norm(delta,axis=1).max()*5),topology_unchanged=True,bones_unchanged=True,
 actual_runtime_supported=False,visual_accepted=False,collision_accepted=False),indent=2),'utf8')
print('Private contact sculpt: maximum model delta',displacement.max())
