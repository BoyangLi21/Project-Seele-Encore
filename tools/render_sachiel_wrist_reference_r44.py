"""Actual neutral wrist surface and existing sparse binding, before editing."""
from pathlib import Path
import argparse,json,sys
import bpy
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--vertex',type=int,default=11388);ap.add_argument('--elbow',action='store_true');ap.add_argument('--shoulder',action='store_true');ap.add_argument('--hip',action='store_true');ap.add_argument('--ankle',action='store_true');ap.add_argument('--side',choices=('l','r'),default='l');args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[])
out=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region'/('hip_actual_active_reference'if args.hip else'ankle_actual_active_reference'if args.ankle else'shoulder_actual_reference'if args.shoulder else'elbow_front_actual_reference'if args.elbow else'wrist_actual_reference')
out.mkdir(exist_ok=True)
actor=json.loads((out.parents[1]/'fixture.json').read_text('utf8'))['actors'][1]
for obj in bpy.data.objects:
    if obj.name.startswith('eva_unit01')or'preview'in obj.name:obj.hide_render=True
rig=bpy.data.objects['sachiel_DEFORM'];rig.animation_data_clear()
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
mesh=bpy.data.objects['sachiel_actual_mesh'];mesh.hide_render=False
red=bpy.data.materials.new('Actual problematic wrist vertex');red.diffuse_color=(1,.04,.01,1)
green=bpy.data.materials.new('Actual hand pivot');green.diffuse_color=(.02,1,.08,1)
point=Vector(actor['vertices'][args.vertex]);pivot=Vector(actor['joints']['leg_'+args.side]['upper']if args.hip else actor['joints']['leg_'+args.side]['end']if args.ankle else actor['joints']['arm_'+args.side]['upper']if args.shoulder else actor['joints']['arm_'+args.side]['joint']if args.elbow else actor['hands'][args.side]['pivot'])
for position,mat in((point,red),(pivot,green)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.28,location=position);bpy.context.object.data.materials.append(mat)
scene=bpy.context.scene;camera=scene.camera;centre=(point+pivot)*.5
camera.location=centre+Vector((20 if args.side=='r'else-20,22,14));camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=19
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4;scene.cycles.max_bounces=1
scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=720;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.filepath=str(out/f'actual_neutral_joint_{args.vertex}.png');bpy.context.view_layer.update();bpy.ops.render.render(write_still=True)
(out/'actual_neutral_wrist_reference.json').write_text(json.dumps(dict(vertex=args.vertex,neutral_point=list(point),actual_joint_pivot=list(pivot),offset_from_joint_pivot=list(point-pivot),
    source='Actual saved counter_v13 neutral mesh, no altered pose or binding',quality='Anatomical region reference; not acceptance'),indent=2),'utf8')
