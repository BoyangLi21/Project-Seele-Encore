"""Build the actual local captured-head slide and open spherical socket.

The original ball, stem, carrier and deck remain selected source geometry.
This writes only a model candidate, or its exact resource with --publish.
It never reads or writes a Minecraft world.
"""
from pathlib import Path
import argparse,json,hashlib,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'src/main/resources/assets/projectseele/mesh'
source=base/'upright_outer_captured_r52.json'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='18768bb49713daf08a8f3b9d186fff5ac123e21b471e8fcc21c7251e17a66fb7'
original=json.loads(source.read_text(encoding='utf-8'))
F=[0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5]
def box(b):
 x,y,z,X,Y,Z=b;v=[[x,y,z],[X,y,z],[X,Y,z],[x,Y,z],[x,y,Z],[X,y,Z],[X,Y,Z],[x,Y,Z]];return [a for i in F for a in v[i]+[.36,.43,.48]]
parts=[]
for side,frame in [(-1,'RUNNER_NEG'),(1,'RUNNER_POS')]:
 for name,role,b in [('stator','transfer_stator',[.08,0,-.72,.18,.06,.14]),('mount','transfer_stator',[.04,.09,.02,.12,.13,.10]),('post','transfer_stator',[.08,.06,.08,.12,.09,.12]),('lower','transfer_slider',[.07,-.02,-.025,.19,0,.025]),('left','transfer_slider',[.07,0,-.025,.08,.07,.025]),('right','transfer_slider',[.18,0,-.025,.19,.07,.025]),('upper','transfer_slider',[.07,.06,-.025,.19,.07,.025])]:parts.append({'name':f'outer/{side}/transfer/{name}','frame':frame,'role':role,'triangles_rgb':box(b)})
j={'schema':'projectseele.r53.actual-outer-head-slide.v1','outer_source_sha256':'18768bb49713daf08a8f3b9d186fff5ac123e21b471e8fcc21c7251e17a66fb7','retraction_metres':.65,'parts':parts}
overrides=[]
for side in [-1,1]:
 p=next(p for p in original['parts'] if p['name']==f'outer/{side}/ball_socket');tri=np.array(p['triangles_rgb']).reshape(-1,3,6);values=[];rings=[[],[]];direction=-side;plane=.03
 for t in tri:
  poly=list(t);cut=[]
  for a,b in zip(poly,poly[1:]+poly[:1]):
   ia=direction*a[0]<=plane+1e-12;ib=direction*b[0]<=plane+1e-12
   if ia:cut.append(a)
   if ia!=ib:
    q=a+(b-a)*(plane-direction*a[0])/(direction*(b[0]-a[0]));q[0]=direction*plane;cut.append(q);r=np.linalg.norm(t[:,:3]-np.array([0,.35,0]),axis=1).mean();rings[int(r>.20)].append(q[:3])
  for i in range(1,len(cut)-1):values.extend(np.array([cut[0],cut[i],cut[i+1]]).ravel().tolist())
 contours=[]
 for points in rings:
  q=np.unique(np.round(points,12),axis=0);angle=np.arctan2(q[:,2],q[:,1]-.35);contours.append(q[np.argsort(angle)])
 angles=sorted(set(round(math.atan2(q[2],q[1]-.35),12) for ps in contours for q in ps))
 def point_at(poly,a):
  u=np.array([math.cos(a),math.sin(a)]);P=poly[:,[1,2]]-[.35,0]
  for x,y in zip(P,np.roll(P,-1,axis=0)):
   delta=y-x;den=u[0]*delta[1]-u[1]*delta[0]
   if abs(den)<1e-15:continue
   r=(x[0]*delta[1]-x[1]*delta[0])/den;t=-(u[0]*x[1]-u[1]*x[0])/den
   if r>=0 and -1e-8<=t<=1+1e-8:return np.array([direction*plane,.35+r*u[0],r*u[1]])
  raise ValueError('ring ray does not intersect')
 for a,b in zip(angles,angles[1:]+[angles[0]+2*math.pi]):
  ia,ib=point_at(contours[0],a),point_at(contours[0],b);oa,ob=point_at(contours[1],a),point_at(contours[1],b)
  for t in [[ia,ib,ob],[ia,ob,oa]]:
   if direction>0:t=list(reversed(t))
   for q in t:values.extend(q.tolist()+[.36,.43,.48])
 out={k:v for k,v in p.items() if k!='triangles_rgb'};out['triangles_rgb']=values;overrides.append(out)
j['socket_openings']={'plane_toward_original_inward_beam_m':.03,'retained_socket':'>half-sphere with finite closed annular wall rim; aperture smaller than original ball diameter','original_ball_socket_parts':[p['name'] for p in overrides]};j['socket_overrides']=overrides

a=argparse.ArgumentParser();a.add_argument('--publish',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'.Codex/map_complete_20261013/route_audit/phases_r53/rebuilt_head_source.json');args=a.parse_args()
p=base/'outer_head_transfer_r53.json' if args.publish else args.output
p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,separators=(',',':')),encoding='utf-8')
print(p,hashlib.sha256(p.read_bytes()).hexdigest())
