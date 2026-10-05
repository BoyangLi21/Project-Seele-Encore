"""Blender intake: preserve supplied masters, prepare textured LOD geometry and one preview."""
import argparse,json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--triangles',type=int,default=160000)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.source=args.source.resolve();args.out=args.out.resolve()
    args.out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.source))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(meshes)==1,'Inspect multi-object source before assigning joint ownership'
    obj=meshes[0];bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    original_count=sum(len(p.vertices)-2 for p in obj.data.polygons)
    modifier=obj.modifiers.new('Game surface LOD0','DECIMATE')
    modifier.decimate_type='COLLAPSE';modifier.ratio=min(1,args.triangles/original_count)
    modifier.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.calc_loop_triangles();mesh=obj.data
    vertices=np.asarray([obj.matrix_world@v.co for v in mesh.vertices],dtype=np.float32)
    # Blender Z-up -> the existing native mesh convention used by this project.
    vertices=vertices[:,[0,2,1]]*[-1,1,1]
    triangles=np.asarray([t.vertices[:] for t in mesh.loop_triangles],dtype=np.int32)
    uv=np.asarray([[mesh.uv_layers.active.data[i].uv[:] for i in t.loops]for t in mesh.loop_triangles],dtype=np.float32)
    normals=np.asarray([[mesh.corner_normals[i].vector[:]for i in t.loops]for t in mesh.loop_triangles],dtype=np.float32)
    rotation=np.asarray(obj.matrix_world.to_3x3());normals=normals@np.linalg.inv(rotation)
    normals=normals[:,:,[0,2,1]]*[-1,1,1];normals/=np.maximum(np.linalg.norm(normals,axis=2,keepdims=True),1e-12)
    np.savez_compressed(args.out/'lod0_geometry.npz',vertices=vertices,triangles=triangles,uv=uv,normals=normals)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out/'lod0.blend'))
    bpy.ops.export_scene.gltf(filepath=str(args.out/'lod0.glb'),export_format='GLB',use_selection=True,export_animations=False)

    bounds=[obj.matrix_world@Vector(corner)for corner in obj.bound_box]
    low=Vector(tuple(min(p[i]for p in bounds)for i in range(3)))
    high=Vector(tuple(max(p[i]for p in bounds)for i in range(3)))
    centre=(low+high)*.5;height=max(high.z-low.z,.01)
    bpy.ops.object.camera_add(location=centre+Vector((1.8,-3.4,1.0))*height)
    camera=bpy.context.object;camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=height*1.23;bpy.context.scene.camera=camera
    world=bpy.data.worlds.new('Neutral studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.55,.55,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.55;bpy.context.scene.world=world
    for offset,energy,size in [((2,-3,4),450,3),((-3,-2,2),280,3),((1,3,3),400,2)]:
        bpy.ops.object.light_add(type='AREA',location=centre+Vector(offset)*height)
        lamp=bpy.context.object;lamp.data.energy=energy*height*height;lamp.data.shape='DISK';lamp.data.size=size*height
        lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16
    scene.render.resolution_x=768;scene.render.resolution_y=1024;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX';scene.render.filepath=str(args.out/'actual_lod0_preview.png')
    bpy.ops.render.render(write_still=True)
    report=dict(source=str(args.source),source_triangles=original_count,lod0_triangles=len(triangles),vertices=len(vertices),
                bounds=[vertices.min(0).tolist(),vertices.max(0).tolist()],materials=len(mesh.materials),
                original_master_unchanged=True,rigged=False,game_integrated=False,preview='actual_lod0_preview.png')
    (args.out/'intake_lod0.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
