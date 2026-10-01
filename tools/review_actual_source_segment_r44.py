"""Full original-source FK playback. Joint tubes are visualization, not skin."""
from pathlib import Path
import argparse,json,sys
import bpy
from mathutils import Vector

ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--segment',required=True)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);args.raw=args.raw.resolve();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=True);folder=args.out/'frames';folder.mkdir(exist_ok=True)
fixture=json.loads((args.raw/'fixture.json').read_text('utf8'));card=fixture['source_motion_card'];segment=next(s for s in card['segments']if s['label']==args.segment)
source=bpy.data.objects['ACCAD_continuous_original'];source.hide_render=True
for obj in list(bpy.data.objects):
    if obj!=source:bpy.data.objects.remove(obj,do_unlink=True)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=2;scene.cycles.max_bounces=1
scene.cycles.diffuse_bounces=1;scene.cycles.glossy_bounces=0;scene.cycles.transmission_bounces=0;scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.use_persistent_data=True;scene.render.resolution_x=480;scene.render.resolution_y=320;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.world.color=(.16,.16,.16)
def material(name,color):
    mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);return mat
grey=material('Source axial skeleton',(.45,.48,.52));left=material('Source left joints',(.13,.65,.85));right=material('Source right joints',(.92,.39,.13));floor_mat=material('Source floor',(.27,.29,.32))
joints={};links={}
for bone in source.data.bones:
    color=left if bone.name.startswith('Left')else right if bone.name.startswith('Right')else grey
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=5,radius=.085 if bone.name=='Head'else .028)
    sphere=bpy.context.object;sphere.name='Original joint '+bone.name;sphere.data.materials.append(color);joints[bone.name]=sphere
    if bone.parent:
        bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.023,depth=1)
        cylinder=bpy.context.object;cylinder.name='Original chain '+bone.name;cylinder.data.materials.append(color);links[bone.name]=cylinder
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.002));bpy.context.object.data.materials.append(floor_mat)
cam_data=bpy.data.cameras.new('Original source fixed direction');camera=bpy.data.objects.new('Original source fixed direction',cam_data);bpy.context.collection.objects.link(camera);scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=3.6
light_data=bpy.data.lights.new('Source area','AREA');light_data.energy=500;light_data.size=5
light=bpy.data.objects.new('Source area',light_data);bpy.context.collection.objects.link(light)
rows=[];first,last=segment['candidate_frames']
for index,frame in enumerate(range(first,last+1),1):
    scene.frame_set(frame);bpy.context.view_layer.update();rig=source.evaluated_get(bpy.context.evaluated_depsgraph_get());positions={n:source.matrix_world@rig.pose.bones[n].head for n in joints}
    for n,obj in joints.items():obj.location=positions[n]
    for n,obj in links.items():
        a=positions[source.data.bones[n].parent.name];b=positions[n];delta=b-a;obj.hide_render=delta.length<.001
        obj.location=(a+b)*.5;obj.scale.z=max(.001,delta.length);obj.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
    centre=Vector(tuple((min(v[i]for v in positions.values())+max(v[i]for v in positions.values()))*.5 for i in range(3)))
    camera.location=centre+Vector((3,-6,2.3));camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler()
    light.location=centre+Vector((0,-2,4));light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(folder/f'{index:04d}.png');bpy.ops.render.render(write_still=True)
    rows.append(dict(render_index=index,raw_scene_frame=frame,original_take_frame=segment['source_frame_range'][0]+index-1,seconds=(index-1)/30,
                     actual_joint_centres={n:list(v)for n,v in positions.items()}))
    print('Actual original source frame',index,'/',last-first+1,flush=True)
(args.out/'source_segment_receipt.json').write_text(json.dumps(dict(segment=segment,frames=rows,source_scene=str(args.raw/'rokoko_continuous_legs_r44.blend'),
    fps=30,playback_speed=1,actor_repositioned=False,camera='Fixed direction/scale, tracks actual whole joint AABB',
    representation='Actual source joint FK, drawn as colored joint tubes; no captured human mesh/skin exists',quality='Source motion review only; captured angles and contacts are not automatically suitable or accepted for EVA'),indent=2),'utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'actual_source_segment_review.blend'))
