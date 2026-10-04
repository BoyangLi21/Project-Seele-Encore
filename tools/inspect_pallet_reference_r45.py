"""Side elevation of the actual installed rifle source and contact proposals."""
from pathlib import Path
import sys
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'artifacts/rebuild_r45/models/hands/pallet_contact_reference';out.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);points=[];faces=[]
for line in(ROOT/'external-assets/work/pallet-rifle-oni/palett/palett.obj').read_text(encoding='utf8').splitlines():
 if line.startswith('v '):x,y,z=map(float,line.split()[1:4]);points.append((z,-x,y))
 elif line.startswith('f '):f=[int(r.split('/')[0])-1 for r in line.split()[1:]];faces.append(f)
mesh=bpy.data.meshes.new('Actual Pallet Rifle');mesh.from_pydata(points,[],faces);mesh.update();o=bpy.data.objects.new('Actual Pallet Rifle',mesh);bpy.context.collection.objects.link(o);mat=bpy.data.materials.new('Weapon geometry');mat.diffuse_color=(.32,.36,.30,1);mesh.materials.append(mat)
for text,z,y,col,offset in [('Old origin',18,36,(1,.2,.1,1),(-65,30)),('Right palm',23,24,(.1,.6,1,1),(30,-20)),('Left support',-25,21,(1,.8,.1,1),(-90,-25))]:
 bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=2,location=(z,-10,y));m=bpy.data.materials.new(text);m.diffuse_color=col;bpy.context.object.data.materials.append(m)
 curve=bpy.data.curves.new(text,'FONT');curve.body=text;curve.size=7;obj=bpy.data.objects.new(text,curve);bpy.context.collection.objects.link(obj);obj.location=(z+offset[0],-15,y+offset[1]);obj.rotation_euler=(np.pi/2,0,0);curve.materials.append(m)
scene=bpy.context.scene;camera=bpy.data.objects.new('Orthographic source camera',bpy.data.cameras.new('Camera'));bpy.context.collection.objects.link(camera);scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=390;camera.location=(0,-650,57);camera.rotation_euler=(Vector((0,0,57))-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.world=bpy.data.worlds.new('Grey');scene.world.color=(.10,.12,.14);scene.render.resolution_x=1200;scene.render.resolution_y=500;scene.render.resolution_percentage=100;scene.render.filepath=str(out/'source_side.png');bpy.ops.render.render(write_still=True)
