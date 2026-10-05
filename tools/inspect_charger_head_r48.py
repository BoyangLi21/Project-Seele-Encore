from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'artifacts/rebuild_r48/tripo_pipeline/charger'
bpy.ops.wm.open_mainfile(filepath=str(folder/'lod0.blend'))
scene=bpy.context.scene
for mat in bpy.data.materials:
    if not mat.use_nodes:continue
    for node in mat.node_tree.nodes:
        if node.type!='BSDF_PRINCIPLED':continue
        for name,value in [('Metallic',0),('Roughness',.65)]:
            for link in list(node.inputs[name].links):mat.node_tree.links.remove(link)
            node.inputs[name].default_value=value
world=bpy.data.worlds.new('View');world.use_nodes=True
background=next((n for n in world.node_tree.nodes if n.type=='BACKGROUND'),None) or world.node_tree.nodes.new('ShaderNodeBackground')
output=next((n for n in world.node_tree.nodes if n.type=='OUTPUT_WORLD'),None) or world.node_tree.nodes.new('ShaderNodeOutputWorld')
world.node_tree.links.new(background.outputs[0],output.inputs[0]);background.inputs[1].default_value=.65;scene.world=world
target=Vector((-.23,-.035,.87))
for location in [(-3,-1,2),(-2,1,1)]:
    bpy.ops.object.light_add(type='AREA',location=location);lamp=bpy.context.object;lamp.data.energy=100;lamp.data.size=3;lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(-3,-.70,.87));camera=bpy.context.object;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=.30;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.render.filepath=str(folder/'head_end.png');bpy.ops.render.render(write_still=True)
