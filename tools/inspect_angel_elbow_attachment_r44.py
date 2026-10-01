"""Actually view the anatomical attachment base before enlarging a binding mask."""
from pathlib import Path
import json
import bpy
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/bind_region/base_boundary'
OUT.mkdir(exist_ok=True);fixture=json.loads((OUT.parent.parent/'fixture.json').read_text('utf8'))['actors'][1]
for obj in bpy.data.objects:
    if obj.name.startswith('eva_unit01') or 'preview' in obj.name:obj.hide_render=True
rig=bpy.data.objects['sachiel_DEFORM'];rig.animation_data_clear()
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
obj=bpy.data.objects['sachiel_actual_mesh'];obj.hide_render=False;rows=[]
for vertex,side in ((3305,'l'),(13745,'r')):
    point=Vector(fixture['vertices'][vertex]);joint=Vector(fixture['joints']['arm_'+side]['joint'])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.40,location=point)
    material=bpy.data.materials.new('Native same-pose remaining error '+str(vertex));material.diffuse_color=(1,.06,.1,1);bpy.context.object.data.materials.append(material)
    rows.append(dict(vertex=vertex,anatomical_side=side,neutral_point=list(point),actual_elbow_joint=list(joint),neutral_offset_from_elbow=list(point-joint),
                     original_weights=[dict(bone=fixture['bones'][index]['name'],weight=w) for index,w in zip(fixture['influences'][vertex],fixture['weights'][vertex])]))
scene=bpy.context.scene;camera=scene.camera;camera.animation_data_clear();camera.location=(72,-82,43)
camera.rotation_euler=(Vector((0,-4,37))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=62
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=3;scene.render.threads_mode='FIXED';scene.render.threads=2
scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.cycles.max_bounces=1
scene.render.filepath=str(OUT/'actual_neutral_elbow_base_3305_13745.png');bpy.context.view_layer.update();bpy.ops.render.render(write_still=True)
(OUT/'anatomical_attachment_points.json').write_text(json.dumps(dict(points=rows,scope='Actually viewed neutral real mesh; points lie on the posterior attachment base, not a hand. Soft/hard boundary still needs topology/surface confirmation.'),indent=2),'utf8')
