"""Mark the real neutral mesh vertices before judging their weight ownership."""
from pathlib import Path
import json,sys
import bpy,numpy as np
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region';OUT.mkdir(exist_ok=True)
data=json.loads((OUT.parent/'fixture.json').read_text('utf8'))['actors'][1]
for name in ('eva_unit01_actual_mesh','sachiel_export_first_slot_DQ_preview','sachiel_export_native_DQ_preview'):
    obj=bpy.data.objects.get(name)
    if obj:obj.hide_render=True
rig=bpy.data.objects['sachiel_DEFORM'];rig.animation_data_clear()
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
obj=bpy.data.objects['sachiel_actual_mesh'];obj.hide_render=False;obj.hide_set(False);rows=[]
red=bpy.data.materials.new('Marked actual neutral spike');red.diffuse_color=(1,.02,.01,1)
green=bpy.data.materials.new('Actual elbow socket');green.diffuse_color=(.02,1,.12,1)
for i,side in ((4184,'l'),(15592,'r')):
    point=Vector(data['vertices'][i]);joint=Vector(data['joints']['arm_'+side]['joint'])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.65,location=point);bpy.context.object.data.materials.append(red)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.55,location=joint);bpy.context.object.data.materials.append(green)
    rows.append(dict(vertex=i,neutral_point=list(point),actual_elbow_socket=list(joint),behind_elbow_blocks=float(joint.y-point.y),distance_to_elbow=float((joint-point).length),influences=[dict(bone=data['bones'][slot]['name'],weight=w)for slot,w in zip(data['influences'][i],data['weights'][i])],anatomical_observation='Point lies ~14.73 blocks behind the actual elbow socket and ~3.25 below it; elongated rear elbow spike, not a palm surface. Arm/forearm blend at this distant hard protrusion plus torso/hand minority influences require independent binding review. No binding edit inferred.'))
scene=bpy.context.scene;camera=scene.camera;camera.location=(95,-100,60);camera.rotation_euler=(Vector((0,-1,33))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=115;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=3;scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.cycles.max_bounces=1;scene.render.filepath=str(OUT/'neutral_elbow_spikes.png');bpy.context.view_layer.update();bpy.ops.render.render(write_still=True)
(OUT/'anatomical_weight_review.json').write_text(json.dumps(dict(rows=rows,quality='Neutral real mesh diagnostic; weight reasonableness not certified by bone names or nearest pivot alone.'),indent=2),'utf8');print('Saved actual neutral elbow-spike markers',flush=True)
