"""Root-declared61c9 paths -> real outer rail steel and exact socket triangles.

Geometry only. Native anchor selection/World writes belong to Root. The
unanchored output cannot enable production movement.
"""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FACES=np.array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5])
BASIS=np.diag([-1.,1.,-1.])
def bezier(p,t):return sum(math.comb(len(p)-1,i)*t**i*(1-t)**(len(p)-1-i)*v for i,v in enumerate(p))
def normal_frame(T):
 z=T/np.linalg.norm(T);x=np.array([-1.,0,0])-z*z[0]*-1;x/=np.linalg.norm(x);return np.stack([x,np.cross(z,x),z],axis=1)
def main():
 a=argparse.ArgumentParser();a.add_argument('--directory',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--maximum-span',type=float,default=12.);args=a.parse_args()
 doc=json.loads(args.directory.read_text('utf8'));nodes={n['id']:n for n in doc['nodes']};model_path=ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json';model=json.loads(model_path.read_text('utf8'));model_sha=hashlib.sha256(model_path.read_bytes()).hexdigest();nom=json.loads((ROOT/'src/main/resources/assets/projectseele/mesh/foot_guide_rig_r52.json').read_text('utf8'))['nominal_sole_bindings'];paths=[];pieces=[];sockets=[];counts=[]
 for leg in doc['legs']:
  if 'centre_curve' not in leg or leg['id'].endswith('/reverse'):continue
  variant=next(route['variant'] for route in doc['routes'] if leg['id'] in route['legs']);centre=(np.array(nom[str(variant)]['l'])+np.array(nom[str(variant)]['r']))/2;segments=leg['centre_curve']['segments'];knots=[]
  def evaluate(control,t):
   foot=bezier(control,t);d=bezier((len(control)-1)*np.diff(control,axis=0),t);Q=normal_frame(d);root=foot-BASIS@centre;frames=[]
   for m in model['mounts_root_local']:frames.append((root+BASIS@np.asarray(m)-Q[:,1]*.35,Q))
   return foot,frames
  def corners(frames):
   out=[]
   for origin,Q in frames:
    for s in [model['rail_head_section'],model['rail_web_section']]:
     for x,y in [(s[0],s[1]),(s[2],s[1]),(s[2],s[3]),(s[0],s[3])]:out.append(origin+Q@np.array([x,y,0]))
   return np.array(out)
  def split(control,lo,hi,A,B,depth=0):
   C=corners(A[1]);D=corners(B[1]);error=0
   for f in (.25,.5,.75):
    M=evaluate(control,lo+(hi-lo)*f);error=max(error,float(np.max(np.linalg.norm(corners(M[1])-(C+(D-C)*f),axis=1))))
   if np.linalg.norm(B[0]-A[0])>8 or error>0.00005:
    assert depth<24,'Path geometric budget exceeded';mid=(lo+hi)/2;M=evaluate(control,mid);split(control,lo,mid,A,M,depth+1);split(control,mid,hi,M,B,depth+1)
   else:knots.append((A,B,error))
  for raw in segments:
   control=np.array(raw['controls'],float);split(control,0,1,evaluate(control,0),evaluate(control,1))
  # A finite real overrun keeps the complete pads/side bearings supported at
  # the declared centre endpoints. It changes no route point or EVA pose.
  def overrun_end(sample,amount):
   frames=[(O+Q[:,2]*amount,Q) for O,Q in sample[1]]
   return sample[0]+sample[1][0][1][:,2]*amount,frames
  start=knots[0][0];end=knots[-1][1]
  knots=[(overrun_end(start,-.30),start,0.)]+knots+[(end,overrun_end(end,.30),0.)]
  canonical={'segments':[dict(type='LINE' if len(s['controls'])==2 else 'QUINTIC_BEZIER',controls=s['controls']) for s in segments]};paths.append(dict(leg=leg['id'],reverse_leg=leg['id']+'/reverse',variant=variant,from_=nodes[leg['from']]['foot_frame'],to=nodes[leg['to']]['foot_frame'],centre_curve=canonical))
  paths[-1]['from']=paths[-1].pop('from_');distance=0;next_seat=[args.maximum_span/2,args.maximum_span/2]
  for i,(A,B,error) in enumerate(knots):
   length=float(np.linalg.norm(B[0]-A[0]));start_distance=distance;distance+=length
   for slot,side in enumerate((-1,1)):
    O,Q=A[1][slot];P,S=B[1][slot]
    for component,section in [('head',model['rail_head_section']),('web',model['rail_web_section'])]:
     x,y,X,Y=section;local=np.array([[x,y,0],[X,y,0],[X,Y,0],[x,Y,0]]);v=np.concatenate([local@Q.T+O,local@S.T+P]);position=v.mean(axis=0);local_vertices=(v-position).astype(np.float32).astype(float);rgb=np.column_stack([local_vertices[FACES],np.tile([.36,.43,.48],(len(FACES),1))]);name=f'upright_rail/{leg["id"]}/{side}/{i}/{component}';pieces.append(dict(name=name,leg=leg['id'],side=side,component=component,frame=dict(translation=position.tolist(),quaternion_xyzw=[0,0,0,1]),triangles_rgb=rgb.ravel().tolist()))
     if component=='web' and (distance>=next_seat[slot] or i==len(knots)-1):
      actual=local_vertices+position;tri=actual[[0,1,5]];point=tri.mean(axis=0);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal);sockets.append(dict(socket_id=f'upright_seat_request/{leg["id"]}/{side}/{len(sockets)}',leg=leg['id'],side=side,rail_piece=name,rail_bearing=point.tolist(),actual_rail_weld_triangle=tri.tolist(),normal=normal.tolist(),along_curve_m=(start_distance+distance)/2,maximum_native_connector_m=4.));next_seat[slot]=distance+args.maximum_span
  counts.append(dict(leg=leg['id'],actual_rendered_rail_intervals=len(knots),actual_polyline_length_m=distance,maximum_authored_corner_probe_error_m=max(k[2] for k in knots)));print(leg['id'],len(knots),'intervals',len(sockets),'sockets',flush=True)
 output=dict(schema='projectseele.r52.upright-captured-paths.v1',profile='projectseele.r52.upright-captured-guideway.v1',status='UNANCHORED_GEOMETRY_ONLY',model_source_sha256=model_sha,head_transfer_source_sha256=hashlib.sha256((ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json').read_bytes()).hexdigest(),directory_geometry_sha256=hashlib.sha256(args.directory.read_bytes()).hexdigest(),paths=paths,pieces=pieces,anchors=[],socket_requests=sockets,path_geometry_report=counts,world_written=False,native_admission=False)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(output,separators=(',',':')),encoding='utf8');digest=hashlib.sha256(args.output.read_bytes()).hexdigest();receipt=args.output.with_suffix('.RECEIPT.json');receipt.write_text(json.dumps(dict(source=str(args.output.resolve()),sha256=digest,model_source_sha256=model_sha,head_transfer_source_sha256=hashlib.sha256((ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json').read_bytes()).hexdigest(),directory_geometry_sha256=output['directory_geometry_sha256'],paths=len(paths),pieces=len(pieces),socket_requests=len(sockets),source_generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),world_written=False,production_enable=False),indent=2));args.output.with_suffix('.SOCKETS.json').write_text(json.dumps(dict(model_source_sha256=model_sha,head_transfer_source_sha256=hashlib.sha256((ROOT/'src/main/resources/assets/projectseele/mesh/outer_head_transfer_r53.json').read_bytes()).hexdigest(),directory_geometry_sha256=output['directory_geometry_sha256'],sockets=sockets),indent=2));print(receipt,digest,flush=True)
if __name__=='__main__':main()
