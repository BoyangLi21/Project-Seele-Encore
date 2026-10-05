"""Show the actual installed torso meshes and UVs for connector fitting."""
from pathlib import Path
import bpy, json, numpy as np, sys
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'artifacts/rebuild_r48/assets/assets/projectseele'
OUT=ROOT/'artifacts/rebuild_r48/tripo_pipeline/charger/power_ports';OUT.mkdir(parents=True,exist_ok=True)
for variant in (0,1,2):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    name=f'eva_unit0{variant}';data=json.loads((ASSETS/'mesh'/f'{name}.mesh.json').read_text('utf8'))
    rows=[]
    for bone,part in data['parts'].items():
        if bone not in ('torso_upper','torso_lower','head','neck','pylon_l','pylon_r'):continue
        points=np.asarray(part['vertices'],float).reshape(-1,8);points[:,:3]+=part['pivot'];rows.append(points)
    rows=np.concatenate(rows);v=rows[:,:3]*[-1,1,1]/192
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(v[:,[0,2,1]].tolist(),[],np.arange(len(v)).reshape(-1,3).tolist());mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    uv=mesh.uv_layers.new(name='UVMap');coords=rows[:,3:5].copy();coords[:,1]=1-coords[:,1]
    for loop in mesh.loops:uv.data[loop.index].uv=coords[loop.vertex_index]
    mat=bpy.data.materials.new('Installed paint');mat.use_nodes=True
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bsdf.inputs['Roughness'].default_value=.65
    image=mat.node_tree.nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(ASSETS/'textures/entity'/f'{name}.png'))
    mat.node_tree.links.new(image.outputs['Color'],bsdf.inputs['Base Color']);obj.data.materials.append(mat)
    zoom='--zoom' in sys.argv
    centre=.800 if zoom else .76
    bpy.ops.object.camera_add(location=(0,3,centre));camera=bpy.context.object;target=Vector((0,.04,centre));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=.105 if zoom else .65;bpy.context.scene.camera=camera
    world=bpy.data.worlds.new('Study');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[1].default_value=.65;bpy.context.scene.world=world
    for location in ((1,2,2),(-1,1,1)):
        bpy.ops.object.light_add(type='AREA',location=location);lamp=bpy.context.object;lamp.data.energy=80;lamp.data.size=2;lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=1100;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.render.filepath=str(OUT/(name+('_port.png' if zoom else '_back.png')));bpy.ops.render.render(write_still=True)
    np.savez_compressed(OUT/(name+'_surface.npz'),vertices=v,uv=coords)
