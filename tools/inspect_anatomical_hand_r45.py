"""Editable new-rig review with named anatomical poses; stills only, no video."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--textured',action='store_true');p.add_argument('--poses',default='');p.add_argument('--view',choices=['front','back','three-quarter'],default='three-quarter');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);candidate=a.candidate.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
contract=json.loads((candidate/'hand_rig_contract.json').read_text());rig_id=contract['rig'];name=f'eva_unit0{rig_id}';data=json.loads((candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text());geo=json.loads((candidate/(name+'.geo.json')).read_text());bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};cache={};AX=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);C=np.eye(4);C[:3,:3]=AX
def bind(n):
 if n in cache:return cache[n].copy()
 b=bones[n];v=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);x,y,z=np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1]);q=Matrix.Rotation(float(z),4,'Z')@Matrix.Rotation(float(y),4,'Y')@Matrix.Rotation(float(x),4,'X');m=Matrix.Translation(v)@q@Matrix.Translation(-v)
 if b.get('parent'):m=bind(b['parent'])@m
 cache[n]=m.copy();return m
def converted(m):
 # Convert the world frame while retaining bone-local anatomical controls.
 x=C@np.asarray(m);x[:3,3]*=5;return Matrix(x)
records=[]
for side in ['l','r']:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';arm=bpy.data.armatures.new('EVA anatomical hand');obj=bpy.data.objects.new('EVA anatomical hand '+side,arm);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
 selected=[n for n in data['parts']if n=='hand_'+side or n.startswith('r45_hand_'+side+'_')]
 palette=sorted(set(n for part in selected for n in data['jointSkins'][part]['influences']));required=set(palette)
 for n in list(palette):
  parent=bones[n].get('parent')
  while parent:required.add(parent);parent=bones[parent].get('parent')
 for n in required:
  b=bones[n];v=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);m=converted(bind(n)@Matrix.Translation(v));length=next((j['length']*5 for d in contract['hands'][side]['digits'].values() for j in d['joints'] if j['name']==n),.35);eb=arm.edit_bones.new(n);eb.head=m.translation;eb.tail=eb.head+m.to_3x3().col[1]*length;eb.matrix=m;eb.length=length
 for n in required:
  parent=bones[n].get('parent')
  if parent in required:arm.edit_bones[n].parent=arm.edit_bones[parent]
 bpy.ops.object.mode_set(mode='OBJECT');obj.show_in_front=True
 for digit,d in contract['hands'][side]['digits'].items():
  for j in d['joints']:
   pb=obj.pose.bones[j['name']];pb.rotation_mode='XYZ';limit=pb.constraints.new('LIMIT_ROTATION');limit.owner_space='LOCAL';limit.use_transform_limit=True;lim=j['anatomical_limits_degrees'];ranges=[[j['rest_flex_degrees']-lim[0][1],j['rest_flex_degrees']-lim[0][0]],lim[1],lim[2]]
   if 'neutral_local_quaternion_xyzw'in j:
    neutral=np.asarray(j['neutral_local_quaternion_xyzw']);rest=np.asarray(j['local_bind_quaternion_xyzw']);same_bind=abs(float(neutral@rest))>1-1e-7;limit.mute=not same_bind;pb['anatomical_limits_degrees']=str(lim);pb['control_basis']='Local X flexion, Y opposition twist, Z splay; native limits active'if same_bind else'Neutral differs from authored bind; clamp anatomical controls before converting to pose quaternion'
   if side=='r':ranges[1]=[-ranges[1][1],-ranges[1][0]];ranges[2]=[-ranges[2][1],-ranges[2][0]]
   for axis,(lo,hi)in zip('xyz',ranges):setattr(limit,'use_limit_'+axis,True);setattr(limit,'min_'+axis,float(np.radians(lo)));setattr(limit,'max_'+axis,float(np.radians(hi)))
 surfaces=[]
 for part_name in selected:
  part=data['parts'][part_name];raw=np.asarray(part['vertices']).reshape(-1,8);points=((raw[:,:3]+part['pivot'])*[-1,1,1]/16)@AX.T*5
  keys=np.round(np.c_[points,raw[:,5:8]],6);_,unique_indices,inverse=np.unique(keys,axis=0,return_index=True,return_inverse=True)
  mesh=bpy.data.meshes.new(part_name);mesh.from_pydata(points[unique_indices].tolist(),[],inverse.reshape(-1,3).tolist());mesh.update();surface=bpy.data.objects.new(part_name,mesh);bpy.context.collection.objects.link(surface);surface.parent=obj;surfaces.append(surface)
  for n,weights in data['jointSkins'][part_name]['influences'].items():
   g=surface.vertex_groups.new(name=n);w=np.asarray(weights)[unique_indices]
   for weight in np.unique(w):
    if weight>1e-8:g.add(np.flatnonzero(w==weight).tolist(),float(weight),'REPLACE')
  mod=surface.modifiers.new('Original source skin','ARMATURE');mod.object=obj;mod.use_deform_preserve_volume=True
  mat=bpy.data.materials.new(part_name);mat.diffuse_color=(.025,.022,.036,1)if part.get('surface_role','').startswith('flexible')else(.26,.13,.48,1);mesh.materials.append(mat)
  if a.textured:
   uv=mesh.uv_layers.new(name='Original atlas');normals=(raw[unique_indices,5:8]*[-1,1,1])@AX.T
   for loop in mesh.loops:uv.data[loop.index].uv=(raw[loop.index,3],1-raw[loop.index,4])
   for face in mesh.polygons:face.use_smooth=True
   mesh.normals_split_custom_set_from_vertices(normals.tolist());mat.use_nodes=True;node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(Path(__file__).resolve().parents[1]/f'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity/{name}.png'),check_existing=True);bs=mat.node_tree.nodes.get('Principled BSDF');mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.42;bs.inputs['Alpha'].default_value=1
 cam=bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.world=bpy.data.worlds.new('Neutral world');scene.world.color=(.10,.12,.15);scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100
 for pose_name,pose in contract['pose_controls'].items():
  if a.poses and pose_name not in a.poses.split(','):continue
  deltas={};desired_local={}
  for digit,d in contract['hands'][side]['digits'].items():
   for i,j in enumerate(d['joints']):
    if j['name']in pose.get('bone_angles',{}):values=pose['bone_angles'][j['name']]
    elif pose.get('source_rest'):values=[j['rest_flex_degrees'],0,0]
    elif digit=='thumb':values=pose['thumb'][i]
    else:values=[pose.get(digit,pose['fingers'])[i],0,pose.get('splay',{}).get(digit,0)if i==0 else 0]
    values=np.asarray(values,dtype=float);lim=np.asarray(j['anatomical_limits_degrees']);values=np.clip(values,lim[:,0],lim[:,1]);mirror=1 if side=='l'else -1;delta=[j['rest_flex_degrees']-values[0],values[1]*mirror,values[2]*mirror];pb=obj.pose.bones[j['name']]
    if 'neutral_local_quaternion_xyzw'in j:
     delta[0]=-values[0];x,y,z=np.radians(delta);dmat=Matrix.Rotation(float(z),4,'Z')@Matrix.Rotation(float(y),4,'Y')@Matrix.Rotation(float(x),4,'X');q=j['neutral_local_quaternion_xyzw'];neutral=Quaternion((q[3],q[0],q[1],q[2]));desired=neutral.to_matrix().to_4x4()@dmat;q=j['local_bind_quaternion_xyzw'];rest=Quaternion((q[3],q[0],q[1],q[2]));pb.rotation_mode='QUATERNION';pb.rotation_quaternion=rest.inverted()@desired.to_quaternion();desired_local[j['name']]=desired
    else:pb.rotation_euler=np.radians(delta)
    deltas[j['name']]=np.radians(delta)
  bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();allpoints=[]
  actual=obj.evaluated_get(deps);expected_cache={}
  def native_pose(n):
   if n in expected_cache:return expected_cache[n]
   b=bones[n];v=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);x,y,z=np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1]);rotation=Matrix.Rotation(float(z),4,'Z')@Matrix.Rotation(float(y),4,'Y')@Matrix.Rotation(float(x),4,'X')
   if n in desired_local:rotation=desired_local[n]
   elif n in deltas:
    x,y,z=deltas[n];rotation=rotation@Matrix.Rotation(float(z),4,'Z')@Matrix.Rotation(float(y),4,'Y')@Matrix.Rotation(float(x),4,'X')
   m=Matrix.Translation(v)@rotation@Matrix.Translation(-v)
   if b.get('parent'):m=native_pose(b['parent'])@m
   expected_cache[n]=m;return m
  max_joint_error=0;max_rotation_error=0
  for n in deltas:
   v=Vector(np.asarray(bones[n]['pivot'])*[-1,1,1]/16);expected=converted(native_pose(n)@Matrix.Translation(v));max_joint_error=max(max_joint_error,(actual.pose.bones[n].matrix.translation-expected.translation).length);max_rotation_error=max(max_rotation_error,float(np.abs(np.asarray(actual.pose.bones[n].matrix.to_3x3())-np.asarray(expected.to_3x3())).max()))
  assert max_joint_error<.0001,('Native/Blender posed-joint parity',side,pose_name,max_joint_error)
  assert max_rotation_error<.0001,('Native/Blender local-axis parity',side,pose_name,max_rotation_error)
  for surface in surfaces:
   ev=surface.evaluated_get(deps);m=ev.to_mesh();allpoints.extend(v.co[:]for v in m.vertices);ev.to_mesh_clear()
  ps=np.asarray(allpoints);centre=Vector((ps.min(0)+ps.max(0))*.5);span=float(np.ptp(ps,axis=0).max());normal=Vector(np.asarray(contract['hands'][side]['palmar_normal_bind'])@AX.T);up=-Vector(np.asarray(contract['hands'][side]['longitudinal_bind'])@AX.T)
  view=normal if a.view=='front' else -normal if a.view=='back' else (normal+normal.cross(up)*.35+up*.15).normalized()
  cam.location=centre+view*span*3;right=up.cross(view).normalized();camera_up=view.cross(right).normalized();cam.rotation_euler=Matrix((right,camera_up,view)).transposed().to_euler();cam.data.ortho_scale=span*1.4
  if a.textured:
   scene.render.engine='BLENDER_EEVEE';scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.15,.18,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
   for i,direction in enumerate([normal+Vector((-.3,-.3,1)),normal*-1+Vector((.4,1,.6))]):
    light=bpy.data.objects.get('Studio'+str(i))
    if light is None:light=bpy.data.objects.new('Studio'+str(i),bpy.data.lights.new('Studio'+str(i),'AREA'));bpy.context.collection.objects.link(light)
    light.location=centre+direction.normalized()*span*2;light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler();light.data.energy=1600 if i==0 else 1000;light.data.shape='DISK';light.data.size=span*2
  path=a.out/f'{side}_{pose_name}.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);records.append(dict(side=side,pose=pose_name,file=str(path),finite=bool(np.isfinite(ps).all()),native_blender_joint_error_world_blocks=max_joint_error,native_blender_rotation_error=max_rotation_error,artist_passed=False))
 bpy.ops.wm.save_as_mainfile(filepath=str(a.out/f'new_anatomical_hand_{side}.blend'))
(a.out/'pose_review.json').write_text(json.dumps(records,indent=2),'utf8');print('New-rig original surface poses generated; no animation/video')
