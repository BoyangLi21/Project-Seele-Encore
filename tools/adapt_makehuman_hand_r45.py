"""Fit CC0 MakeHuman hand topology to EVA, retaining artist dorsal armour.

Only body-group hand faces are read. Human skeleton/weights are asset data;
no downloaded code executes. Each phalanx fits the measured EVA neutral frame.
"""
from pathlib import Path
import argparse,copy,json,collections
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.interpolate import RBFInterpolator
from author_anatomical_hand_rig_r45 import unit,model_matrix

ROOT=Path(__file__).resolve().parents[1]
def subdivide(points,faces,weights):
 data=np.c_[points,weights];face_points=np.asarray([data[f].mean(0)for f in faces]);edges=collections.defaultdict(list);vertex_faces=collections.defaultdict(list);vertex_edges=collections.defaultdict(list)
 for i,f in enumerate(faces):
  for v in f:vertex_faces[v].append(i)
  for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))].append(i)
 edge_keys=list(edges);edge_indices={e:len(data)+len(faces)+i for i,e in enumerate(edge_keys)};edge_points=[]
 for a,b in edge_keys:
  adjacent=edges[(a,b)];vertex_edges[a].append((a,b));vertex_edges[b].append((a,b))
  edge_points.append((data[a]+data[b]+face_points[adjacent].sum(0))/4 if len(adjacent)==2 else (data[a]+data[b])*.5)
 out=data.copy()
 for v in range(len(data)):
  es=vertex_edges[v];boundary=[b if a==v else a for a,b in es if len(edges[(a,b)])==1]
  if len(boundary)==2:out[v]=(6*data[v]+data[boundary].sum(0))/8
  elif es:
   n=len(vertex_faces[v]);F=face_points[vertex_faces[v]].mean(0);mid=np.asarray([(data[a]+data[b])*.5 for a,b in es]).mean(0);out[v]=(F+2*mid+(n-3)*data[v])/n
 quads=[]
 for i,f in enumerate(faces):
  for k,v in enumerate(f):quads.append([v,edge_indices[tuple(sorted((v,f[(k+1)%len(f)])))],len(data)+i,edge_indices[tuple(sorted((f[k-1],v)))]] )
 out=np.concatenate([out,face_points,edge_points]);w=np.maximum(0,out[:,3:]);w/=w.sum(1)[:,None]
 return out[:,:3],quads,w
def main():
 p=argparse.ArgumentParser();p.add_argument('--basis',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 c=json.loads((a.basis/'hand_rig_contract.json').read_text());key=c['rig'];name=f'eva_unit0{key}';geo=json.loads((a.basis/(name+'.geo.json')).read_text());bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};cache={};artist=json.loads((a.basis/(name+'_anatomical_hands_r45.mesh.json')).read_text())
 source=json.loads((a.reference/'default.mhskel').read_text());weight_data=json.loads((a.reference/'default_weights.mhw').read_text());assert source['license']=='CC0'and weight_data['license']=='CC0'
 vertices=[];faces=[];group=''
 for line in(a.reference/'base.obj').read_text().splitlines():
  if line.startswith('v '):vertices.append([float(x)for x in line.split()[1:4]])
  elif line.startswith('g '):group=line[2:]
  elif line.startswith('f ')and group=='body':faces.append([int(s.split('/')[0])-1 for s in line.split()[1:]])
 vertices=np.asarray(vertices);src_joint=lambda key:vertices[source['joints'][key]].mean(0)
 def source_head(bone):return src_joint(source['bones'][bone]['head'])
 def source_tail(bone):return src_joint(source['bones'][bone]['tail'])
 src_wrist=source_head('wrist.L');src_middle=source_head('finger3-1.L');src_along=unit(src_middle-src_wrist);src_width=unit(source_head('finger2-1.L')-source_head('finger5-1.L'));src_normal=-unit(np.cross(src_width,src_along))
 hand_names=[n for n in weight_data['weights']if n.endswith('.L')and(n.startswith('finger')or n.startswith('metacarpal')or n.startswith('wrist'))]
 mass=np.zeros(len(vertices))
 for n in hand_names:
  for i,w in weight_data['weights'][n]:mass[i]+=w
 included=[face for face in faces if all(mass[i]>.30 for i in face)]
 keep=sorted({i for f in included for i in f});index={old:i for i,old in enumerate(keep)}
 mapped_faces=[[index[i]for i in f]for f in included]
 game=json.loads((ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/mesh/{name}.mesh.json').read_text())
 output=dict(format_version=1,model_height=192,stride=8,parts={},jointSkins={},source='CC0 MakeHuman hand topology fitted to EVA; original EVA dorsal armour retained',r37_mouth={'preserve_auto_joint_seams':True})
 reports=[]
 for side in ['l','r']:
  h=c['hands'][side];hand='hand_'+side;n=np.asarray(h['palmar_normal_bind']);target_wrist=np.asarray(bones[hand]['pivot'])*[-1,1,1]/16
  digit_numbers=dict(thumb=1,index=2,middle=3,ring=4,little=5)
  source_points=[src_wrist];target_points=[target_wrist]
  for digit in ['index','middle','ring','little']:
   source_points.append(source_head(f'finger{digit_numbers[digit]}-1.L'));target_points.append(h['digits'][digit]['joints'][0]['head_bind'])
  src_centre=np.mean(source_points,axis=0);dst_centre=np.mean(target_points,axis=0)
  # The source .L frame has its palmar normal in the opposite half-space.
  radial_scale=np.linalg.norm(np.asarray(target_points[1])-target_points[4])/np.linalg.norm(source_points[1]-source_points[4])
  source_points += [src_centre+src_normal*.25,src_centre-src_normal*.25]
  target_points += [dst_centre+n*.25*radial_scale,dst_centre-n*.25*radial_scale]
  affine=np.linalg.lstsq(np.c_[source_points,np.ones(len(source_points))],target_points,rcond=None)[0]
  palette=[hand]+[j['name']for d in h['digits'].values()for j in d['joints']];weights=np.zeros((len(keep),len(palette)));transforms={hand:affine};landmark_source=[src_wrist];landmark_target=[target_wrist]
  assigned={n:hand for n in hand_names if not n.startswith('finger')}
  for digit,number in digit_numbers.items():
   for j,joint in enumerate(h['digits'][digit]['joints']):
    source_name=f'finger{number}-{j+1}.L';head=source_head(source_name);tail=source_tail(source_name);sy=unit(tail-head);sx=unit(np.cross(src_normal,sy));sz=unit(np.cross(sx,sy));sf=np.column_stack([sx,sy,sz])
    dy=unit(np.asarray(joint['tip_bind'])-np.asarray(joint['head_bind']));dx=unit(np.cross(n,dy));dz=unit(np.cross(dx,dy));tf=np.column_stack([dx,dy,dz])
    # The left/right target frame is right-handed; mirror the source cross
    # coordinate before fitting the right hand, never negate a runtime scale.
    scales=np.array([radial_scale,joint['length']/np.linalg.norm(tail-head),radial_scale])
    scales[0]*=np.sign(np.linalg.det(affine[:3].T))
    mat=tf@np.diag(scales)@sf.T;shift=np.asarray(joint['head_bind'])-mat@head
    transforms[joint['name']]=np.vstack([mat.T,shift]);assigned[source_name]=joint['name']
    landmark_source.extend([head,tail]);landmark_target.extend([joint['head_bind'],joint['tip_bind']])
  for source_name in hand_names:
   column=palette.index(assigned[source_name])
   for old,w in weight_data['weights'][source_name]:
    if old in index:weights[index[old],column]+=w
  weights[:,0]+=np.maximum(0,1-weights.sum(1));weights/=weights.sum(1)[:,None]
  # One continuous spatial fit preserves the topology between metacarpals.
  # Independent per-bone affine fits disagree at the webs even in rest pose.
  for p0,q0 in [(src_wrist,target_wrist),(src_centre,dst_centre)]:
   for sign in [-1,1]:landmark_source.append(p0+src_normal*.22*sign);landmark_target.append(q0+n*.22*radial_scale*sign)
  unique={}
  for src,dst in zip(landmark_source,landmark_target):unique[tuple(np.round(src,6))]=np.asarray(dst)
  ls=np.asarray(list(unique));lt=np.asarray(list(unique.values()));warp=RBFInterpolator(ls,lt,kernel='thin_plate_spline',degree=1,smoothing=1e-8)
  ps=warp(vertices[keep]);fit_error=float(np.linalg.norm(warp(ls)-lt,axis=1).max())
  ps,fitted_faces,weights=subdivide(ps,mapped_faces,weights)
  triangles=[]
  for face in fitted_faces:
   for i in range(1,len(face)-1):triangles.append([face[0],face[i],face[i+1]])
  triangles=np.asarray(triangles)
  # Affine mirroring reverses the winding. Determine it from the fitted palm.
  if np.linalg.det(affine[:3].T)<0:triangles=triangles[:,[0,2,1]]
  normals=np.zeros_like(ps)
  for tri in triangles:
   cross=np.cross(ps[tri[1]]-ps[tri[0]],ps[tri[2]]-ps[tri[0]])
   for i in tri:normals[i]+=cross
  normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
  # One midpoint subdivision improves the retained quad-derived topology;
  # the source vertex weights interpolate continuously across the split.
  uv=np.asarray(game['parts']['finger_middle_'+side]['vertices'][3:5]);packed=[];skin=[]
  pivot=np.asarray(bones[hand]['pivot'])
  for ids in triangles:
   for i in ids:packed.extend([*(ps[i]*[-1,1,1]*16-pivot),*uv,*(normals[i]*[-1,1,1])]);skin.append(weights[i])
  # Existing dorsal armour is an overlay. Its original artist texture stays;
  # underlying continuous glove closes joints and the palm-facing side.
  old=artist['parts'][hand];raw=np.asarray(old['vertices']).reshape(-1,8);oldw=artist['jointSkins'][hand]['influences']
  armour_triangles=0
  for begin in range(0,len(raw),3):
   tri=raw[begin:begin+3];positions=(tri[:,:3]+pivot)*[-1,1,1]/16;ns=tri[:,5:8]*[-1,1,1]
   # Retain only the original palm triangles: finger loft vertices use a
   # constant uniform UV, so exact UV variation distinguishes artist faces.
   if np.ptp(tri[:,3:5],axis=0).max()<1e-6:continue
   for k in range(3):
    packed.extend(tri[k]);w=np.zeros(len(palette));w[0]=1;skin.append(w)
   armour_triangles+=1
  skin=np.asarray(skin);output['parts'][hand]=dict(pivot=pivot.tolist(),vertices=np.round(packed,7).tolist());output['jointSkins'][hand]=dict(influences={bone:np.round(skin[:,i],7).tolist()for i,bone in enumerate(palette)},inverseBindColumnMajor={bone:np.linalg.inv(model_matrix(bones,bone,cache)).T.reshape(-1).tolist()for bone in palette})
  reports.append(dict(side=side,source_hand_vertices=len(keep),source_quad_faces=len(included),fitted_quads=len(fitted_faces),landmark_fit_error=fit_error,palm_determinant=float(np.linalg.det(affine[:3].T)),source_weights_preserved_and_rebound=True,original_dorsal_triangles=armour_triangles,thumb_base_topology='Continuous anatomical source web'))
 c['construction']['topology_source']='MakeHuman base mesh, CC0, immutable source SHA manifest in sibling makehuman_reference'
 c['construction']['makehuman_fit']=reports;c['construction']['visual_passed']=False
 (a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8');(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(output,separators=(',',':')),'utf8');(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8');print(json.dumps(reports))

if __name__=='__main__':main()
