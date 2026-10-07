"""Review the editable original marine mesh and its real Blender armature."""
from pathlib import Path
import bpy,math,json
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
out=root/'artifacts/rebuild_r50/gaghiel_review';out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'artifacts/rebuild_r49/gaghiel_model/gaghiel_r49.blend'))
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=1000;scene.render.resolution_y=750;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Review background');scene.world.color=(.18,.18,.2)
bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=135
centre=Vector((0,5,1));cam.location=(-100,-125,90);cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler()
for loc,power in[((-80,-80,110),180000),((80,25,80),120000)]:
    bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=70;light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler()
rig=bpy.data.objects.get('Gaghiel rig')
for state in('closed','open'):
    jaw=rig.pose.bones['jaw_lower'];jaw.rotation_mode='QUATERNION'
    # The bone's local axes differ from mesh world axes; rotate in armature space.
    from mathutils import Matrix
    rest=jaw.bone.matrix_local
    jaw.matrix_basis=rest.inverted()@Matrix.Translation(rest.translation)@Matrix.Rotation(1.05 if state=='open'else 0,4,'X')@Matrix.Translation(-rest.translation)@rest
    scene.render.filepath=str(out/(state+'.png'));bpy.ops.render.render(write_still=True)
(out/'report.json').write_text(json.dumps(dict(source='Original editable Gaghiel mesh; closed and actual rig jaw review',native=False,user_accepted=False),indent=2),'utf8')
