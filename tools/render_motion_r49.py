"""Render authoring surfaces from preview_motion_r49 in background Blender."""
from pathlib import Path
import json
import sys
import bpy
import numpy as np
from mathutils import Vector

folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
doc=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=750;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Authoring world')
scene.world.color=(.16,.16,.16)
materials={}
for role,name in [('hero','eva_unit01'),('angel','sachiel'),('weapon','progressive_knife'),('head','eva_unit01')]:
    mat=bpy.data.materials.new(role);mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.65
    image=mat.node_tree.nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(Path(doc['texture_root'])/(name+'.png')))
    mat.node_tree.links.new(image.outputs['Color'],shader.inputs['Base Color'])
    if role=='head':
        base=image
        image=mat.node_tree.nodes.new('ShaderNodeTexImage');image.name='EyeMask';image.image=bpy.data.images.load(str(Path(doc['texture_root'])/'eva_unit01_eyes.png'),check_existing=True)
        mat.node_tree.links.new(image.outputs['Alpha'],shader.inputs['Alpha']);mat.surface_render_method='DITHERED'
        separate=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(image.outputs['Color'],separate.inputs['Color'])
        max1=mat.node_tree.nodes.new('ShaderNodeMath');max1.operation='MAXIMUM';mat.node_tree.links.new(separate.outputs[0],max1.inputs[0]);mat.node_tree.links.new(separate.outputs[1],max1.inputs[1])
        max2=mat.node_tree.nodes.new('ShaderNodeMath');max2.operation='MAXIMUM';mat.node_tree.links.new(max1.outputs[0],max2.inputs[0]);mat.node_tree.links.new(separate.outputs[2],max2.inputs[1])
        combine=mat.node_tree.nodes.new('ShaderNodeCombineColor');mat.node_tree.links.new(max2.outputs[0],combine.inputs[0])
        for channel,divisor in((1,24),(2,32)):
            divide=mat.node_tree.nodes.new('ShaderNodeMath');divide.operation='DIVIDE';divide.inputs[1].default_value=divisor;mat.node_tree.links.new(max2.outputs[0],divide.inputs[0]);mat.node_tree.links.new(divide.outputs[0],combine.inputs[channel])
        mat.node_tree.links.new(combine.outputs[0],shader.inputs['Base Color']);mat.node_tree.links.new(combine.outputs[0],shader.inputs['Emission Color']);shader.inputs['Emission Strength'].default_value=3
        shader.inputs['Alpha'].default_value=1
        for link in list(mat.node_tree.links):
            if link.to_socket==shader.inputs['Alpha']:mat.node_tree.links.remove(link)
        mixed=mat.node_tree.nodes.new('ShaderNodeMixRGB');mixed.name='EyeBaseMix';mixed.blend_type='MIX'
        mat.node_tree.links.new(image.outputs['Alpha'],mixed.inputs[0]);mat.node_tree.links.new(base.outputs['Color'],mixed.inputs[1]);mat.node_tree.links.new(combine.outputs[0],mixed.inputs[2]);mat.node_tree.links.new(mixed.outputs[0],shader.inputs['Base Color'])
        emitting=mat.node_tree.nodes.new('ShaderNodeMixRGB');emitting.name='EyeEmission';emitting.blend_type='MULTIPLY';emitting.inputs[0].default_value=1
        mat.node_tree.links.new(image.outputs['Alpha'],emitting.inputs[1]);mat.node_tree.links.new(combine.outputs[0],emitting.inputs[2]);mat.node_tree.links.new(emitting.outputs[0],shader.inputs['Emission Color'])
    materials[role]=mat
bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
lamps=[]
for offset,power in [((-65,-85,110),130000),((80,25,65),85000)]:
    bpy.ops.object.light_add(type='AREA');lamp=bpy.context.object;lamp.data.energy=power;lamp.data.size=80;lamps.append((lamp,Vector(offset)))
floor=None
for row in doc['records']:
    requested=sys.argv[sys.argv.index('--')+2:]
    if requested and row['name'] not in requested[0].split(','):continue
    data=np.load(folder/(row['name']+'.npz'));objects=[]
    if row.get('ground')and floor is None:
        bpy.ops.mesh.primitive_plane_add(size=600,location=(0,0,-.01));floor=bpy.context.object
        fm=bpy.data.materials.new('Ground');fm.diffuse_color=(.055,.055,.06,1);floor.data.materials.append(fm)
    if floor:floor.hide_render=not row.get('ground',False)
    for role in ('hero','angel','weapon','head'):
        if role not in data:continue
        vertices=data[role]
        if not len(vertices):continue
        vertices=vertices[:,[0,2,1]]*[1,-1,1]
        mesh=bpy.data.meshes.new(role);mesh.from_pydata(vertices,[],np.arange(len(vertices)).reshape(-1,3));mesh.update()
        uv=mesh.uv_layers.new();coords=data[role+'_uv'].copy();coords[:,1]=1-coords[:,1];uv.data.foreach_set('uv',coords.ravel())
        if role=='hero'and row.get('hero_texture'):
            tex=materials[role].node_tree.nodes.get('Image Texture');tex.image=bpy.data.images.load(str(Path(doc['texture_root'])/row['hero_texture']),check_existing=True)
        if role=='weapon'and row.get('weapon_texture'):
            tex=materials[role].node_tree.nodes.get('Image Texture');tex.image=bpy.data.images.load(str(Path(doc['texture_root'])/row['weapon_texture']),check_existing=True)
        if role=='head':
            shader=materials[role].node_tree.nodes.get('Principled BSDF');shader.inputs['Emission Strength'].default_value=0 if row.get('eyes_state')=='dark'else 3
            tree=materials[role].node_tree
            texture=row.get('hero_texture','eva_unit01.png')
            tree.nodes.get('Image Texture').image=bpy.data.images.load(str(Path(doc['texture_root'])/texture),check_existing=True)
            eye=tree.nodes.get('EyeMask');eye.image=bpy.data.images.load(str(Path(doc['texture_root'])/texture.replace('.png','_eyes.png')),check_existing=True)
            combine=materials[role].node_tree.nodes.get('Combine Color')
            mixed=materials[role].node_tree.nodes.get('EyeBaseMix')
            emitting=tree.nodes.get('EyeEmission')
            for link in list(materials[role].node_tree.links):
                if link.to_socket==mixed.inputs[2]or link.to_socket==emitting.inputs[2]:materials[role].node_tree.links.remove(link)
            if row.get('eyes_state')=='dark':mixed.inputs[2].default_value=(.003,.003,.004,1)
            else:materials[role].node_tree.links.new(eye.outputs['Color']if row.get('eyes_state')=='normal'else combine.outputs[0],mixed.inputs[2])
            tree.links.new(eye.outputs['Color']if row.get('eyes_state')=='normal'else combine.outputs[0],emitting.inputs[2])
        mesh.materials.append(materials[role]);obj=bpy.data.objects.new(role,mesh);bpy.context.collection.objects.link(obj);objects.append(obj)
    centre=Vector((row['centre'][0],-row['centre'][2],row['centre'][1]))
    camera.data.ortho_scale=row['extent']*1.16
    camera.location=centre+Vector((110,120,20) if '--back' in requested else (-110,-120,20));camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler()
    for lamp,offset in lamps:
        lamp.location=centre+offset;lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(folder/(row['name']+('_back' if '--back' in requested else '')+'.png'));bpy.ops.render.render(write_still=True)
    for obj in objects:
        mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
