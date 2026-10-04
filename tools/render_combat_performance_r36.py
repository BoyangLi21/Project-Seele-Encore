"""Blender rendering of exported real mesh poses, not an in-game screenshot."""
import bpy,json,numpy as np,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=8;scene.cycles.use_denoising=True
scene.render.resolution_x=600;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.world.color=(.5,.5,.5)
materials={}
for spec in json.loads((OUT/'manifest.json').read_text()):
    name=spec['model']
    if name in materials:continue
    mat=bpy.data.materials.new(name);mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();shader=nodes.new('ShaderNodeBsdfPrincipled');output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface']);shader.inputs['Roughness'].default_value=.6
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity/{name}.png'))
    color=nodes.new('ShaderNodeVertexColor');color.layer_name='tint';multiply=nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
    mat.node_tree.links.new(tex.outputs['Color'],multiply.inputs[1]);mat.node_tree.links.new(color.outputs['Color'],multiply.inputs[2]);mat.node_tree.links.new(multiply.outputs[0],shader.inputs['Base Color']);materials[name]=mat
bpy.ops.mesh.primitive_plane_add(size=350,location=(0,0,-.04));floor=bpy.context.object;mat=bpy.data.materials.new('floor');mat.diffuse_color=(.23,.25,.28,1);floor.data.materials.append(mat)
for loc,power,size in [((-40,75,105),60000,70),((60,-25,65),42000,60)]:
    bpy.ops.object.light_add(type='AREA',location=loc);lamp=bpy.context.object;lamp.data.energy=power;lamp.data.size=size;lamp.rotation_euler=(Vector((0,0,28))-lamp.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
for spec in json.loads((OUT/'manifest.json').read_text()):
    target=Vector(spec['camera_target']);cam.location=target+Vector(spec['camera_offset']);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=spec['scale']
    data=np.load(OUT/(spec['file']+'.npz'));v=data['vertices'][:,[0,2,1]]*[1,-1,1];me=bpy.data.meshes.new('body');me.from_pydata(v,[],np.arange(len(v)).reshape(-1,3));me.update()
    uv=me.uv_layers.new();values=data['uv'].copy();values[:,1]=1-values[:,1];uv.data.foreach_set('uv',values.ravel());me.materials.append(materials[spec['model']]);obj=bpy.data.objects.new('body',me);bpy.context.collection.objects.link(obj)
    color=me.color_attributes.new(name='tint',type='FLOAT_COLOR',domain='CORNER');color.data.foreach_set('color',(data['colors'] if 'colors' in data else np.ones((len(v),4))).ravel())
    weapon=None
    if 'weapon_vertices'in data:
        w=data['weapon_vertices'][:,[0,2,1]]*[1,-1,1];wm=bpy.data.meshes.new('weapon');wm.from_pydata(w,[],np.arange(len(w)).reshape(-1,3));wm.update()
        weapon=bpy.data.objects.new('weapon',wm);bpy.context.collection.objects.link(weapon);steel=bpy.data.materials.get('Review steel')or bpy.data.materials.new('Review steel');steel.diffuse_color=(.28,.30,.34,1);wm.materials.append(steel)
    scene.render.filepath=str(OUT/(spec['file']+'.png'));bpy.ops.render.render(write_still=True);bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me)
    if weapon is not None:bpy.data.objects.remove(weapon,do_unlink=True);bpy.data.meshes.remove(wm)
