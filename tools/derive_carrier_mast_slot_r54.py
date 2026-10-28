"""Finite original deck/toe rear-slot refit; keep all source vertices ahead of Z6.4."""
import sys,json,argparse,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT/'.Codex/geometry-deps'))
import shapely
from shapely.geometry import LineString,box
from shapely.ops import polygonize,polygonize_full,unary_union
X,Z=-15,6.4
SOURCE=ROOT/'build/resources/main/assets/projectseele/mesh/carrier_mk2_r53.json'
OUT=ROOT/'src/main/resources/assets/projectseele/mesh/carrier_mast_slot_r54.json'

def clip(poly,axis,limit,keep_low):
 out=[]
 if not poly:return out
 before=poly[-1];old=before[axis]-limit
 for now in poly:
  new=now[axis]-limit;a=old<=0 if keep_low else old>=0;b=new<=0 if keep_low else new>=0
  if a!=b:
   t=old/(old-new);v=[before[k]+t*(now[k]-before[k]) for k in range(8)];v[axis]=limit;out.append(v)
  if b:out.append(now)
  before=now;old=new
 return out

def fan(poly):
 return [v for i in range(1,len(poly)-1) for v in [poly[0],poly[i],poly[i+1]]]

def plane_segments(tris,axis,limit):
 axes=[i for i in range(3) if i!=axis];segments=[]
 for tri in tris:
  points=[]
  for a,b in zip(tri,tri[1:]+tri[:1]):
   da,db=a[axis]-limit,b[axis]-limit
   if da*db<0:
    t=da/(da-db);points.append(tuple(round(a[k]+t*(b[k]-a[k]),5) for k in axes))
   elif da==0:points.append(tuple(round(a[k],5) for k in axes))
  points=list(dict.fromkeys(points))
  if len(points)==2 and points[0]!=points[1]:segments.append(LineString(points))
 return axes,segments

def inside(point,axis,tris):
 # Exact planar projection barycentrics, counted by distinct source crossings.
 axes=[k for k in range(3) if k!=axis];hits=[]
 for a,b,c in tris:
  u,v=axes;det=(b[v]-c[v])*(a[u]-c[u])+(c[u]-b[u])*(a[v]-c[v])
  if abs(det)<1e-10:continue
  p=((b[v]-c[v])*(point[u]-c[u])+(c[u]-b[u])*(point[v]-c[v]))/det
  q=((c[v]-a[v])*(point[u]-c[u])+(a[u]-c[u])*(point[v]-c[v]))/det
  r=1-p-q
  if min(p,q,r)<-1e-8:continue
  hit=p*a[axis]+q*b[axis]+r*c[axis]
  if hit>point[axis]+1e-6:hits.append(round(hit,5))
 return len(set(hits))%2==1

def derive(encoded,open_toe_shell=False):
 verts=[encoded[i:i+8] for i in range(0,len(encoded),8)];tris=[verts[i:i+3] for i in range(0,len(verts),3)];result=[]
 for tri in tris:
  result+=fan(clip(tri,2,Z,True))
  result+=fan(clip(clip(tri,2,Z,False),0,X,True))
 caps=0;areas=[]
 for axis,limit in [(2,Z),(0,X)]:
  axes,segments=plane_segments(tris,axis,limit)
  # The supplied toe shells have an open, planar underside. The cut receives
  # its real end wall, closed along that same measured underside edge.
  _,_,dangling,_=polygonize_full(unary_union(segments))
  for line in shapely.get_parts(shapely.line_merge(dangling)):
   coords=list(line.coords)
   if len(coords)>2 and abs(coords[0][1 if axis==2 else 0]-coords[-1][1 if axis==2 else 0])<1e-5:
    segments.append(LineString([coords[0],coords[-1]]))
  regions=list(polygonize(unary_union(segments)));accepted=[]
  for poly in regions:
   q=poly.representative_point();point=[0,0,0];point[axis]=limit;point[axes[0]]=q.x;point[axes[1]]=q.y
   if open_toe_shell or inside(point,axis,tris):accepted.append(poly)
  section=unary_union(accepted)
  section=section.intersection(box(X,-1000,1000,1000) if axis==2 else box(-1000,Z,1000,1000))
  areas.append(section.area)
  for tri in shapely.get_parts(shapely.constrained_delaunay_triangles(section)):
   pts=list(tri.exterior.coords)[:3];v=[]
   for u,w in pts:
    p=[0.,0.,0.,0.,0.,0.,0.,0.];p[axis]=limit;p[axes[0]]=u;p[axes[1]]=w;p[3]=u*.05;p[4]=w*.05;p[5+axis]=1;v.append(p)
   a,b,c=v;normal=[(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])]
   if normal[axis]<0:v=[a,c,b]
   result+=v;caps+=1
 assert caps>0,'Original finite cut must receive an actual closure surface'
 assert all(v[2]<=Z+1e-6 or v[0]<=X+1e-6 for v in result)
 # Original triangle surfaces wholly in the foot-bearing half are byte-for-
 # byte retained, including their UVs and authored smooth normals.
 original_front=[t for t in tris if all(v[2]<Z for v in t)]
 kept={tuple(q for v in result[i:i+3] for q in v) for i in range(0,len(result),3)}
 assert all(tuple(q for v in t for q in v) in kept for t in original_front)
 return [q for v in result for q in v],dict(original_triangles=len(tris),derived_triangles=len(result)//3,closure_triangles=caps,closure_area=areas,untouched_front_triangles=len(original_front))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--jar',type=Path);args=parser.parse_args()
 if args.jar:
  with zipfile.ZipFile(args.jar) as archive:source=json.loads(archive.read('assets/projectseele/mesh/carrier_mk2_r53.json'))
 else:source=json.loads(SOURCE.read_text('utf8'))
 parts={};report={}
 for name in ['deck','toe_l','toe_r']:parts[name],report[name]=derive(source['parts'][name],name.startswith('toe_'))
 # The retired rear right foot sat inside the mast channel. Both replacement
 # rear bearing shoes now land on the fixed front rail, directly below the
 # retained sole platform. These are real closed steel boxes, not proof pads.
 shoes=[]
 for low,high in [(8.6,9.2),(-10.1,-9.5)]:
  bounds=[low,-4.0078125,4.5,high,-.11132773,5.5];shoes.append(bounds)
  verts=[[bounds[3] if i&1 else bounds[0],bounds[4] if i&2 else bounds[1],bounds[5] if i&4 else bounds[2]] for i in range(8)]
  for corners,normal in [([0,4,6,2],[-1,0,0]),([1,3,7,5],[1,0,0]),([0,1,5,4],[0,-1,0]),([2,6,7,3],[0,1,0]),([0,2,3,1],[0,0,-1]),([4,5,7,6],[0,0,1])]:
   for idx in [0,1,2,0,2,3]:parts['deck']+=verts[corners[idx]]+[0.,0.]+normal
 report['deck']['derived_triangles']+=24;report['deck']['new_closed_support_shoes']=shoes
 doc=dict(schema='projectseele.carrier-mast-slot.r54.v1',revision='rear-slot-xneg15-z6p4-closed-v2',source=source['schema'],cut=dict(min_x=X,min_z=Z,vertical='through',six_sole_pad_max_z=5.559728145599365),parts=parts,report=report)
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(doc,separators=(',',':')),'utf8');print(json.dumps(report))
if __name__=='__main__':main()
