"""Candidate-only exact RGB polygon clipping of Root's one authorized floor part."""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clip(poly,axis,edge,above):
 out=[]
 if not poly:return out
 prev=poly[-1];old=prev[axis]>=edge if above else prev[axis]<=edge
 for cur in poly:
  now=cur[axis]>=edge if above else cur[axis]<=edge
  if now!=old:out.append(prev+(cur-prev)*(edge-prev[axis])/(cur[axis]-prev[axis]))
  if now:out.append(cur)
  prev=cur;old=now
 return out
def subtract(poly,lo,hi):
 outer=[];inner=poly
 for axis in range(3):
  q=clip(inner,axis,lo[axis],False)
  if len(q)>=3:outer.append(q)
  inner=clip(inner,axis,lo[axis],True)
  q=clip(inner,axis,hi[axis],True)
  if len(q)>=3:outer.append(q)
  inner=clip(inner,axis,hi[axis],False)
  if not inner:break
 return outer
def area(tri):return .5*np.linalg.norm(np.cross(tri[1,:3]-tri[0,:3],tri[2,:3]-tri[0,:3]))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True);ap.add_argument('--mask',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();m=json.loads(a.original.read_text('utf8'));mask=json.loads(a.mask.read_text('utf8'));assert mask['root_authorized'] and mask['target_part_only']=='legacy_contact_source';cells=np.array(mask['positions'],float);lo,hi=cells,cells+1;origin=np.array(m['original_frame']['origin']);assert m['original_frame']['yaw_degrees']==180;basis=np.array([-1.,1.,-1.]);old=np.array(m['parts']['legacy_contact_source']).reshape(-1,3,6);total=0.;out=[];removed=[];head_hits=[]
 # True bearing strips are independently declared by the unchanged source.
 for i,tri in enumerate(np.array(m['finite_head_vertices_world']).reshape(-1,3,3)):
  low,high=tri.min(0),tri.max(0);candidates=np.flatnonzero(np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1))
  for index in candidates:
   poly=list(np.column_stack([tri,np.zeros((3,3))]));
   for axis in range(3):poly=clip(clip(poly,axis,lo[index,axis],True),axis,hi[index,axis],False)
   if len(poly)>=3 and sum(area(np.array([poly[0],poly[j],poly[j+1]])) for j in range(1,len(poly)-1))>1e-10:head_hits.append(dict(head_triangle=i,cell=cells[index].astype(int).tolist()))
 assert not head_hits,('Root mask intersects a real declared bearing strip',head_hits[:3])
 for i,source in enumerate(old):
  tri=source.copy();tri[:,:3]=tri[:,:3]*basis+origin;before=area(tri);total+=before;low,high=tri[:,:3].min(0),tri[:,:3].max(0);indices=np.flatnonzero(np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1));polys=[list(tri)]
  for index in indices:
   fresh=[]
   for poly in polys:fresh.extend(subtract(poly,lo[index],hi[index]))
   polys=fresh
   if not polys:break
  kept=0
  for poly in polys:
   for j in range(1,len(poly)-1):
    t=np.array([poly[0],poly[j],poly[j+1]]);value=area(t)
    if value<=1e-12:continue
    kept+=value;t[:,:3]=(t[:,:3]-origin)*basis;out.append(t)
  if before-kept>1e-9:removed.append(dict(original_triangle_index=i,original_world_vertices=tri[:,:3].tolist(),original_area_m2=before,retained_area_m2=kept,removed_area_m2=before-kept))
  if i%2000==0:print('actual floor triangle',i,'of',len(old),flush=True)
 result=np.array(out).reshape(-1,6);remaining=sum(area(q) for q in np.array(out));doc=dict(schema='projectseele.r52.actual-original-contact-floor-ported-candidate.v1',status='CANDIDATE_NOT_INSTALLED',target_part_only='legacy_contact_source',original_running_source_sha256=sha(a.original),root_mask_sha256=sha(a.mask),original_frame=m['original_frame'],triangles_rgb=result.ravel().tolist(),original_bearing_vertices_sha256=hashlib.sha256(json.dumps(m['finite_head_vertices_world'],separators=(',',':')).encode()).hexdigest(),unchanged_other_part_sha256={k:hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest() for k,v in m['parts'].items() if k!='legacy_contact_source'},world_written=False,production_asset_written=False);a.output.write_text(json.dumps(doc,separators=(',',':')),'utf8');receipt=dict(output=str(a.output.resolve()),sha256=sha(a.output),original_running_source_sha256=sha(a.original),root_mask_sha256=sha(a.mask),mask_cells=len(cells),original_triangles=len(old),retained_triangles=len(out),original_area_m2=total,retained_area_m2=remaining,removed_area_m2=total-remaining,original_bearing_mask_intersections=head_hits,changed_original_triangle_count=len(removed),changed_triangles=removed,producer_sha256=sha(Path(__file__)),world_written=False,production_asset_written=False);a.output.with_suffix('.CLIP_RECEIPT.json').write_text(json.dumps(receipt,indent=2),'utf8');print('floor',total,remaining,'removed',total-remaining,'heads0',flush=True)
if __name__=='__main__':main()
