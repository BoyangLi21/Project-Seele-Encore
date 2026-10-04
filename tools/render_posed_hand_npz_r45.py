"""Fixed-camera stills of an explicit offline hand surface; never native evidence."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector,Matrix

p=argparse.ArgumentParser();p.add_argument('--surface',type=Path,required=True)
p.add_argument('--contract',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--side',choices=('l','r'),default='r');p.add_argument('--vertices-key',default='vertices');p.add_argument('--weapon-key');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
assert a.out.is_absolute();a.out.mkdir(parents=True,exist_ok=False)
d=np.load(a.surface);c=json.loads(a.contract.read_text('utf8'));axes=np.array([[1,0,0],[0,0,-1],[0,1,0]])
points=d[a.vertices_key]@axes.T;origin=points.mean(0);points-=origin
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
mesh=bpy.data.meshes.new('Offline actual hand');faces=d['faces']if'faces'in d else np.arange(len(points)).reshape(-1,3);mesh.from_pydata(points.tolist(),[],faces.tolist());mesh.update()
obj=bpy.data.objects.new('Offline posed surface',mesh);bpy.context.collection.objects.link(obj)
mat=bpy.data.materials.new('Diagnostic purple');mat.diffuse_color=(.35,.14,.65,1);mesh.materials.append(mat)
if a.weapon_key:
 weapon=d[a.weapon_key]@axes.T-origin;wm=bpy.data.meshes.new('Actual rigid weapon');wm.from_pydata(weapon.tolist(),[],np.arange(len(weapon)).reshape(-1,3).tolist());wm.update()
 wo=bpy.data.objects.new('Actual rigid weapon',wm);bpy.context.collection.objects.link(wo);wmat=bpy.data.materials.new('Diagnostic grip');wmat.diffuse_color=(.22,.25,.28,1);wm.materials.append(wmat)
normal=Vector(np.asarray(c['hands'][a.side]['palmar_normal_bind'])@axes.T)
up=-Vector(np.asarray(c['hands'][a.side]['longitudinal_bind'])@axes.T)
centre=Vector((points.min(0)+points.max(0))*.5);span=float(np.ptp(points,axis=0).max())
cam=bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=span*1.4
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True
scene.world=bpy.data.worlds.new('Neutral review');scene.world.color=(.10,.12,.15)
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100
for name,view in [('palm',normal),('three_quarter',(normal+normal.cross(up)*.35+up*.15).normalized()),('back',-normal)]:
 cam.location=centre+view*span*3;right=up.cross(view).normalized();camera_up=view.cross(right).normalized();cam.rotation_euler=Matrix((right,camera_up,view)).transposed().to_euler()
 scene.render.filepath=str(a.out/(name+'.png'));bpy.ops.render.render(write_still=True)
(a.out/'scope.json').write_text(json.dumps({'surface':str(a.surface),'native':False,'accepted':False}),'utf8')
