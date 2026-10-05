"""One actual selected-mesh rear assembly review, labelled offline rather than gameplay."""
from pathlib import Path
import sys,json,math,bpy,numpy as np
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[1]/'artifacts/rebuild_r48'
asset=ROOT/'assets/assets/projectseele';out=ROOT/'un_selected_review';out.mkdir(exist_ok=True)
args=sys.argv[sys.argv.index('--')+1:];name=args[0]
data=json.loads((asset/'mesh'/f'{name}.mesh.json').read_text());geo=json.loads((asset/'geo'/f'{name}.geo.json').read_text())
bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};spec=data['r13_dorsal_socket']
for opening in (0,1):
    bpy.ops.wm.read_factory_settings(use_empty=True);mat=bpy.data.materials.new('Selected original UN surface');mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Metallic'].default_value=.5;bsdf.inputs['Roughness'].default_value=.48
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(asset/'textures/entity'/f'{name}.png'));mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    for part,payload in data['parts'].items():
        a=np.asarray(payload['vertices']).reshape(-1,8);p=(a[:,:3]+payload['pivot'])*[-1,1,1]/192
        if part=='dorsal_cover'and opening:
            pivot=Vector(np.array(bones[part]['pivot'])*[-1,1,1]/192);axis=np.array(spec['hinge_axis'])*[1,-1,-1]
            transform=Matrix.Translation(pivot)@Quaternion(Vector(axis),math.radians(spec['open_angle_degrees'])).to_matrix().to_4x4()@Matrix.Translation(-pivot)
            p=(np.c_[p,np.ones(len(p))]@np.array(transform).T)[:,:3]
        coords=p[:,[0,2,1]];mesh=bpy.data.meshes.new(part);mesh.from_pydata(coords.tolist(),[],np.arange(len(coords)).reshape(-1,3).tolist());mesh.update()
        obj=bpy.data.objects.new(part,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='Selected UV')
        for loop in mesh.loops:uv.data[loop.index].uv=(float(a[loop.vertex_index,3]),float(1-a[loop.vertex_index,4]))
        for face in mesh.polygons:face.use_smooth=True
    centre=Vector((0,.06,.79));bpy.ops.object.camera_add(location=(.30,1.5,1.05));cam=bpy.context.object;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.46
    scene=bpy.context.scene;scene.camera=cam;scene.world=bpy.data.worlds.new('Inspection');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    for position in ((1,2,3),(-2,1,2)):
        bpy.ops.object.light_add(type='AREA',location=position);lamp=bpy.context.object;lamp.data.energy=140;lamp.data.size=3;lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.samples=8;scene.render.resolution_x=850;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.filepath=str(out/(name+('_open.png'if opening else'_closed.png')));bpy.ops.render.render(write_still=True)
print('Selected UN source mesh rear assemblies rendered offline',name)
