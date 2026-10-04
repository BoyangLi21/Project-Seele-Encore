"""Offline geometric grip preview, explicitly not an in-game render."""
from pathlib import Path
import argparse,sys
import bpy,numpy as np
from mathutils import Matrix,Vector
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out.mkdir(parents=True,exist_ok=False)
d=np.load(a.input);AX=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;points=[]
for name,color in [('hand',(.13,.14,.18,1)),('knife',(.35,.26,.48,1))]:
 if len(d[name])==0:continue
 v=d[name]@AX.T*5;points.extend(v);mesh=bpy.data.meshes.new(name);mesh.from_pydata(v.tolist(),[],np.arange(len(v)).reshape(-1,3).tolist());mesh.update();obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);mat=bpy.data.materials.new(name);mat.diffuse_color=color;mesh.materials.append(mat)
cam=bpy.data.objects.new('Offline camera',bpy.data.cameras.new('Offline camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';pts=np.asarray(points);centre=Vector((pts.min(0)+pts.max(0))*.5);span=float(np.ptp(pts,axis=0).max());normal=Vector(d['normal']@AX.T);up=-Vector(d['along']@AX.T)
for label,view in [('palm',normal),('edge',(normal+normal.cross(up)*1.3).normalized())]:
 cam.location=centre+view*span*3;right=up.cross(view).normalized();camera_up=view.cross(right).normalized();cam.rotation_euler=Matrix((right,camera_up,view)).transposed().to_euler();cam.data.ortho_scale=span*1.2;scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.world=bpy.data.worlds.new('Neutral');scene.world.color=(.08,.1,.12);scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.filepath=str((a.out/(label+'.png')).resolve());bpy.ops.render.render(write_still=True)
