"""One close-up of the actual fitted shield/posed skin, without changing either source."""
from pathlib import Path
import bpy,numpy as np,json
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/models/user_shield_fitted'
data=np.load(OUT/'grip.npz')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def points(a):return np.column_stack((a[:,0],-a[:,2],a[:,1]))
def mesh(name,a,faces):
    m=bpy.data.meshes.new(name);m.from_pydata(points(a).tolist(),[],faces);m.update()
    obj=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(obj);return obj
hand=mesh('Actual unit00 posed hand',data['hand'],np.arange(len(data['hand'])).reshape(-1,3).tolist())
hm=bpy.data.materials.new('Glove');hm.diffuse_color=(.38,.37,.32,1);hand.data.materials.append(hm)
shield=mesh('Original supplied shield',data['shield'],data['faces'].tolist())
sm=bpy.data.materials.new('Original shield texture');sm.use_nodes=True
tex=sm.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'artifacts/rebuild_r47/models/user_shield_source/dun_tex.tga'))
bsdf=sm.node_tree.nodes.new('ShaderNodeBsdfPrincipled');output=sm.node_tree.nodes.new('ShaderNodeOutputMaterial')
sm.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);sm.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface']);shield.data.materials.append(sm)
uv=shield.data.uv_layers.new();values=data['texture_uv'].copy();values[:,1]=1-values[:,1]
for loop in shield.data.loops:uv.data[loop.index].uv=values[loop.index]
p=points(data['hand']);centre=Vector((p.min(0)+p.max(0))/2);extent=float(max(p.max(0)-p.min(0)))
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world.color=(.18,.18,.18);scene.view_settings.view_transform='Standard'
for name,offset,energy in [('key',(2,-2,3),1500),('fill',(-2,-1,1),900)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=energy*extent*extent/40;light.size=extent*3
    obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=centre+Vector(offset)*extent
    obj.rotation_euler=(centre-obj.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.cameras.new('Grip');cam.type='ORTHO';cam.ortho_scale=extent*1.8
obj=bpy.data.objects.new('Grip',cam);scene.collection.objects.link(obj);scene.camera=obj
binding=json.loads((OUT/'IMPORT.json').read_text('utf8'))['binding'];r=binding['rotation_column_major']
back=Vector((r[6],-r[8],r[7]));cross=Vector((r[0],-r[2],r[1]))
obj.location=centre+back*extent*6+cross*extent*.65;obj.rotation_euler=(centre-obj.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(OUT/'grip.png');bpy.ops.render.render(write_still=True)
