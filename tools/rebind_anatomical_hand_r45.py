"""Rebuild the entire hand rig from coherent CC0 hand topology.

All palm/finger vertices share one monotonic anatomical fit. Straightening is
then an actual DQ skeletal pose, baked into a new bind, never separate finger
affine fits. This preserves web continuity and avoids opposing reflections.
"""
from pathlib import Path
import argparse,collections,copy,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import make_tiger_unit01_pack as tiger
from author_anatomical_hand_rig_r45 import model_matrix,unit
from adapt_makehuman_hand_r45 import subdivide

ROOT=Path(__file__).resolve().parents[1]
def dq_pose(points,weights,matrices):
 qs=[];duals=[]
 for m in matrices:
  q=R.from_matrix(m[:3,:3]).as_quat();t=m[:3,3]
  d=np.r_[q[3]*t+np.cross(t,q[:3]),-t@q[:3]]*.5;qs.append(q);duals.append(d)
 qs=np.asarray(qs);duals=np.asarray(duals);ref=qs[np.argmax(weights,axis=1)];sign=np.where(ref@qs.T<0,-1,1);w=weights*sign
 q=w@qs;d=w@duals;norm=np.linalg.norm(q,axis=1)[:,None];q/=norm;d/=norm;d-=q*np.sum(q*d,axis=1)[:,None]
 xyz=q[:,:3];dw=d[:,3,None];qw=q[:,3,None];translation=2*(-dw*xyz+qw*d[:,:3]+np.cross(xyz,d[:,:3]));a=2*np.cross(xyz,points)
 return points+qw*a+np.cross(xyz,a)+translation

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--basis',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--palm-cup',action='store_true');ap.add_argument('--palm-finger-ratio',type=float);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 old=json.loads((a.basis/'hand_rig_contract.json').read_text());rig=old['rig'];name=f'eva_unit0{rig}';c=copy.deepcopy(old)
 geo=json.loads((a.basis/(name+'.geo.json')).read_text());bs=geo['minecraft:geometry'][0]['bones'];bs[:]=[b for b in bs if not b['name'].startswith('r45_hand_')];bones={b['name']:b for b in bs};cache={};c['new_bones']=[]
 mh=json.loads((a.reference/'default.mhskel').read_text());mhw=json.loads((a.reference/'default_weights.mhw').read_text());assert mh['license']==mhw['license']=='CC0'
 verts=[];faces=[];group=''
 for line in(a.reference/'base.obj').read_text().splitlines():
  if line.startswith('v '):verts.append([float(x) for x in line.split()[1:4]])
  elif line.startswith('g '):group=line[2:]
  elif line.startswith('f ')and group=='body':faces.append([int(x.split('/')[0])-1 for x in line.split()[1:]])
 verts=np.asarray(verts)
 def source_point(bone,part):return verts[mh['joints'][mh['bones'][bone][part]]].mean(0)
 hand_names=[n for n in mhw['weights']if n.endswith('.L')and n.startswith(('wrist','metacarpal','finger'))];mass=np.zeros(len(verts))
 for n in hand_names:
  for i,w in mhw['weights'][n]:mass[i]+=w
 faces=[f for f in faces if all(mass[i]>.30 for i in f)];ids=sorted({i for f in faces for i in f});lookup={i:j for j,i in enumerate(ids)};faces=[[lookup[i]for i in f]for f in faces]
 sw=source_point('wrist.L','head');middle=source_point('finger3-1.L','head');sy=unit(middle-sw);sx=unit(source_point('finger2-1.L','head')-source_point('finger5-1.L','head'));sx=unit(sx-sy*(sx@sy));sz=unit(np.cross(sx,sy));S=np.column_stack([sx,sy,sz])
 smcp=np.asarray([source_point(f'finger{i}-1.L','head')for i in [2,3,4,5]]);source_palm_length=float(np.mean((smcp-sw)@sy));source_width=float(np.ptp((smcp-sw)@sx))
 ov,uv,ns,ot=tiger.parse_obj(Path(old['source']).read_text());tiger.CLEAN_GRIP_FINGERS=False;fb,_,_=tiger.discover_finger_rig(ov,ot);owners=tiger.complete_face_owners(ov,ot,fb);membership=collections.defaultdict(set)
 for i,f in enumerate(ot):
  for r in f:membership[tuple(np.round(ov[r[0]],6))].add(owners[i])
 minimum=min(p[1] for p in ov);factor=192/(max(p[1]for p in ov)-minimum)/16;native=lambda p:(np.asarray(p)-[0,minimum,0])*[-1,1,-1]*factor
 game=json.loads((ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/mesh/{name}.mesh.json').read_text());artist=json.loads((a.basis/(name+'_anatomical_hands_r45.mesh.json')).read_text())
 out=dict(format_version=1,model_height=192,stride=8,source='Coherent CC0 MakeHuman hand topology, EVA proportions, newly rebuilt neutral bind and original EVA palm armour',parts={},jointSkins={},r37_mouth={'preserve_auto_joint_seams':True});audit=[]
 for side in ['l','r']:
  hand='hand_'+side;h=old['hands'][side];old_normal=np.asarray(h['palmar_normal_bind']);ty=unit(h['longitudinal_bind']);roots=np.asarray([h['digits'][d]['joints'][0]['head_bind']for d in ['index','middle','ring','little']]);tx=unit(roots[0]-roots[-1]);tx=unit(tx-ty*(tx@ty));tz=unit(np.cross(tx,ty));T=np.column_stack([tx,ty,tz])
  # The fitted surface uses T. Reusing the old artist-palm PCA normal here
  # tilted the finger flexion plane by about30deg relative to the new palm.
  palm_normal=-tz if side=='l'else tz
  c['hands'][side]['palmar_normal_bind']=palm_normal.tolist()
  wrist=np.mean([native(p)for p,names in membership.items()if hand in names and 'forearm_'+side in names],axis=0)
  target_palm_length=float(np.mean((roots-wrist)@ty));target_width=float(np.ptp((roots-wrist)@tx));radial=target_width/source_width
  desired_finger=np.mean([sum(j['length']for j in h['digits'][d]['joints'])for d in ['index','middle','ring','little']]);source_finger=np.mean([sum(np.linalg.norm(source_point(f'finger{i}-{j}.L','tail')-source_point(f'finger{i}-{j}.L','head'))for j in range(1,4))for i in range(2,6)])
  if a.palm_finger_ratio is not None:
   assert .7<=a.palm_finger_ratio<=1.2
   total=target_palm_length+desired_finger;desired_finger=total/(1+a.palm_finger_ratio);target_palm_length=total-desired_finger
  finger_scale=desired_finger/source_finger;palm_scale=target_palm_length/source_palm_length
  # Positive derivative everywhere; palm and digits are never reflected or
  # displaced independently, so a web cannot fold inside-out at its boundary.
  def warp(points):
   local=(np.asarray(points)-sw)@S;x=local[...,0]*radial;y=local[...,1];z=local[...,2]*radial
   width=source_palm_length*.12;u=(y-source_palm_length)/width
   integral=width*np.logaddexp(0,u)-width*np.logaddexp(0,-source_palm_length/width)
   mapped_y=palm_scale*y+(finger_scale-palm_scale)*integral
   return np.stack([x,mapped_y,z],axis=-1)@T.T+wrist
  fitted=warp(verts[ids]);raw_joints={};new_specs=[];names=[];digit_source={};rest_matrices={};cup_parents={}
  for digit in ['cup_ring','cup_little']:c['hands'][side]['digits'].pop(digit,None)
  if a.palm_cup:
   for digit,number in [('ring',3),('little',4)]:
    source_name=f'metacarpal{number}.L';head=warp(source_point(source_name,'head'));tip=warp(source_point(source_name,'tail'));y=unit(tip-head);x=unit(np.cross(palm_normal,y));z=unit(np.cross(x,y));frame=np.column_stack([x,y,z]);parent_m=model_matrix(bones,hand,cache);pivot=(np.linalg.inv(parent_m)@np.r_[head,1])[:3];local=parent_m[:3,:3].T@frame
    bone=f'r45_hand_{side}_cup_{digit}';spec=dict(name=bone,parent=hand,pivot=(pivot*[-1,1,1]*16).tolist(),rotation=(R.from_matrix(local).as_euler('xyz',degrees=True)*[-1,-1,1]).tolist());bs.append(spec);bones[bone]=spec;new_specs.append(spec);names.append(bone);digit_source[source_name]=bone;cup_parents[digit]=bone;rest_matrices[bone]=model_matrix(bones,bone,cache)
    record=dict(name=bone,index=0,head_bind=head.tolist(),tip_bind=tip.tolist(),length=float(np.linalg.norm(tip-head)),rest_flex_degrees=0,anatomical_limits_degrees=[[0,25],[0,0],[0,0]])
    raw_joints[bone]=record;c['hands'][side]['digits']['cup_'+digit]=dict(joints=[record],source_rest='CC0 donor metacarpal; palm cupping helper')
  for digit,number in dict(thumb=1,index=2,middle=3,ring=4,little=5).items():
   parent=cup_parents.get(digit,hand);records=[]
   for i in range(3):
    source_name=f'finger{number}-{i+1}.L';head=warp(source_point(source_name,'head'));tip=warp(source_point(source_name,'tail'));y=unit(tip-head);x=unit(np.cross(palm_normal,y));z=unit(np.cross(x,y));frame=np.column_stack([x,y,z]);parent_m=model_matrix(bones,parent,cache);pivot=(np.linalg.inv(parent_m)@np.r_[head,1])[:3];local=parent_m[:3,:3].T@frame
    bone=f'r45_hand_{side}_{digit}_{i+1}';spec=dict(name=bone,parent=parent,pivot=(pivot*[-1,1,1]*16).tolist(),rotation=(R.from_matrix(local).as_euler('xyz',degrees=True)*[-1,-1,1]).tolist());bs.append(spec);bones[bone]=spec;new_specs.append(spec);names.append(bone);digit_source[source_name]=bone
    bind=model_matrix(bones,bone,cache);rest_matrices[bone]=bind
    record=copy.deepcopy(h['digits'][digit]['joints'][i]);record.update(name=bone,head_bind=head.tolist(),tip_bind=tip.tolist(),length=float(np.linalg.norm(tip-head)),rest_flex_degrees=0)
    records.append(record);raw_joints[bone]=record;parent=bone
   c['hands'][side]['digits'][digit]['joints']=records
  palette=[hand]+names;weights=np.zeros((len(ids),len(palette)))
  for sn in hand_names:
   col=palette.index(digit_source.get(sn,hand))
   for original,w in mhw['weights'][sn]:
    if original in lookup:weights[lookup[original],col]+=w
  weights[:,0]+=np.maximum(0,1-weights.sum(1));weights/=weights.sum(1)[:,None]
  # Bake the actual neutralizing pose and its inverse bind as one operation.
  neutral_cache={};common_x=unit(np.cross(palm_normal,ty));common_z=unit(np.cross(common_x,ty));common=np.column_stack([common_x,ty,common_z])
  for spec in new_specs:
   bone=spec['name'];parent=spec['parent'];raw=raw_joints[bone];parent_m=neutral_cache[parent]if parent in neutral_cache else model_matrix(bones,parent,cache)
   if '_thumb_' in bone or '_cup_' in bone:q=R.from_euler('xyz',np.asarray(spec['rotation'])*[-1,-1,1],degrees=True)
   else:q=R.from_matrix(parent_m[:3,:3].T@common)if bone.endswith('_1')else R.identity()
   spec['rotation']=(q.as_euler('xyz',degrees=True)*[-1,-1,1]).tolist();pivot=np.asarray(spec['pivot'])*[-1,1,1]/16;m=np.eye(4);m[:3,:3]=q.as_matrix();m[:3,3]=pivot-m[:3,:3]@pivot;neutral_cache[bone]=parent_m@m
   deformation=neutral_cache[bone]@np.linalg.inv(rest_matrices[bone]);head=(deformation@np.r_[raw['head_bind'],1])[:3];tip=(deformation@np.r_[raw['tip_bind'],1])[:3]
   raw.update(head_bind=head.tolist(),tip_bind=tip.tolist(),local_bind_quaternion_xyzw=q.as_quat().tolist(),neutral_local_quaternion_xyzw=q.as_quat().tolist(),inverse_bind_column_major=np.linalg.inv(neutral_cache[bone]).T.reshape(-1).tolist(),angle_reference='Neutral pose baked together with the coherent source mesh and new inverse bind')
   c['new_bones'].append(copy.deepcopy(spec))
  matrices=[np.eye(4)]+[neutral_cache[n]@np.linalg.inv(rest_matrices[n])for n in names];fitted=dq_pose(fitted,weights,matrices);fitted,quads,weights=subdivide(fitted,faces,weights)
  triangles=np.asarray([tri for f in quads for tri in [[f[0],f[1],f[2]],[f[0],f[2],f[3]]]])
  # Both source/target frames are proper; anatomical right is the mirrored
  # left surface in the source-to-target frame, not a runtime negative scale.
  normals=np.zeros_like(fitted)
  for tri in triangles:
   normal=np.cross(fitted[tri[1]]-fitted[tri[0]],fitted[tri[2]]-fitted[tri[0]])
   for j in tri:normals[j]+=normal
  normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12);packed=[];skin=[];pivot=np.asarray(bones[hand]['pivot']);tex=np.asarray(game['parts']['finger_middle_'+side]['vertices'][3:5])
  for tri in triangles:
   for j in tri:packed.extend([*(fitted[j]*[-1,1,1]*16-pivot),*tex,*(normals[j]*[-1,1,1])]);skin.append(weights[j])
  # A closed dorsal shell follows this actual hand surface. Do not retain
  # disconnected fragments from the old palm mask around the new glove.
  chosen=[]
  for face in quads:
   centre=fitted[face].mean(0);along=(centre-wrist)@ty
   if np.mean(weights[face,0])<.72 or not .025<along<target_palm_length*.94:continue
   if normals[face].mean(0)@palm_normal>-.55:continue
   chosen.append(face)
  border=collections.Counter(tuple(sorted((x,y)))for f in chosen for x,y in zip(f,f[1:]+f[:1]));armour_uv=np.asarray(game['parts']['finger_thumb_'+side]['vertices'][3:5]);rigid=np.eye(len(palette))[0]
  def shell_triangle(points):
   normal=unit(np.cross(points[1]-points[0],points[2]-points[0]))
   for point in points:packed.extend([*(point*[-1,1,1]*16-pivot),*armour_uv,*(normal*[-1,1,1])]);skin.append(rigid)
  for face in chosen:
   upper=fitted[face]+normals[face]*.024;lower=fitted[face]+normals[face]*.007
   for i in [1,2]:shell_triangle([upper[0],upper[i],upper[i+1]]);shell_triangle([lower[0],lower[i+1],lower[i]])
   for k,(x,y)in enumerate(zip(face,face[1:]+face[:1])):
    if border[tuple(sorted((x,y)))]!=1:continue
    kk=(k+1)%4;shell_triangle([lower[k],lower[kk],upper[kk]]);shell_triangle([lower[k],upper[kk],upper[k]])
  skin=np.asarray(skin);out['parts'][hand]=dict(pivot=pivot.tolist(),vertices=np.round(packed,7).tolist());out['jointSkins'][hand]=dict(influences={n:np.round(skin[:,i],7).tolist()for i,n in enumerate(palette)},inverseBindColumnMajor={n:(np.linalg.inv(neutral_cache[n])if n in neutral_cache else np.linalg.inv(model_matrix(bones,n,cache))).T.reshape(-1).tolist()for n in palette})
  cache.clear();audit.append(dict(side=side,palm_longitudinal_scale=palm_scale,finger_longitudinal_scale=finger_scale,radial_scale=radial,source_quads=len(faces),neutral_mesh_and_bind_baked_together=True,legacy_palm_frame_misalignment_degrees=float(np.degrees(np.arccos(np.clip(palm_normal@old_normal,-1,1)))),new_normal_dot_knuckle_axis=float(palm_normal@tx)))
 for pose in c['pose_controls'].values():pose.pop('bone_angles',None)
 c['schema']='projectseele.anatomical-hands.r45.v2'if a.palm_cup else'projectseele.anatomical-hands.r45.v1'
 if a.palm_cup:
  for pose_name,pose in c['pose_controls'].items():
   ring,little=(10,18)if pose_name=='fist'else(6,12)if pose_name in ['knife','grab','rifle_right']else(2,4)if pose_name in ['relaxed','rifle_left']else(0,0)
   pose['cup_ring']=[ring];pose['cup_little']=[little]
 c.pop('thumb_opposition_solver',None);c['construction']=dict(method='Single monotonic fit of complete CC0 topology, then DQ neutral-pose bake with a newly authored rig',audit=audit,dorsal_armour='Closed shell fitted to actual dorsal palm; TV-style coverage, original EVA palette; no floating legacy mask pieces',visual_passed=False)
 (a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8');(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(out,separators=(',',':')),'utf8');(a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8');print(json.dumps(audit))

if __name__=='__main__':main()
