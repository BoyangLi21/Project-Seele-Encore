"""Blender exact union of overlapping closed shoulder-shell sections."""
from pathlib import Path
import argparse,json,sys
import bpy,bmesh,numpy as np

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);parts=json.loads(a.input.read_text());bpy.ops.wm.read_factory_settings(use_empty=True)
objects=[]
for i,part in enumerate(parts):
    mesh=bpy.data.meshes.new('Section');mesh.from_pydata(part['vertices'],[],part['faces']);mesh.update()
    clean=bmesh.new();clean.from_mesh(mesh);bmesh.ops.remove_doubles(clean,verts=list(clean.verts),dist=1e-5)
    bmesh.ops.dissolve_degenerate(clean,edges=list(clean.edges),dist=1e-6);bmesh.ops.recalc_face_normals(clean,faces=list(clean.faces))
    assert all(e.is_manifold for e in clean.edges),'Input section is not closed'
    clean.to_mesh(mesh);clean.free()
    obj=bpy.data.objects.new('Section_'+str(i),mesh);bpy.context.collection.objects.link(obj);objects.append(obj)
base=objects[0];bpy.context.view_layer.objects.active=base;base.select_set(True)
for obj in objects[1:]:
    modifier=base.modifiers.new('Union','BOOLEAN');modifier.operation='UNION';modifier.solver='MANIFOLD';modifier.object=obj
    bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.data.objects.remove(obj,do_unlink=True)
bm=bmesh.new();bm.from_mesh(base.data);boundary=sum(e.is_boundary for e in bm.edges);nonmanifold=sum(not e.is_manifold for e in bm.edges)
assert boundary==0 and nonmanifold==0,(boundary,nonmanifold)
base.data.calc_loop_triangles();vertices=np.asarray([v.co[:]for v in base.data.vertices]);triangles=[]
for face in base.data.loop_triangles:
    points=vertices[list(face.vertices)];normal=np.cross(points[1]-points[0],points[2]-points[0]);length=np.linalg.norm(normal)
    if length>1e-9:triangles.append(dict(vertices=points.tolist(),normal=(normal/length).tolist()))
a.out.write_text(json.dumps(dict(triangles=triangles,boundary_edges=boundary,nonmanifold_edges=nonmanifold),separators=(',',':')),encoding='utf8')
