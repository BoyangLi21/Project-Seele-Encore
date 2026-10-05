"""Orthographic actual-asset rigging views; no generated concept substitution."""
import bpy, sys
from pathlib import Path
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index('--') + 1:]
name = args[0]
folder = ROOT / 'artifacts/rebuild_r48/tripo_pipeline' / name
bpy.ops.wm.open_mainfile(filepath=str(folder / 'lod0.blend'))
scene = bpy.context.scene
world = bpy.data.worlds.new('Rigging studio'); world.use_nodes = True
background = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
if background is None: background = world.node_tree.nodes.new('ShaderNodeBackground')
output = next((n for n in world.node_tree.nodes if n.type == 'OUTPUT_WORLD'), None)
if output is None: output = world.node_tree.nodes.new('ShaderNodeOutputWorld')
world.node_tree.links.new(background.outputs[0], output.inputs[0])
background.inputs[0].default_value = (.45, .45, .45, 1)
background.inputs[1].default_value = .65; scene.world = world
for loc, energy in [((1, -2, 3), 240), ((-2, -1, 2), 180), ((0, 2, 2), 260)]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    lamp = bpy.context.object; lamp.data.energy = energy; lamp.data.size = 3
    lamp.rotation_euler = (Vector((0, 0, .5)) - lamp.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(); camera = bpy.context.object
camera.data.type = 'ORTHO'; scene.camera = camera
scene.render.engine = 'CYCLES'; scene.cycles.samples = 12
scene.render.resolution_x = 1000; scene.render.resolution_y = 1300; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'; scene.view_settings.view_transform = 'AgX'
hand_x = -.19 if name == 'un00' else -.218
views = [('front', (0, -3, .49), (0, 0, .49), 1.06), ('side', (3, 0, .49), (0, 0, .49), 1.06)]
if '--hands-only' in args:
    views = [('hand_front', (hand_x, -3, .445), (hand_x, 0, .445), .155),
             ('hand_side', (-3, .015, .445), (hand_x, .015, .445), .155)]
if '--back-only' in args:
    views = [('back', (0, 3, .69), (0, 0, .69), .67)]
for label, location, target, scale in views:
    camera.location = location; camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = scale; scene.render.filepath = str(folder / ('rig_' + label + '.png'))
    bpy.ops.render.render(write_still=True)
