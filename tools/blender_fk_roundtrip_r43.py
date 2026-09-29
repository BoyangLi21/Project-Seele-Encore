"""Run inside isolated Blender: actual armatures/modifiers, saved scene and readback."""
from pathlib import Path
import argparse,sys,json
import bpy
import numpy as np
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/repair_r43/blender_interop');ap.add_argument('--readback',action='store_true')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.out.resolve();FIXTURE=json.loads((OUT/'fixture.json').read_text('utf8'));READBACK=args.readback


def material(name,texture):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes
    shader=n.get('Principled BSDF');shader.inputs['Roughness'].default_value=.65
    tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(texture,check_existing=True)
    m.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color']);return m


def make_actor(data):
    arm=bpy.data.armatures.new(data['name']);rig=bpy.data.objects.new(data['name'],arm);bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for row in data['bones']:
        bone=arm.edit_bones.new(row['name']);bone.head=row['head'];bone.tail=Vector(row['head'])+Vector((0,0,.4));bone.use_connect=False
    for row in data['bones']:
        if row['parent']:arm.edit_bones[row['name']].parent=arm.edit_bones[row['parent']]
    bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
    mesh=bpy.data.meshes.new(data['name']+'_mesh');mesh.from_pydata(data['vertices'],[],data['faces']);mesh.update()
    obj=bpy.data.objects.new(data['name']+'_mesh',mesh);bpy.context.collection.objects.link(obj);obj.parent=rig
    uv=mesh.uv_layers.new(name='UVMap')
    for loop,value in zip(uv.data,data['uv']):loop.uv=(value[0],1-value[1])
    obj.data.materials.append(material(data['name']+'_paint',data['texture']))
    groups=[obj.vertex_groups.new(name=b['name']) for b in data['bones']]
    for vertex,(indices,weights) in enumerate(zip(data['influences'],data['weights'])):
        for index,weight in zip(indices,weights):
            if weight>0:groups[index].add([vertex],weight,'REPLACE')
    modifier=obj.modifiers.new('Measured armature','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=False
    previous={}
    for pose in data['poses']:
        targets={row['name']:Matrix(m)@arm.bones[row['name']].matrix_local for row,m in zip(data['bones'],pose['deform'])}
        for row in data['bones']:
            name=row['name'];bone=rig.pose.bones[name];rest=arm.bones[name].matrix_local
            basis=rest.inverted()@targets[name] if not row['parent'] else rest.inverted()@arm.bones[row['parent']].matrix_local@targets[row['parent']].inverted()@targets[name]
            bone.rotation_mode='QUATERNION';bone.matrix_basis=basis
            if name in previous and bone.rotation_quaternion.dot(previous[name])<0:bone.rotation_quaternion.negate()
            previous[name]=bone.rotation_quaternion.copy()
            for path in ('location','rotation_quaternion','scale'):bone.keyframe_insert(path,frame=pose['frame'])
        rig.location=pose['root'];rig.keyframe_insert('location',frame=pose['frame'])
    return rig,obj


def validate():
    report=[]
    for data in FIXTURE['actors']:
        rig=bpy.data.objects[data['name']];obj=bpy.data.objects[data['name']+'_mesh'];names=[b['name'] for b in data['bones']]
        vertices=np.column_stack([np.asarray(data['vertices']),np.ones(len(data['vertices']))]);ids=np.asarray(data['influences']);weights=np.asarray(data['weights'])
        for pose in data['poses']:
            bpy.context.scene.frame_set(pose['frame']);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
            actual_rig=rig.evaluated_get(deps);worst=0
            for name,wanted in zip(names,pose['deform']):
                actual=np.asarray(actual_rig.pose.bones[name].matrix@rig.data.bones[name].matrix_local.inverted());worst=max(worst,float(np.max(np.abs(actual-np.asarray(wanted)))))
            expected=(np.einsum('vkij,vj->vki',np.asarray(pose['deform'])[ids],vertices)*weights[:,:,None]).sum(1)[:,:3]
            evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();actual=np.array([v.co[:] for v in mesh.vertices]);evaluated.to_mesh_clear()
            error=float(np.linalg.norm(actual-expected,axis=1).max());report.append(dict(actor=data['name'],frame=pose['frame'],bone_matrix_error=worst,vertex_error_blocks=error,scope=data['weighting_scope']))
    passed=all(r['bone_matrix_error']<.001 and r['vertex_error_blocks']<.002 for r in report)
    (OUT/('readback.json' if READBACK else 'evaluation.json')).write_text(json.dumps(dict(blender=bpy.app.version_string,passed=passed,samples=report),indent=2),'utf8')
    print('BLENDER FK',len(report),'actual evaluated mesh samples',passed,flush=True)
    assert passed,'Blender evaluation differs from the exported FK input'


if not READBACK:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for data in FIXTURE['actors']:make_actor(data)
    scene=bpy.context.scene;scene.render.fps=30;scene.frame_end=691
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paired_fk_r43.blend'))
validate()
