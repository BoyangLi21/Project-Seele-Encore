"""Replace redundant original hanger assemblies with the installed four-jaw drive.
The original load spine, feet, deck and rear-guide datums are retained exactly.
"""
import argparse,json,zipfile,hashlib,ast
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--accepted-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
with zipfile.ZipFile(args.accepted_jar) as z:
 source=json.loads(z.read('assets/projectseele/mesh/carrier_mk2_r53.json'));selection=json.loads(z.read('assets/projectseele/eva/carrier_assembly_r53_sources.json'))
parts=source['parts'];materials=source['materials'];texture=next(iter(materials.values()))
raw=np.asarray(parts['retract_body']).reshape(-1,24);tri=raw.reshape(-1,3,8)[:,:,:3];parents=list(range(len(tri)));vertices={}
def root(i):
 while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
 return i
for i,t in enumerate(tri):
 for v in t:
  key=tuple(np.round(v,5))
  if key in vertices:parents[root(i)]=root(vertices[key])
  else:vertices[key]=i
groups={}
for i in range(len(tri)):groups.setdefault(root(i),[]).append(i)
groups={min(v):v for v in groups.values()};keepfirst={0:23,106:44,114:23,214:44,218:28}
assert len(groups)==39 and all(len(groups[i])==n for i,n in keepfirst.items())
keep=sorted(i for first in keepfirst for i in groups[first]);assert len(keep)==162
parts['retract_body']=raw[keep].ravel().tolist()
# Keep the original hollow guide; only its anchor and three joining beams change.
helper=ast.parse(Path('tools/build_r53_upright_carrier_slides.py').read_text())
faces=np.array([[0,2,3],[0,3,1],[4,5,7],[4,7,6],[0,1,5],[0,5,4],[2,6,7],[2,7,3],[0,4,6],[0,6,2],[1,3,7],[1,7,5]])
for f in helper.body:
 if isinstance(f,ast.FunctionDef) and f.name in ('box','beam','prism','encode'):exec(compile(ast.Module(body=[f],type_ignores=[]),'<original hollow slide helpers>','exec'))
c=next(c for c in source['engineering_upright_drive_r53']['interfaces'] if c['jaw']=='clamp_upper_r');mesh=np.asarray(parts['retract_spine']).reshape(-1,3,8)[:,:,:3];y=c['guide_y'];cent=mesh.mean(1);n=np.cross(mesh[:,1]-mesh[:,0],mesh[:,2]-mesh[:,0]);area=np.linalg.norm(n,axis=1)
can=np.flatnonzero((abs(cent[:,1]-y)<2.5)&(cent[:,0]>4)&(abs(n[:,0])>.98*area)&(area>.005));ai=max(can,key=lambda i:cent[i,0]-.03*abs(cent[i,1]-y));ap=mesh[ai];ac=ap.mean(0);rail=c['guide_x'];tip=np.asarray(c['jaw_anchor_patch']).max(0)[2];tail=tip+.6;zmin=tail-.5;zmax=tail+2.6;external=ac+[.16,0,0];rear=max(zmax+.3,float(ap.max(0)[2])+.25);outer=np.array([rail,y-.4,rear]);elbow=np.array([external[0],external[1],rear])
fixed=[prism(ap,np.array([.16,0,0])),beam(external,elbow,.16),beam(elbow,outer,.16),beam(outer,[rail,y-.4,zmax-.2],.16)]
x=rail;fixed.extend([box([x+.15,y-.32,zmin],[x+.25,y+.32,zmax]),box([x-.25,y+.22,zmin],[x+.15,y+.32,zmax]),box([x-.25,y-.32,zmin],[x+.15,y-.22,zmax])]);encode('jaw_fixed_upper_r',fixed)
c.update(body_anchor_part='retract_spine',body_anchor_triangle=int(ai),body_anchor_patch=ap.tolist())
source['duplicate_hanger_refit_r53']=dict(mode='four_jaw_hollow_drive_replaces_redundant_side_hangers',part='retract_body',retained_component_first_triangles=list(keepfirst),retained_triangles=162,retired_components=34,retired_triangles=1894,main_load_spine_deck_feet_rear_unchanged=True)
source['fitting']['source_faces_removed']=1894
source['engineering_upright_drive_r53']['mode']='fixed_load_mast_with_four_independent_hollow_jaw_slides';source['engineering_upright_drive_r53']['imported_faces_retained']=6833
out=args.output;mp=out/'mesh/carrier_mk2_r53.json';mp.parent.mkdir(parents=True,exist_ok=True);mp.write_text(json.dumps(source,separators=(',',':')),'utf8');selection['resources']['mesh/carrier_mk2_r53.json']=hashlib.sha256(mp.read_bytes()).hexdigest();sp=out/'eva/carrier_assembly_r53_sources.json';sp.parent.mkdir(parents=True,exist_ok=True);sp.write_text(json.dumps(selection,separators=(',',':')),'utf8');print(json.dumps(dict(retained_imported_triangles=6833,retired_duplicate_components=34,retired_triangles=1894,right_upper_anchor_part='retract_spine',right_upper_anchor_triangle=int(ai),output=str(out))))
