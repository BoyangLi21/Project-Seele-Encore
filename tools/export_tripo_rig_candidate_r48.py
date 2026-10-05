"""Build an editable armature on the unchanged supplied LOD surface."""
from pathlib import Path
import sys,json,bpy,numpy as np
from mathutils import Vector,Matrix

ROOT=Path(__file__).resolve().parents[1]
name=sys.argv[sys.argv.index('--')+1];folder=ROOT/'artifacts/rebuild_r48/tripo_pipeline'/name
land=json.loads((folder/'rig_candidate/rig_landmarks.json').read_text());skin=json.loads((folder/'rig_candidate/smoothed_skin.json').read_text())
specs={b['name']:b for b in land['bones']};segments={b['bone']:b for b in land['segments']}
def point(v):return Vector((-v[0],v[2],v[1]))
bpy.ops.wm.open_mainfile(filepath=str(folder/'lod0.blend'))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.armature_add();arm=bpy.context.object;arm.name='EVA_'+name.upper()+'_measured_R48'
bpy.ops.object.mode_set(mode='EDIT');arm.data.edit_bones.remove(arm.data.edit_bones[0])
for bone_name in skin['bones']:
    bone=arm.data.edit_bones.new(bone_name)
    if bone_name in specs:
        s=specs[bone_name];p=s['pivot'];end=segments[bone_name]['end']if bone_name in segments else specs['torso_lower']['pivot']
    else:
        parent=bone_name[:-4];p=segments[parent]['end'];end=np.array(p)+[0,.002,0]
    bone.head=point(p);bone.tail=point(end)
    if (bone.tail-bone.head).length<1e-5:bone.tail=bone.head+Vector((0,0,.002))
for bone_name in skin['bones']:
    parent=specs[bone_name]['parent']if bone_name in specs else bone_name[:-4]
    if parent:arm.data.edit_bones[bone_name].parent=arm.data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT');arm.show_in_front=True
ids=np.array(skin['skin_indices']).reshape(-1,4);weights=np.array(skin['skin_weights']).reshape(-1,4)
assert len(ids)==len(mesh.data.vertices)
for index,bone_name in enumerate(skin['bones']):
    mask=ids==index;per_vertex=np.sum(np.where(mask,weights,0),axis=1);active=np.flatnonzero(per_vertex>1e-6)
    if not len(active):continue
    group=mesh.vertex_groups.new(name=bone_name)
    for value in np.unique(per_vertex[active]):group.add(np.flatnonzero(per_vertex==value).tolist(),float(value),'REPLACE')
modifier=mesh.modifiers.new('Measured skeleton deformation','ARMATURE');modifier.object=arm;modifier.use_deform_preserve_volume=True
original_world=mesh.matrix_world.copy();mesh.parent=arm;mesh.matrix_world=original_world
arm['source']='Owner supplied GLB; source surface and UV preserved';arm['skinning']='Measured segment assignment + Mesh2Motion MIT solvers, pinned 79f3f61';arm['status']='candidate; not yet installed or motion-accepted'
out=folder/'rig_candidate';bpy.ops.wm.save_as_mainfile(filepath=str(out/'editable_rig.blend'))
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(out/'rigged_candidate.glb'),export_format='GLB',use_selection=True,export_animations=False)

# A finite actual-mesh articulation check, not a fake gameplay preview.
world=bpy.data.worlds.new('Rig review');world.use_nodes=True
background=next((n for n in world.node_tree.nodes if n.type=='BACKGROUND'),None)or world.node_tree.nodes.new('ShaderNodeBackground')
output=next((n for n in world.node_tree.nodes if n.type=='OUTPUT_WORLD'),None)or world.node_tree.nodes.new('ShaderNodeOutputWorld')
world.node_tree.links.new(background.outputs[0],output.inputs[0]);background.inputs[1].default_value=.65;bpy.context.scene.world=world
target=Vector((0,0,.50))
for loc in [(2,-3,3),(-2,-1,2),(1,3,2)]:
    bpy.ops.object.light_add(type='AREA',location=loc);lamp=bpy.context.object;lamp.data.energy=160;lamp.data.size=3;lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(1.8,-3.5,1));camera=bpy.context.object;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=1.23;bpy.context.scene.camera=camera
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=850;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
fist={}
calibration_file=folder/'rig_candidate/fist_calibration.json'
calibrated=json.loads(calibration_file.read_text())['angles']if calibration_file.exists()else None
for side,sign in [('r',-1),('l',1)]:
    for digit in ('index','middle','ring','little'):
        keys=['finger_'+digit+(''if j==0 else '_tip'if j==1 else '_distal')+'_'+side for j in range(3)]
        previous=0
        for joint,key in enumerate(keys):
            neutral=np.array(segments[key]['end'])-segments[key]['start']
            desired=[(.985*sign,-.174),(.342*sign,.940),(-.714*sign,.700)][joint]
            cumulative=(np.arctan2(desired[1],desired[0])-np.arctan2(neutral[1],neutral[0])+np.pi)%(2*np.pi)-np.pi
            angle=(cumulative-previous+np.pi)%(2*np.pi)-np.pi;previous+=angle
            key='finger_'+digit+(''if joint==0 else '_tip'if joint==1 else '_distal')+'_'+side
            fist[key]=(0,0,float(angle))
            if calibrated:fist[key]=(0,0,float(np.deg2rad(calibrated[side][digit][joint])))
    for joint,angle in enumerate((-20,40,20)):
        key='finger_thumb'+(''if joint==0 else '_tip'if joint==1 else '_distal')+'_'+side
        fist[key]=(0,float(np.deg2rad(-sign*70 if joint==0 else 0)),float(np.deg2rad(-sign*angle)))
views=[('rest',{}),('joint_probe',{'forearm_r':(1.2,0,0),'shin_l':(-1.0,0,0),'arm_r':(-.55,0,0)})]
if '--fist-only' in sys.argv:
    views=[('fist_detail',fist)]
    hand_x=-.19 if name=='un00'else-.218
    target=Vector((hand_x,-.060,.446));camera.location=(hand_x-.22,-1.0,.49)
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=.18
for label,rotations in views:
    matrices={}
    def evaluate(key):
        if key in matrices:return matrices[key]
        parent=specs[key]['parent']if key in specs else key[:-4]
        p=point(specs[key]['pivot']if key in specs else segments[parent]['end'])
        x,y,z=rotations.get(key,(0,0,0))
        # Native XYZ -> Blender (-X,Z,Y), all rotations around measured world pivots.
        rot=Matrix.Rotation(y,4,'Z')@Matrix.Rotation(z,4,'Y')@Matrix.Rotation(-x,4,'X')
        delta=Matrix.Translation(p)@rot@Matrix.Translation(-p)
        matrices[key]=(evaluate(parent)@delta)if parent else delta
        return matrices[key]
    for bone in arm.pose.bones:
        parent=specs[bone.name]['parent']if bone.name in specs else bone.name[:-4]
        parent_delta=evaluate(parent)if parent else Matrix.Identity(4)
        # Assign local bases together. Setting evaluated world matrices one
        # after another reads stale parents and applies parent motion twice.
        bone.matrix_basis=bone.bone.matrix_local.inverted()@parent_delta.inverted()@evaluate(bone.name)@bone.bone.matrix_local
    bpy.context.view_layer.update();scene.render.filepath=str(out/(label+'.png'));bpy.ops.render.render(write_still=True)
print(name,'editable rig exported; diagnostic articulation needs visual review',flush=True)
