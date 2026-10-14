from pathlib import Path
import json,hashlib,numpy as np,math
root=Path(__file__).resolve().parents[1];p=root/'.Codex/r52_continuous_route_migration_20261012';p.mkdir(parents=True,exist_ok=True)
actual=json.loads((root/'tools/data/upright_outer_reverse_deck_contacts_r53.json').read_text('utf8'));parts=[];links=[]
def part(name,frame,xyz,role):
 parts.append(dict(name=name,frame=frame,role=role,triangles_rgb=np.asarray(xyz,dtype=np.float32).ravel().astype(float).tolist()))
def colored(tri):
 return np.concatenate([np.asarray(tri).reshape(-1,3),np.tile([.36,.43,.48],(np.asarray(tri).size//3,1))],axis=1)
faces=np.array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5])
def box(lo,hi):
 x,y,z=lo;X,Y,Z=hi;v=np.array([[x,y,z],[X,y,z],[X,Y,z],[x,Y,z],[x,y,Z],[X,y,Z],[X,Y,Z],[x,Y,Z]]);return colored(v[faces])
def sphere(radius,centre,reverse=False):
 out=[];n,m=48,96
 def q(a,b):return np.array([radius*math.sin(a)*math.cos(b),radius*math.cos(a),radius*math.sin(a)*math.sin(b)])+centre
 for i in range(n):
  a,b=math.pi*i/n,math.pi*(i+1)/n
  for j in range(m):
   c,d=2*math.pi*j/m,2*math.pi*(j+1)/m;A,B,C,D=q(a,c),q(b,c),q(b,d),q(a,d)
   if i>0:out.extend([A,C,B] if reverse else [A,B,C])
   if i<n-1:out.extend([A,D,C] if reverse else [A,C,D])
 return colored(out)
for side in (-1,1):
 pin=np.array([side*15.,-3.42,-side*14.78]);row=next(v for v in actual['actual_deck_connections'] if v['variant']==0 and v['radius']==15. and v['side']==side);tri=np.array(row['actual_deck_face']);a=tri.mean(axis=0);D=pin-a;length=np.linalg.norm(D);assert length<=3
 elbow=np.array([a[0],pin[1],a[2]]);segments=[]
 for j,(A,B) in enumerate(((a,elbow),(elbow,pin))):
  delta=B-A;span=np.linalg.norm(delta);Y=delta/span;axis=np.array([0.,1.,0.]) if abs(Y[1])<.95 else np.array([0.,0.,1.]);X=np.cross(Y,axis);X/=np.linalg.norm(X);Z=np.cross(X,Y);R=np.stack([X,Y,Z],axis=1)
  b=box([-.10,-.08,-.10],[.10,span+.04,.10]);b[:,:3]=b[:,:3]@R.T+A;part(f'outer/{side}/short_deck_beam/{j}','ROOT',b,'structure');segments.append(dict(from_root_local=A.tolist(),to_root_local=B.tolist(),actual_length_m=float(span)))
 n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);n/=np.linalg.norm(n);v=np.concatenate([tri,tri+n*.04]);f=[0,1,2,3,5,4,0,3,4,0,4,1,1,4,5,1,5,2,2,5,3,2,3,0];part(f'outer/{side}/actual_deck_weld','ROOT',colored(v[f]),'deck_weld');part(f'outer/{side}/ball','ROOT',sphere(.18,pin),'ball');links.append(dict(side=side,pin_root_local=pin.tolist(),actual_deck_triangle_root_local=tri.tolist(),actual_weld_centroid_root_local=a.tolist(),actual_short_beam_direct_length_m=length,actual_short_beam_segments=segments,actual_weld_area_m2=np.linalg.norm(np.cross(tri[1]-tri[0],tri[2]-tri[0]))/2))
 # Both articulation axes are carried by the compact spherical joint.
 frame='RUNNER_NEG' if side<0 else 'RUNNER_POS'
 cup=np.concatenate([sphere(.23,np.array([0,.35,0])),sphere(.1802,np.array([0,.35,0]),True)])
 part(f'outer/{side}/ball_socket',frame,cup,'ball_socket');part(f'outer/{side}/socket_neck',frame,box([-.05,-.035,-.05],[.05,.15,.05]),'structure')
 part(f'outer/{side}/capture_crossbar',frame,box([-.344,-.035,-.20],[.344,-.020,.20]),'capture_structure')
 part(f'outer/{side}/upper_pad_web',frame,box([-.20,-.055,-.004],[.20,-.020,.004]),'capture_structure')
 old=json.loads((root/'src/main/resources/assets/projectseele/mesh/legacy_running_heads_r52.json').read_text());part(f'outer/{side}/upper_bearing',frame,np.array(old['parts']['ride_contact_pad']).reshape(-1,6),'upper_bearing')
 for s in (-1,1):
  lo,hi=(-.344,-.306) if s<0 else (.306,.344)
  part(f'outer/{side}/capture_cheek/{s}',frame,box([lo,-.244,-.20],[hi,-.020,.20]),'capture_structure')
  lo,hi=(-.344,-.21) if s<0 else (.21,.344)
  part(f'outer/{side}/capture_under/{s}',frame,box([lo,-.244,-.20],[hi,-.205,.20]),'capture_structure')
  lo,hi=(-.30,-.12) if s<0 else (.12,.30)
  part(f'outer/{side}/lower_bearing/{s}',frame,box([lo,-.206,-.004],[hi,-.20,.004]),'lower_bearing')
  lo,hi=(-.306,-.30) if s<0 else (.30,.306)
  part(f'outer/{side}/side_bearing/{s}',frame,box([lo,-.20,-.004],[hi,-.08,.004]),'side_bearing')
doc=dict(schema='projectseele.r52.upright-outer-captured-model.v1',original_full_source_sha256='0fa6f8fe5e0d4195ae52702ecb0bcc366057ca76490b490ecae39892f91e7561',original_running_source_sha256='63fa3c8c4140a34557ee7a07f47a7bc82485900b68d669b11457ba6b1aee3f97',retired_r52_addon='FootGuideRig stator/rotor only; unchanged original carrier/deck/four housing heads remain',mounts_root_local=[[-15.,-3.42,14.78],[15.,-3.42,-14.78]],rail_head_section=[-.30,-.20,.30,-.08],rail_web_section=[-.10,-.55,.10,-.20],runner_origin_from_ball_local=[0,-.35,0],ball_radius_m=.18,socket_inner_radius_m=.1802,socket_outer_radius_m=.23,actual_connections=links,parts=parts)
target=root/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json';target.write_text(json.dumps(doc,separators=(',',':')));digest=hashlib.sha256(target.read_bytes()).hexdigest();(p/'OUTER_CAPTURED_MODEL_SOURCE_RECEIPT.json').write_text(json.dumps(dict(source=str(target.resolve()),sha256=digest,actual_connections=links,parts=len(parts),triangles=sum(len(v['triangles_rgb'])//18 for v in parts),native_admission=False,world_written=False),indent=2));print(digest,links)
