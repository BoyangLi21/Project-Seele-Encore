"""Replace only the earlier engineered carrier rods with four hollow slides.

Input is the accepted local carrier JAR. Preserve its complete imported source
and keep the predecessor as a runtime surface-continuity witness. No report of
resource fingerprints is emitted; only required selection bindings are written.
"""
import argparse
import json,zipfile,hashlib
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--accepted-jar',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.accepted_jar) as z:
 predecessor=z.read('assets/projectseele/mesh/carrier_mk2_r53.json')
 source=json.loads(predecessor);selection=json.loads(z.read('assets/projectseele/eva/carrier_assembly_r53_sources.json'))
assert 'engineering_upright_drive_r53' not in source, 'Use the accepted pre-refit carrier source'

parts=source['parts'];materials=source['materials'];texture=next(iter(materials.values()));old=list(materials)
for name in old:parts.pop(name);materials.pop(name)
original={n:np.asarray(v,dtype=np.float32).reshape(-1,8)[:,:3].astype(float).reshape(-1,3,3) for n,v in parts.items()}
faces=np.array([[0,2,3],[0,3,1],[4,5,7],[4,7,6],[0,1,5],[0,5,4],[2,6,7],[2,7,3],[0,4,6],[0,6,2],[1,3,7],[1,7,5]])
def box(lo,hi):
 assert np.all(np.array(hi)>lo),(lo,hi)
 v=np.array([[hi[k] if i>>k&1 else lo[k] for k in range(3)] for i in range(8)]);return v[faces]
def beam(a,b,width):
 a=np.asarray(a);b=np.asarray(b);axis=b-a;axis/=np.linalg.norm(axis);ref=np.array([0.,1,0]) if abs(axis[1])<.9 else np.array([1.,0,0]);u=np.cross(axis,ref);u/=np.linalg.norm(u);v=np.cross(axis,u)
 q=np.array([p+sx*u*width/2+sy*v*width/2 for p in (a,b) for sx,sy in [(-1,-1),(1,-1),(-1,1),(1,1)]]);return q[faces]
def prism(t,d):
 q=np.concatenate([t,t+d]);return q[np.array([[0,2,1],[3,4,5],[0,1,4],[0,4,3],[1,2,5],[1,5,4],[2,0,3],[2,3,5]])]
def encode(name,rows):
 a=np.concatenate(rows).astype(np.float32);v=[]
 for t in a:
  normal=np.cross(t[1]-t[0],t[2]-t[0]);normal/=max(np.linalg.norm(normal),1e-20)
  for p in t:v.extend([*map(float,p),0.,0.,*map(float,normal)])
 parts[name]=v;materials[name]=texture
contracts=[]
for group in ('lower','upper'):
 for side,suffix in [(-1,'l'),(1,'r')]:
  key=group+'_'+suffix;jaw=original['clamp_'+key];centres=jaw.mean(1);normals=np.cross(jaw[:,1]-jaw[:,0],jaw[:,2]-jaw[:,0]);length=np.linalg.norm(normals,axis=1)
  candidates=np.flatnonzero((np.abs(normals[:,2])>.7*length)&(centres[:,2]>jaw[:,:,2].max()-.8)&(length>.005));idx=max(candidates,key=lambda i:centres[i,2]);end=jaw[idx];centre=end.mean(0);patch=end.copy();y=float(centre[1]);pin=float(centre[0]);tip=float(patch[:,:,] .max(0)[2])
  rail=side*max(12.2 if group=='lower' else 14.0,abs(pin)+3.65);tail=tip+.6;zmin=tail-.5;zmax=tail+2.6
  # Fixed bracket takes a finite patch from the original outer steel face.
  choices=[]
  for candidate in ('body','retract_body','retract_spine'):
   mesh=original[candidate];cent=mesh.mean(1);n=np.cross(mesh[:,1]-mesh[:,0],mesh[:,2]-mesh[:,0]);area=np.linalg.norm(n,axis=1);can=np.flatnonzero((abs(cent[:,1]-y)<2.5)&(side*cent[:,0]>4)&(abs(n[:,0])>.98*area)&(area>.005))
   choices.extend((side*cent[i,0]-.03*abs(cent[i,1]-y),candidate,int(i)) for i in can)
  _,anchorPart,ai=max(choices);mesh=original[anchorPart];face=mesh[ai];ac=face.mean(0);ap=face.copy();external=ac+[side*.16,0,0];rear=max(zmax+.3,float(ap.max(0)[2])+.25);outer=np.array([rail,y-.4,rear]);elbow=np.array([external[0],external[1],rear]);
  fixed=[prism(ap,np.array([side*.16,0,0])),beam(external,elbow,.16),beam(elbow,outer,.16),beam(outer,[rail,y-.4,zmax-.2],.16)]
  # Three-sided guide with an inboard mouth for the moving transverse tube.
  x=abs(rail);fixed.extend([box([x+.15,y-.32,zmin],[x+.25,y+.32,zmax]),box([x-.25,y+.22,zmin],[x+.15,y+.32,zmax]),box([x-.25,y-.32,zmin],[x+.15,y-.22,zmax])])
  if side<0:
   for i in range(4,len(fixed)):fixed[i][:,:,0]*=-1
  encode('jaw_fixed_'+key,fixed)
  # Carriage is one welded source group; the transverse tube is genuinely hollow.
  innerEnd=abs(pin)+1.9;start=innerEnd-.25;end=abs(rail)+.14
  car=[box([abs(rail)-.14,y-.21,tail-.28],[abs(rail)+.14,y+.21,tail+.28])]
  for lo,hi in [([start,y+.14,tail-.2],[end,y+.2,tail+.2]),([start,y-.2,tail-.2],[end,y-.14,tail+.2]),([start,y-.14,tail+.14],[end,y+.14,tail+.2]),([start,y-.14,tail-.2],[end,y+.14,tail-.14])]:car.append(box(lo,hi))
  if side<0:
   for a in car:a[:,:,0]*=-1
  encode('jaw_carriage_'+key,car)
  rod=[prism(patch,np.array([0,0,.14])),box([abs(pin)-.10,y-.10,tip+.04],[abs(pin)+.10,y+.10,tail+.12]),box([abs(pin)-.10,y-.12,tail-.12],[innerEnd,y+.12,tail+.12])]
  if side<0:
   for a in rod[1:]:a[:,:,0]*=-1
  encode('jaw_rod_'+key,rod)
  contracts.append(dict(jaw='clamp_'+key,body_anchor_part=anchorPart,body_anchor_triangle=int(ai),body_anchor_patch=ap.tolist(),jaw_anchor_triangle=int(idx),jaw_anchor_patch=patch.tolist(),guide_x=rail,guide_y=y,axial_travel_m=2,lateral_travel_m=1.5,inner_tube_clearance_m=.02,carriage_clearance_m=.01))
source['engineering_upright_drive_r53']=dict(mode='fixed_full_imported_body_with_four_independent_hollow_jaw_slides',replaced_engineering_members=old,imported_faces_retained=8727,source_body_deck_relative_transform='identity_at_every_bay_clock',jaw_open_order=['lateral_1.5m','axial_2m'],interfaces=contracts)
source['retained_surface_predecessor']='mesh/carrier_mk2_pre_upright_r53.json'
previouspath=out/source['retained_surface_predecessor'];previouspath.parent.mkdir(parents=True,exist_ok=True);previouspath.write_bytes(predecessor)
selection['resources'][source['retained_surface_predecessor']]=hashlib.sha256(predecessor).hexdigest()
meshpath=out/'mesh/carrier_mk2_r53.json';meshpath.parent.mkdir(parents=True,exist_ok=True);meshpath.write_text(json.dumps(source,separators=(',',':')),'utf8')
selection['resources']['mesh/carrier_mk2_r53.json']=hashlib.sha256(meshpath.read_bytes()).hexdigest();sp=out/'eva/carrier_assembly_r53_sources.json';sp.parent.mkdir(parents=True,exist_ok=True);sp.write_text(json.dumps(selection,separators=(',',':')),'utf8')
assert sum(len(parts[n])//24 for n in parts if n not in materials)==8727
print(json.dumps(dict(original_triangles=8727,new_engineered_parts=len(materials),output=str(out))))

