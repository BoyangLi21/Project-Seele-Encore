"""Render saved armature evaluation for diagnosis; these are not game screenshots."""
from pathlib import Path
import argparse,sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/repair_r43/blender_interop');ap.add_argument('--frames',default='296:grip,391:pin')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);OUT=args.out.resolve()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Diagnostic studio');scene.world.use_nodes=True
nodes=scene.world.node_tree.nodes;background=nodes.new('ShaderNodeBackground');output=nodes.new('ShaderNodeOutputWorld')
background.inputs[0].default_value=(.36,.39,.43,1);background.inputs[1].default_value=.5;scene.world.node_tree.links.new(background.outputs[0],output.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=500,location=(0,0,-.04));floor=bpy.context.object;floor.name='diagnostic_floor'
mat=bpy.data.materials.new('matte floor');mat.diffuse_color=(.22,.24,.27,1);floor.data.materials.append(mat)
for point,power in [((-100,-75,110),90000),((90,25,100),75000)]:
    bpy.ops.object.light_add(type='AREA',location=point);light=bpy.context.object;light.data.energy=power;light.data.size=90;light.rotation_euler=(Vector((0,0,30))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=83
for label,shift in [('before',-75),('candidate',75)]:
    for obj in bpy.data.objects:
        if obj.name.startswith(('eva_','angel_')):obj.hide_render=label not in obj.name
    for item in args.frames.split(','):
        frame,title=item.split(':');frame=int(frame)
        scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();points=[]
        for obj in bpy.data.objects:
            if obj.type=='MESH' and obj.name.startswith(('eva_','angel_')) and label in obj.name:
                evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
                points.extend(evaluated.matrix_world@v.co for v in mesh.vertices);evaluated.to_mesh_clear()
        low=Vector(tuple(min(p[i] for p in points) for i in range(3)));high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
        target=(low+high)*.5;camera.location=target+Vector((62,-95,28));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        inverse=camera.rotation_euler.to_matrix().transposed();projected=[inverse@(p-target) for p in points]
        camera.data.ortho_scale=max(max(p[i] for p in projected)-min(p[i] for p in projected) for i in (0,1))*1.15
        # The earlier fixed camera omitted the contact partner. Preserve it as
        # framing-failure evidence; evaluate both complete actors in this view.
        scene.render.filepath=str(OUT/f'{label}_{title}_full_pair.png');bpy.ops.render.render(write_still=True)
