"""Current actual assembly bands plus an analytic continuous tangent-cone enclosure of db7 heads.

Read-only engineering geometry. No World/route writes and no gate-clearance claim.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import gzip,struct,json,hashlib,math,argparse
import numpy as np
from scipy.spatial import ConvexHull

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/map_complete_20261013/route_audit/launch_hulls_current'
DESIGN=Path('D:/eva/artifacts/map_complete_20261013/phased_routes/PHASED_MONOTONE_DESIGN.json')
ANGLE_ERROR_BUDGET=.02
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read_mesh(p):
 data=memoryview(gzip.decompress(p.read_bytes()));i=0;n=struct.unpack_from('>i',data,i)[0];i+=4;parts={}
 for _ in range(n):
  size=struct.unpack_from('>H',data,i)[0];i+=2;name=bytes(data[i:i+size]).decode();i+=size
  size=struct.unpack_from('>H',data,i)[0];i+=2;family=bytes(data[i:i+size]).decode();i+=size
  size=struct.unpack_from('>i',data,i)[0];i+=4;a=np.frombuffer(data[i:i+size*8],dtype='>f8').astype(np.float64).reshape(-1,3,3);i+=size*8
  assert name not in parts;parts[name]=(family,a)
 assert i==len(data);return parts
def hull(p):
 p=np.unique(np.asarray(p),axis=0)
 if len(p)<3:return p
 try:return p[ConvexHull(p).vertices]
 except Exception:return p
def clipped(tri,extra=0.):
 lo=tri[:,:,1].min(1);hi=tri[:,:,1].max(1);rows={}
 for y in range(math.floor(float(lo.min()-extra)),math.floor(float(hi.max()+extra))+1):
  lower=y-extra;upper=y+1+extra;t=tri[(lo<=upper)&(hi>=lower)]
  if not len(t):continue
  pts=[t[(t[:,:,1]>=lower)&(t[:,:,1]<=upper)]]
  for plane in (lower,upper):
   for i,j in ((0,1),(1,2),(2,0)):
    a,b=t[:,i],t[:,j];mask=((a[:,1]<plane)&(b[:,1]>plane))|((a[:,1]>plane)&(b[:,1]<plane));a,b=a[mask],b[mask]
    if len(a):pts.append(a+(b-a)*((plane-a[:,1])/(b[:,1]-a[:,1]))[:,None])
  p=np.concatenate(pts)
  if len(p):
   xz=hull(p[:,[0,2]])
   if extra:xz=hull(np.concatenate([xz+q for q in ((-extra,-extra),(-extra,extra),(extra,-extra),(extra,extra))]))
   rows[y]=xz
 return rows
def merge(target,source):
 for y,p in source.items():target[y]=hull(np.concatenate([target[y],p])) if y in target else p
def bands(rows):return [dict(height_band_m=[y,y+1],actual_clipped_XZ_convex_hull_m=p.tolist()) for y,p in sorted(rows.items()) if len(p)>=3]
def split(p):
 levels=[p]
 while len(levels[-1])>1:levels.append((levels[-1][:-1]+levels[-1][1:])/2)
 return np.array([r[0] for r in levels]),np.array([r[-1] for r in levels[::-1]])
def midpoint(p):
 while len(p)>1:p=(p[:-1]+p[1:])/2
 return p[0]
def cones(controls,coefficient,roundoff,leg,segment):
 derivative=(len(controls)-1)*np.diff(controls,axis=0);todo=[(derivative,0.,1.,0)];out=[]
 while todo:
  p,a,b,depth=todo.pop();norms=np.linalg.norm(p,axis=1);assert np.all(norms>0),'Zero derivative control lacks a tangent-cone certificate'
  unit=p/norms[:,None];ref=midpoint(p);ref/=np.linalg.norm(ref);cosine=float((unit@ref).min());delta=math.sqrt(max(0.,2-2*max(-1.,min(1.,cosine))))
  max_abs_x=abs(float(ref[0]))+delta;smin=math.sqrt(max(0.,1-max_abs_x*max_abs_x));error=math.inf
  if cosine>0 and smin>.1:error=(4*coefficient[0]/smin+coefficient[1])*delta+roundoff
  if error<=ANGLE_ERROR_BUDGET:
   out.append(dict(leg=leg,segment=segment,geometric_bezier_parameter=[a,b],direction=ref.tolist(),unit_direction_distance_bound=delta,minimum_projected_fixed_x_norm=smin,position_error_m=error,positive_cone_cosine=cosine));continue
  assert depth<22,('Direction frame is degenerate or cannot be bounded',leg,segment,a,b)
  left,right=split(p);m=(a+b)/2;todo.extend([(right,m,b,depth+1),(left,a,m,depth+1)])
 return out
def write(path,value):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8');temp.replace(path)
def main():
 global OUT
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);args=ap.parse_args();OUT=args.output.resolve()
 design_bytes=DESIGN.read_bytes();design_sha=hashlib.sha256(design_bytes).hexdigest();design=json.loads(design_bytes);(OUT/'INPUT_DIRECTORY_SNAPSHOT.json').write_bytes(design_bytes)
 export=json.loads((OUT/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json').read_text('utf8'));assert export['root_design_sha256']==design_sha,'Root changed design during current geometry export'
 assert not export.get('construction_hull_invalidated',False),'An invalidated complete assembly cannot be exported'
 for p,h in export['sources_sha256'].items():
  if p.endswith('PHASED_MONOTONE_DESIGN.json') or '.bin.gz' in p:assert sha(Path(p))==h
 head=read_mesh(OUT/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz');template={p['name']:p for p in export['head_templates']};assert len(head)==48
 mount_source=OUT/'CURRENT_PRODUCTION_HEAD_EXPORT.json'
 if mount_source.exists():
  current=json.loads(mount_source.read_text('utf8'));assert current['head_source_sha256']==export['head_source_sha256']
  balls={int(k):np.asarray(v,dtype=float) for k,v in current['world_yaw180_mounts'].items()};assert set(balls)=={-1,1}
 else:balls={side:np.array([-side*15.,-3.42,side*14.78]) for side in (-1,1)}
 root_parts=[];moving={-1:[],1:[]}
 for name,(_,a) in head.items():
  frame=template[name]['frame']
  if frame=='ROOT':root_parts.append(a*np.array([-1,1,-1]))
  else:
   assert frame in ('RUNNER_NEG','RUNNER_POS');moving[-1 if frame=='RUNNER_NEG' else 1].append(a)
 root_mesh=np.concatenate(root_parts);moving={side:np.concatenate(parts) for side,parts in moving.items()}
 allmoving=np.concatenate(list(moving.values())).reshape(-1,3)
 coefficient=(float((np.abs(allmoving[:,0])+np.abs(allmoving[:,1]-.35)).max()),float((np.abs(allmoving[:,1]-.35)+np.abs(allmoving[:,2])).max()))
 radius=float(np.linalg.norm(allmoving,axis=1).max());roundoff=radius*16e-6+1e-6
 base=[];fixed_variants=[]
 for v in range(3):
  parts=read_mesh(OUT/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz');body=np.concatenate([a for _,a in parts.values()]);offset=export['variants'][v]['root_relative_to_actual_foot_midpoint']['translation'];offset=np.array([offset['x'],offset['y'],offset['z']]);assert offset[0]==offset[1]==0
  body=np.concatenate([body,root_mesh+offset]);rows=clipped(body);base.append(rows);fixed_variants.append(dict(variant=v,actual_triangles=len(body),actual_xyz_bounds_m=np.r_[body.reshape(-1,3).min(0),body.reshape(-1,3).max(0)].tolist(),height_slices_1m=bands(rows)))
  print('Current actual fixed variant',v,'triangles',len(body),'bands',len(rows),flush=True)
 fixed=dict(world_written=False,game_started=False,clearance_passed=False,root_design_sha256=design_sha,directory_fingerprint=export['directory_fingerprint'],head_directional_members_included=False,variants=fixed_variants,scope='Fresh full current body/closed plug/original carrier with union of the three actual bank-ready shoe states, plus all actual ROOT-frame outer members. Direction-dependent head members are in the separate continuous source enclosure; do not use this fixed subset as a complete construction or door clearance hull.')
 write(OUT/'ACTUAL_FIXED_ASSEMBLY_HEIGHT_SLICES.json',fixed)
 allcones=[]
 for leg in design['legs']:
  if leg['id'].endswith('/reverse') or 'centre_curve' not in leg:continue
  for i,seg in enumerate(leg['centre_curve']['segments']):allcones.extend(cones(np.array(seg['controls']),coefficient,roundoff,leg['id'],i))
 # Near-identical translated lanes share an orientation only with explicit extra
 # roundoff larger than the rounding used for this numeric cache key.
 unique={}
 for row in allcones:
  key=tuple(round(x,10) for x in row['direction']);known=unique.get(key)
  if known is None:unique[key]=row.copy()
  else:known['position_error_m']=max(known['position_error_m'],row['position_error_m'])
 print('Actual derivative-control cones',len(allcones),'distinct orientation representatives',len(unique),'head triangles',sum(len(a) for a in moving.values()),flush=True)
 write(OUT/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json',dict(root_design_sha256=design_sha,head_source_sha256=export['head_source_sha256'],geometric_parameter_scope='Bezier parameter is used only to cover the complete geometric image. Production intervalFraction/arc mapping is monotone and traverses this same entire image; no uniform-clock or SLERP-between-direction assumption is made.',bound_derivation='Derivative Bezier lies in convex hull of its derivative controls. Positive control cone gives |d-d0|<=delta. x=normalize(u-d(u.d)), u=(-1,0,0), has difference <=4*delta/smin; y=d cross x differs <=delta+4*delta/smin. Each real local vertex x*xlocal+y*(ylocal-.35)+d*zlocal therefore differs by the recorded coefficient*delta plus explicit actual float-frame roundoff. Expanding the height slab and XZ hull by this error encloses every continuous actual posed triangle.',maximum_target_error_m=ANGLE_ERROR_BUDGET,actual_vertex_coefficients=coefficient,actual_maximum_local_radius_m=radius,frame_roundoff_m=roundoff,cones=allcones))
 dynamic={};max_error=0.
 for count,row in enumerate(unique.values(),1):
  d=np.array(row['direction']);u=np.array([-1.,0,0]);x=u-d*np.dot(u,d);x/=np.linalg.norm(x);y=np.cross(d,x);error=row['position_error_m']+1e-8;max_error=max(max_error,error)
  for side,a in moving.items():
   ball=balls[side];posed=a[:,:,0,None]*x+a[:,:,1,None]*y+a[:,:,2,None]*d+ball-.35*y;merge(dynamic,clipped(posed,error))
  if count%500==0:print('Head continuous source cones',count,'/',len(unique),flush=True)
 variants=[]
 write(OUT/'CURRENT_HEAD_CONTINUOUS_HEIGHT_SLICES.json',dict(root_design_sha256=design_sha,head_source_sha256=export['head_source_sha256'],maximum_head_orientation_enclosure_error_m=max_error,height_slices_1m=bands(dynamic),scope='Actual continuous direction-changing heads in world yaw180 root basis, before each variant foot-midpoint offset.'))
 for v in range(3):
  offset=export['variants'][v]['root_relative_to_actual_foot_midpoint']['translation']['z'];combined={k:p.copy() for k,p in base[v].items()};merge(combined,{y:p+np.array([0,offset]) for y,p in dynamic.items()});allpoints=np.concatenate(list(combined.values()));variants.append(dict(variant=v,height_slices_1m=bands(combined),actual_fixed_triangles=fixed_variants[v]['actual_triangles'],conservative_complete_xyz_bounds_m=[float(allpoints[:,0].min()),min(combined),float(allpoints[:,1].min()),float(allpoints[:,0].max()),max(combined)+1,float(allpoints[:,1].max())]))
 result=dict(world_written=False,game_started=False,clearance_passed=False,root_design_sha256=design_sha,directory_fingerprint=export['directory_fingerprint'],head_source_sha256=export['head_source_sha256'],current_full_assembly_source='Actual unchanged seated-plug fixed members plus all48 current production outer templates and production mount coordinates',current_head_continuous_coverage=True,maximum_head_orientation_enclosure_error_m=max_error,variants=variants,source_sha256={str(p):sha(p) for p in [OUT/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json',OUT/'ACTUAL_FIXED_ASSEMBLY_HEIGHT_SLICES.json',OUT/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json',Path(__file__),*([mount_source] if mount_source.exists() else [])]},scope='Engineering construction hull only, fixed world body yaw180 and actual foot-midpoint reference. Fixed assembly bands use exact actual triangle/slab intersections. Direction-dependent head bands add the explicitly certified <=2cm continuous tangent-cone displacement envelope. The union covers all nine ascent routes and three actual ready shoe states. This is not exact gate-frame admission or permission to delete any fixture, support, or door.')
 assert sha(DESIGN)==design_sha, 'Root source changed during continuous head enclosure';write(OUT/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json',result);print('COMPLETE',OUT/'CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json','maxHeadBound',max_error,flush=True)
if __name__=='__main__':main()
