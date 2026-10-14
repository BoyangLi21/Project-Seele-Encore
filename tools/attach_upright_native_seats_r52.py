"""Attach Root-selected real native faces to exact rail socket triangles.
Writes a reviewable geometry source, never World blocks or a ready claim.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
FACES=np.array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5])
def main():
 p=argparse.ArgumentParser();p.add_argument('--steel',type=Path,required=True);p.add_argument('--seats',type=Path,required=True);p.add_argument('--sockets',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--maximum-connector-path',type=float,default=8.);p.add_argument('--allow-reinforced-long-brackets',action='store_true');a=p.parse_args();assert 0<a.maximum_connector_path<=(20 if a.allow_reinforced_long_brackets else 8);d=json.loads(a.steel.read_text('utf8'));s=json.loads(a.seats.read_text('utf8'));assert s['model_source_sha256']==d['model_source_sha256'] and s['directory_geometry_sha256']==d['directory_geometry_sha256']
 if a.sockets:
  q=json.loads(a.sockets.read_text('utf8'));assert q['model_source_sha256']==d['model_source_sha256'] and q['directory_geometry_sha256']==d['directory_geometry_sha256'];d['socket_requests']=q['sockets'];d['socket_request_source_sha256']=hashlib.sha256(a.sockets.read_bytes()).hexdigest()
 requests={v['socket_id']:v for v in d['socket_requests']};used=set();anchors=[];reports=[]
 def mesh(name,leg,side,component,v,faces=FACES):
  v=np.array(v);centre=v.mean(axis=0);xyz=(v-centre).astype(np.float32).astype(float)[faces];rgb=np.column_stack([xyz,np.tile([.36,.43,.48],(len(xyz),1))]);d['pieces'].append(dict(name=name,leg=leg,side=side,component=component,frame=dict(translation=centre.tolist(),quaternion_xyzw=[0,0,0,1]),triangles_rgb=rgb.ravel().tolist()))
 for seat in s['seats']:
  key=seat['socket_id'];assert key in requests and key not in used;used.add(key);q=requests[key];A=np.asarray(q['rail_bearing'],dtype=float);B=np.asarray(seat['bearing'],dtype=float);n=np.asarray(seat['normal'],dtype=float);assert np.sum(np.abs(n))==1 and np.linalg.norm(n)==1;distance=np.linalg.norm(B-A);limit=float(seat.get('finite_connector_limit_m',s.get('finite_connector_limit_m',q['maximum_native_connector_m'])));assert np.isfinite(limit) and 0<limit<=a.maximum_connector_path and 0<distance<=limit+1e-7,(key,distance,limit)
  via=np.asarray(seat.get('connector_via_world',[]),dtype=float)
  assert via.size==0 or via.ndim==2 and via.shape[1]==3 and len(via)<=4 and np.all(np.isfinite(via)),('Finite explicit bent connector required',key)
  route=[A,*list(via),B];lengths=[np.linalg.norm(T-F)for F,T in zip(route,route[1:])]
  assert all(v>1e-6 for v in lengths) and sum(lengths)<=a.maximum_connector_path,('Actual finite steel length exceeded',key,lengths)
  width=float(seat.get('connector_width_m',.12));long=sum(lengths)>8
  assert width>=.12 and (not long or a.allow_reinforced_long_brackets and width>=.25 and seat.get('secondary_native_seat')),('Long main requires a real reinforced second foot',key)
  half=width/2
  for segment,(F,T,length) in enumerate(zip(route,route[1:],lengths)):
   z=(T-F)/length;x=np.cross(z,[0,1,0]);x=np.cross(z,[1,0,0]) if np.linalg.norm(x)<.1 else x;x/=np.linalg.norm(x);y=np.cross(z,x);corners=np.array([[-half,-half,0],[half,-half,0],[half,half,0],[-half,half,0],[-half,-half,length],[half,-half,length],[half,half,length],[-half,half,length]]);v=corners@np.stack([x,y,z],axis=1).T+F;name=f'upright_native_connector/{len(anchors)}'+(f'/{segment}' if segment else '');mesh(name,q['leg'],q['side'],'bracket',v)
  seat_half=float(seat.get('native_seat_width_m',.2))/2
  assert seat_half>=width/2
  u=np.array([0,1.,0]) if abs(n[0])>.5 else np.array([1.,0,0]);v0=np.cross(n,u);corners=np.array([[-seat_half,-seat_half,0],[seat_half,-seat_half,0],[seat_half,seat_half,0],[-seat_half,seat_half,0],[-seat_half,-seat_half,.05],[seat_half,-seat_half,.05],[seat_half,seat_half,.05],[-seat_half,seat_half,.05]]);v=corners@np.stack([u,v0,n],axis=1).T+B;name=f'upright_native_seat/{len(anchors)}';mesh(name,q['leg'],q['side'],'native_seat',v)
  tri=np.asarray(q['actual_rail_weld_triangle'],dtype=float);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal);u=(tri[1]-tri[0])/np.linalg.norm(tri[1]-tri[0]);v0=np.cross(normal,u);poly=list((tri-A)@np.stack([u,v0],axis=1))
  for axis in (0,1):
   for bound,above in ((-.08,True),(.08,False)):
    out=[];previous=poly[-1];old=previous[axis]>=bound if above else previous[axis]<=bound
    for current in poly:
     now=current[axis]>=bound if above else current[axis]<=bound
     if old!=now:out.append(previous+(current-previous)*(bound-previous[axis])/(current[axis]-previous[axis]))
     if now:out.append(current)
     previous=current;old=now
    poly=out
  patch=np.array(poly)@np.stack([u,v0],axis=1).T+A;npatch=len(patch);assert npatch>=3
  v=np.concatenate([patch,patch-normal*.03]);faces=[]
  for i in range(1,npatch-1):faces.extend([0,i,i+1,npatch,npatch+i+1,npatch+i])
  for i in range(npatch):j=(i+1)%npatch;faces.extend([i,j,npatch+j,i,npatch+j,npatch+i])
  mesh(f'upright_rail_weld/{len(anchors)}',q['leg'],q['side'],'bracket',v,np.array(faces));anchors.append(dict(leg=q['leg'],at=seat['at'],state=seat['state'],bearing=seat['bearing'],normal=seat['normal'],seat_piece=name,socket_id=key));reports.append(dict(socket_id=key,actual_connector_length_m=float(sum(lengths)),direct_native_face_distance_m=float(distance),connector_world_path=[point.tolist() for point in route],native_seat_piece=name,actual_weld_patch_maximum_span_m=.16,actual_weld_patch_vertex_count=npatch))
  secondary=seat.get('secondary_native_seat')
  if secondary:
   assert a.allow_reinforced_long_brackets and width>=.25
   B2=np.array(secondary['bearing']);n2=np.array(secondary['normal']);assert np.linalg.norm(n2)==1 and np.count_nonzero(n2)==1
   branch=[A,*[np.array(v) for v in secondary['connector_via_world']],B2]
   branch_lengths=[float(np.linalg.norm(T-F)) for F,T in zip(branch,branch[1:])]
   assert np.allclose(branch[1],route[1],atol=1e-9,rtol=0) and sum(branch_lengths)<=a.maximum_connector_path
   assert np.linalg.norm(B2-B)>=1.5 and np.linalg.norm(np.cross(B-route[1],B2-route[1]))/2>=.75
   assert secondary['at']!=seat['at'] and secondary['selected_by']=='applied_current_lining' and seat['selected_by']=='applied_current_lining'
   # First normal-exit leg is shared by main and diagonal; do not double it.
   for segment,(F,T,length) in enumerate(zip(branch[1:],branch[2:],branch_lengths[1:])):
    z=(T-F)/length;x=np.cross(z,[0,1,0]);x=np.cross(z,[1,0,0]) if np.linalg.norm(x)<.1 else x;x/=np.linalg.norm(x);y=np.cross(z,x)
    corners=np.array([[-half,-half,0],[half,-half,0],[half,half,0],[-half,half,0],[-half,-half,length],[half,-half,length],[half,half,length],[-half,half,length]])
    mesh(f'upright_native_diagonal/{len(reports)-1}/{segment}',q['leg'],q['side'],'bracket',corners@np.stack([x,y,z],axis=1).T+F)
   seat2half=float(secondary.get('native_seat_width_m',.35))/2;assert seat2half>=width/2
   u=np.array([0,1.,0]) if abs(n2[0])>.5 else np.array([1.,0,0]);v0=np.cross(n2,u)
   corners=np.array([[-seat2half,-seat2half,0],[seat2half,-seat2half,0],[seat2half,seat2half,0],[-seat2half,seat2half,0],[-seat2half,-seat2half,.05],[seat2half,-seat2half,.05],[seat2half,seat2half,.05],[-seat2half,seat2half,.05]])
   second_name=f'upright_native_secondary_seat/{len(reports)-1}';mesh(second_name,q['leg'],q['side'],'native_seat',corners@np.stack([u,v0,n2],axis=1).T+B2)
   anchors.append(dict(leg=q['leg'],at=secondary['at'],state=secondary['state'],bearing=secondary['bearing'],normal=secondary['normal'],seat_piece=second_name,socket_id=key,role='reinforced_diagonal_second_native_foot'))
   reports[-1].update(diagonal_weld_to_foot_length_m=sum(branch_lengths),combined_steel_length_m=sum(lengths)+sum(branch_lengths[1:]),main_and_diagonal_width_m=width,secondary_native_seat=second_name)
 missing=sorted(set(requests)-used);d['anchors']=anchors;d['status']='SUPPORTED_FINAL_SOURCE' if not missing else 'PARTIAL_SUPPORT_GEOMETRY_ONLY';d['supports_complete']=not missing;d['unresolved_socket_ids']=missing;d['native_seat_selection_sha256']=hashlib.sha256(a.seats.read_bytes()).hexdigest();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,separators=(',',':')),'utf8');a.output.with_suffix('.SUPPORT_RECEIPT.json').write_text(json.dumps(dict(source=str(a.output.resolve()),sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),supports=len(anchors),missing_socket_ids=missing,connector_lengths=reports,source_generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),world_written=False,production_enable=False),indent=2),'utf8');print(a.output,len(anchors),'supports',len(missing),'pending',flush=True)
if __name__=='__main__':main()
