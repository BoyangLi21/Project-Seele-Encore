"""Neutral, fixed-camera checks of the saved and reimported body; CPU only."""
from pathlib import Path
import json,sys,argparse
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/world_combat_r40/body_lab'
parser=argparse.ArgumentParser();parser.add_argument('--lab',type=Path,default=OUT)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.lab.resolve()
bpy.ops.wm.open_mainfile(filepath=str(OUT/'unit01_reimport.blend'))
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED'
scene.render.threads=2
scene.render.resolution_x=720
scene.render.resolution_y=800
scene.render.resolution_percentage=100
scene.world.color=(.4,.4,.4)
bpy.ops.mesh.primitive_plane_add(size=350,location=(0,0,-.1))
ground=bpy.context.object
mat=bpy.data.materials.new('Diagnostic floor')
mat.diffuse_color=(.16,.18,.2,1)
ground.data.materials.append(mat)
for loc,power,size in [((-40,75,105),65000,65),((65,-35,65),38000,55)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    light=bpy.context.object;light.data.energy=power;light.data.size=size
    light.rotation_euler=(Vector((0,0,28))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add()
cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=75;scene.camera=cam
arm=next(o for o in scene.objects if o.type=='ARMATURE')
views=[('neutral_front','neutral',1,(0,140,28)),('neutral_back','neutral',1,(0,-140,28)),
       ('hip_left_90_side','hip_l_x90',1,(-140,0,28)),('hip_right_90_front','hip_r_x90',1,(0,140,28)),
       ('jab_contact_front','r32_jab',46,(0,140,28)),('jab_contact_side','r32_jab',46,(-140,0,28)),
       ('cross_contact','r32_cross',46,(-90,140,28)),('heavy_contact','r32_heavy',56,(-90,140,28))]
for file,clip,frame,offset in views:
    # Reimport actions are .001 because the old datablocks are retained for
    # provenance. Resolve the one actually assigned to this armature by name.
    action=next(a for a in reversed(list(bpy.data.actions)) if a.name.startswith('EVA::'+clip) and a.name.split('.')[0]=='EVA::'+clip)
    arm.animation_data.action=action;scene.frame_set(frame);bpy.context.view_layer.update()
    target=Vector((0,0,28));cam.location=Vector(offset)
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(file+'.png'))
    bpy.ops.render.render(write_still=True)
(OUT/'views.json').write_text(json.dumps(views,indent=2))
