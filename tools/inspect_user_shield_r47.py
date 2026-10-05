"""Inspect/render a user-provided Blender shield without executing embedded code."""
from pathlib import Path
import bpy,json,math
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/models/user_shield_source'
rows=[];points=[]
for obj in bpy.data.objects:
    if obj.type!='MESH':continue
    world=[obj.matrix_world@v.co for v in obj.data.vertices]
    points.extend(world)
    rows.append(dict(name=obj.name,vertices=len(world),polygons=len(obj.data.polygons),
        bounds=[[min(p[i] for p in world) for i in range(3)],[max(p[i] for p in world) for i in range(3)]],
        materials=[m.name for m in obj.data.materials if m]))
if not points:raise ValueError('No shield mesh')
lo=Vector([min(p[i] for p in points) for i in range(3)])
hi=Vector([max(p[i] for p in points) for i in range(3)])
centre=(lo+hi)/2;extent=max(hi-lo)
(OUT/'blend_inspection.json').write_text(json.dumps(dict(objects=rows,bounds=[list(lo),list(hi)],
    images=[dict(name=i.name,path=i.filepath,packed=bool(i.packed_file)) for i in bpy.data.images]),indent=2,ensure_ascii=False),encoding='utf8')
for image in bpy.data.images:
    if image.source=='FILE' and not image.packed_file:
        image.filepath=str(OUT/'dun_tex.tga');image.reload()
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.color=(.16,.16,.16)
scene.view_settings.view_transform='Standard'
for obj in list(scene.objects):
    if obj.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(obj,do_unlink=True)
for n,p,power in [('key',centre+Vector((extent*.6,-extent*.4,extent)),1500),('fill',centre+Vector((-extent*.5,-extent*.1,-extent)),1000)]:
    light=bpy.data.lights.new(n,'AREA');light.energy=power*extent*extent/20;light.shape='DISK';light.size=extent*.6
    obj=bpy.data.objects.new(n,light);scene.collection.objects.link(obj);obj.location=p
    obj.rotation_euler=(centre-obj.location).to_track_quat('-Z','Y').to_euler()
camera=bpy.data.cameras.new('Shield inspection');obj=bpy.data.objects.new('Shield inspection',camera);scene.collection.objects.link(obj);scene.camera=obj
camera.type='ORTHO';camera.ortho_scale=extent*1.17
for name,side in [('front',1),('back',-1)]:
    obj.location=centre+Vector((extent*.22,extent*2*side,extent*.15))
    obj.rotation_euler=(centre-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print(json.dumps(rows,ensure_ascii=False))
