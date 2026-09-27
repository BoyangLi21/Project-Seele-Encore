"""Editable Blender shape-key source for the actual paired deformation bake."""
import bpy,numpy as np,json,sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_eva_motion_lab_3d import iter_action_fcurves
OUT=Path(sys.argv[sys.argv.index('--')+1]).resolve()
assert OUT.parent==ROOT/'artifacts/world_combat_r40'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=70
for role,name,filename in [('hero','eva_unit01','hero_frames.npz'),('angel','sachiel','surface_frames.npz')]:
    data=np.load(OUT/filename);positions=data['positions'][:,:,[0,2,1]]*[1,-1,1]
    faces=data['indices'].reshape(-1,3) if 'indices' in data else np.arange(positions.shape[1]).reshape(-1,3)
    me=bpy.data.meshes.new(name);me.from_pydata(positions[0],[],faces.tolist());me.update()
    uv=me.uv_layers.new(name='Original UV');coords=data['uv'].copy();coords[:,1]=1-coords[:,1];uv.data.foreach_set('uv',coords.ravel())
    obj=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(obj)
    material=bpy.data.materials.new(name);material.use_nodes=True;material.node_tree.nodes.clear()
    shader=material.node_tree.nodes.new('ShaderNodeBsdfPrincipled');output=material.node_tree.nodes.new('ShaderNodeOutputMaterial');material.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity'/(name+'.png')));tex.image.pack()
    material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color']);shader.inputs['Roughness'].default_value=.7;me.materials.append(material)
    obj.shape_key_add(name='Basis')
    for f,vertices in enumerate(positions):
        key=obj.shape_key_add(name=f'TV_wrap_{489+f:03d}');key.data.foreach_set('co',vertices.astype(np.float32).ravel())
        for frame,value in [(max(0,f),0),(f+1,1),(f+2,0)]:key.value=value;key.keyframe_insert('value',frame=frame)
    for curve in iter_action_fcurves(obj.data.shape_keys.animation_data.action):
        for point in curve.keyframe_points:point.interpolation='LINEAR'
    obj['source_movie']='first_battle_r24.json';obj['source_frames']='489..558 @30fps'
    obj['status']='Work in progress: paired contact and art review required'
    for poly in me.polygons:poly.use_smooth=True
text=bpy.data.texts.new('READ_ME');text.write('R40 actual private mesh bake. No generated concept image substitution.\nEach shape key is a sampled frame; edit or re-bake with bake_envelopment_candidate_r40.py.\nThe authoritative paired skeleton/cockpit markers are in the accompanying first_battle_r24.json.\nNot approved for installation.\n')
bpy.ops.mesh.primitive_plane_add(size=250,location=(0,-80,-.05));floor=bpy.context.object;floor.name='Bearing floor'
bpy.ops.object.camera_add(location=(-92,-159,58));camera=bpy.context.object;target=Vector((4,-78,34));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=110;scene.camera=camera
for loc,power in [((-60,-100,100),100000),((70,-70,70),70000)]:
    bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.data.energy=power;light.data.size=60;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=2
scene.frame_set(70);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paired_source.blend'))
print('Editable paired source saved',OUT/'paired_source.blend',flush=True)
