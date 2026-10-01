"""Complete saved-body review with a fixed view direction and whole-body framing.

This changes the review camera only. It does not improve, install, or certify
the motion. Frame numbers are preserved in a sidecar for failed-frame review.
"""
from pathlib import Path
import argparse, json, sys
import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--step', type=int, default=2)
ap.add_argument('--width', type=int, default=480)
ap.add_argument('--frames')
ap.add_argument('--cpu',action='store_true')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = args.out.resolve()
frames = out / ('diagnostic_review_frames' if args.frames else 'complete_review_frames')
frames.mkdir(exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
if args.cpu:
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=2
    scene.cycles.use_denoising=True;scene.cycles.max_bounces=1;scene.cycles.diffuse_bounces=1
    scene.cycles.glossy_bounces=0;scene.cycles.transmission_bounces=0;scene.cycles.volume_bounces=0
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = 'BOTH'
scene.display.shading.background_type = 'WORLD'
scene.world.color = (.1, .11, .13)
scene.render.resolution_x = args.width
scene.render.resolution_y = round(args.width * 9 / 32) * 2
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.threads_mode = 'FIXED'
scene.render.threads = 2
camera = scene.camera
camera.animation_data_clear()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 120
actor=json.loads((out/'fixture.json').read_text('utf8'))['actors'][0]['name']
rig = bpy.data.objects[actor+'_AUTHOR']
mesh = bpy.data.objects[actor+'_actual_mesh']
baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'))
travel=[r['actors'][actor]['root'] for r in baked]
bound=max(abs(p[i]) for p in travel for i in (0,1))+100
floor=bpy.data.objects.get('Contact floor')
if floor:floor.scale=(max(8,bound/110),max(8,bound/110),max(8,bound/110))
# Workbench cannot show the floor's procedural checker. Static actual grid
# strips make stride travel and planted-foot sliding visible in a tracking
# review. They are diagnostic geometry, not an improvement to the animation.
verts=[];faces=[]
lo_x=int(min(p[0] for p in travel)//10)*10-80;hi_x=int(max(p[0] for p in travel)//10)*10+80
lo_y=int(min(p[1] for p in travel)//10)*10-80;hi_y=int(max(p[1] for p in travel)//10)*10+80
for x in range(lo_x,hi_x+1,10):
    at=len(verts);verts.extend([(x-.12,lo_y,.003),(x+.12,lo_y,.003),(x+.12,hi_y,.003),(x-.12,hi_y,.003)]);faces.append((at,at+1,at+2,at+3))
for y in range(lo_y,hi_y+1,10):
    at=len(verts);verts.extend([(lo_x,y-.12,.003),(hi_x,y-.12,.003),(hi_x,y+.12,.003),(lo_x,y+.12,.003)]);faces.append((at,at+1,at+2,at+3))
grid=bpy.data.meshes.new('Actual static ten-block review grid');grid.from_pydata(verts,[],faces);grid.update()
grid_obj=bpy.data.objects.new('R44_STATIC_CONTACT_GRID',grid);bpy.context.collection.objects.link(grid_obj)
grid_material=bpy.data.materials.new('R44 world contact grid');grid_material.diffuse_color=(.13,.17,.22,1);grid.materials.append(grid_material)
receipt = []
selected=[int(v) for v in args.frames.split(',')] if args.frames else range(1,scene.frame_end+1,args.step)
for index, frame in enumerate(selected, 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    bounds = [evaluated.matrix_world @ Vector(v) for v in evaluated.bound_box]
    low = min(v.z for v in bounds)
    high = max(v.z for v in bounds)
    centre = Vector(tuple((min(v[axis] for v in bounds)+max(v[axis] for v in bounds))*.5 for axis in range(3)))
    camera.location = centre + Vector((112, -65, 38))
    camera.rotation_euler = (centre - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(frames / f'{index:04d}.png')
    bpy.ops.render.render(write_still=True)
    receipt.append(dict(index=index, source_frame=frame, time_seconds=(frame - 1) / 30,actual_body_aabb_centre=list(centre),
                        actual_mesh_bottom=low, actual_mesh_top=high))
    print('Complete body frame', frame, flush=True)
(out / ('diagnostic_review_receipt.json' if args.frames else 'complete_review_receipt.json')).write_text(json.dumps(dict(
    frames=receipt, fps=30/args.step, view='Fixed direction, whole body tracking; camera change only',
    ground_grid_spacing_blocks=10,ground_grid_world_static=True,
    scope=f'Actual saved full {scene.frame_end}-frame scene sampled at step {args.step}; {len(receipt)} rendered frames. Workbench is offline and does not reproduce native rendering',
    quality='UNAPPROVED. Existing floor and transition failures remain visible.'), indent=2), 'utf8')
