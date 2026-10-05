"""Bake the same measured correction into the supplied high-resolution master."""
from pathlib import Path
import json, bpy, numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
PIPE=ROOT/'artifacts/rebuild_r48/tripo_pipeline/charger'
OUT=ROOT/'delivery/Mechanical_Tripo_R48';OUT.mkdir(parents=True,exist_ok=True)
c=json.loads((PIPE/'calibration_unit01.json').read_text('utf8'))
rotation=np.array(c['rotation']);midpoint=np.array(c['midpoint']);controls=np.array(c['controls']);coef=np.array(c['coefficients']);tips=np.array(c['tips']);axis=np.array(c['axis']);seated=np.array(c['seated'])

def deform(v):
    result=(v-midpoint)@rotation.T*c['scale']+[0,0,c['standoff']]
    for start in range(0,len(v),50000):
        p=v[start:start+50000];k=np.exp(-np.sum((p[:,None,:]-controls[None,:,:])**2,axis=2)/(2*c['sigma']**2));result[start:start+len(p)]+=k@coef
    for index,tip in enumerate(tips):
        local=v-tip;axial=local@axis;radial=local-axial[:,None]*axis
        selected=(axial>-.058)&(axial<.012)&(np.linalg.norm(radial,axis=1)<(.024 if index<2 else .035))
        r=radial@rotation.T*c['scale'];straight=np.zeros_like(result)
        straight[:,:2]=seated[index,:2]+r[:,:2]*c['pin_radius_scales'][index]
        straight[:,2]=seated[index,2]-np.minimum(axial,0)*c['scale']
        blend=np.clip((axial+.058)/.022,0,1);blend=blend*blend*(3-2*blend)
        result[selected]=result[selected]*(1-blend[selected,None])+straight[selected]*blend[selected,None]
    return result

bpy.ops.wm.read_factory_settings(use_empty=True)
source=ROOT/'artifacts/rebuild_r48/mechanical_tripo_models/source/charger.glb'
bpy.ops.import_scene.gltf(filepath=str(source));obj=next(o for o in bpy.context.scene.objects if o.type=='MESH');mesh=obj.data
old=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',old);old=old.reshape(-1,3)
matrix=np.array(obj.matrix_world);world=old@matrix[:3,:3].T+matrix[:3,3]
native=world[:,[0,2,1]]*[-1,1,1];fixed=deform(native);new=fixed[:,[0,2,1]]*[-1,1,1]
mesh.vertices.foreach_set('co',new.astype(np.float32).ravel());obj.matrix_world.identity();mesh.update();mesh.calc_loop_triangles()
triangles=np.asarray([t.vertices[:]for t in mesh.loop_triangles],dtype=np.int32)
cross=np.cross(new[triangles[:,1]]-new[triangles[:,0]],new[triangles[:,2]]-new[triangles[:,0]])
normals=np.zeros_like(new)
for corner in range(3):np.add.at(normals,triangles[:,corner],cross)
normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
mesh.normals_split_custom_set_from_vertices(normals.tolist())
obj.name='EVA_NERV_Three_Contact_Charger_R48';obj['units']='metres (Minecraft blocks)';obj['origin']='measured EVA-01 power-port centroid';obj['source_master']='charger.glb preserved unchanged'
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
target=OUT/'charger_corrected_EVA01_high.glb'
bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',use_selection=True,export_animations=False)
print('Corrected original high-resolution charger:',target,len(triangles),'triangles',flush=True)

# Use the actual exported LOD surface for a finite mounting inspection view.
material=obj.data.materials[0];bpy.data.objects.remove(obj,do_unlink=True)
f=np.load(PIPE/'charger_fitted_unit01.npz');vertices=f['vertices']+f['origin'];verts=vertices[:,[0,2,1]]*[1,1,1]
data=bpy.data.meshes.new('Installed charger LOD');data.from_pydata(verts.tolist(),[],f['triangles'].tolist());data.update();data.calc_loop_triangles();uv=data.uv_layers.new(name='UVMap')
for triangle,values in zip(data.loop_triangles,f['uv']):
    for loop,coord in zip(triangle.loops,values):uv.data[loop].uv=coord
charger=bpy.data.objects.new('Fitted charger',data);bpy.context.collection.objects.link(charger);data.materials.append(material)
assets=ROOT/'artifacts/rebuild_r48/assets/assets/projectseele';body=json.loads((assets/'mesh/eva_unit01.mesh.json').read_text('utf8'));rows=[]
for name,part in body['parts'].items():
    if name not in ('torso_upper','torso_lower','head','neck','pylon_l','pylon_r'):continue
    row=np.array(part['vertices']).reshape(-1,8);row[:,:3]+=part['pivot'];rows.append(row)
row=np.concatenate(rows);native=row[:,:3]*[-1,1,1]*5/16
data=bpy.data.meshes.new('Actual installed EVA-01');data.from_pydata(native[:,[0,2,1]].tolist(),[],np.arange(len(native)).reshape(-1,3).tolist());data.update();uv=data.uv_layers.new(name='UVMap')
for loop in data.loops:uv.data[loop.index].uv=(row[loop.vertex_index,3],1-row[loop.vertex_index,4])
actor=bpy.data.objects.new('Actual EVA torso',data);bpy.context.collection.objects.link(actor)
mat=bpy.data.materials.new('Actual original EVA texture');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(assets/'textures/entity/eva_unit01.png'));mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.65;data.materials.append(mat)
world=bpy.data.worlds.new('Inspection');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[1].default_value=.7;bpy.context.scene.world=world
centre=Vector((0,7.5,46));bpy.ops.object.camera_add(location=(11,27,51));camera=bpy.context.object;camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=17;bpy.context.scene.camera=camera
for location in [(5,18,56),(-8,14,47)]:
    bpy.ops.object.light_add(type='AREA',location=location);light=bpy.context.object;light.data.energy=1800;light.data.size=12;light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.resolution_x=1200;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.render.filepath=str(PIPE/'actual_fitted_unit01.png');bpy.ops.render.render(write_still=True)
