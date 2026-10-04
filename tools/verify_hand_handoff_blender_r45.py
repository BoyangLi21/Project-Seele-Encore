"""Read back delivered blend files and export weapon reference exchange assets."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=a.root.resolve();out=root/'06_EDITABLE';assets=root/'02_CURRENT_GAME/assets/projectseele';results=[]
for k in range(3):
    f=out/f'eva_unit0{k}_original_hands_workbench.blend';bpy.ops.wm.open_mainfile(filepath=str(f));deps=bpy.context.evaluated_depsgraph_get();rows=[]
    for side in ['l','r']:
        obj=bpy.data.objects['hand_'+side+'_surface'];evaluated=obj.evaluated_get(deps);m=evaluated.to_mesh()
        before=np.asarray([v.co[:]for v in obj.data.vertices]);after=np.asarray([v.co[:]for v in m.vertices]);assert before.shape==after.shape
        error=float(np.linalg.norm(before-after,axis=1).max());assert error<.0001,('Rest deformation',k,side,error)
        assert all(np.isfinite(after).flatten());rows.append(dict(side=side,vertices=len(before),neutral_armature_deformation_max_blocks=error));evaluated.to_mesh_clear()
    assert all(im.packed_file is not None for im in bpy.data.images if im.source=='FILE'),'Unpacked image'
    results.append(dict(rig=k,file=f.name,hands=rows,packed_textures=True,scope='Reopened editable file; original neutral hand geometry is not displaced by its armature. No claim of correct animated hand deformation.'))
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';axis=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
texmap={'eva02_knife':'eva02_weapons','eva_pallet_smg':'eva_pallet_smg','progressive_knife':'progressive_knife','positron_cannon':'positron_cannon','longinus_lance':'longinus_lance'}
for index,(name,texture)in enumerate(texmap.items()):
    source=json.loads((assets/'mesh'/(name+'.mesh.json')).read_text());mat=bpy.data.materials.new(name);mat.use_nodes=True;tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(assets/'textures/entity'/(texture+'.png')));tex.image.pack();bs=mat.node_tree.nodes.get('Principled BSDF');mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Alpha'].default_value=1
    holder=bpy.data.objects.new(name+'_reference',None);bpy.context.collection.objects.link(holder);holder.location.x=index*100;holder['presentation_offset_only']=True;holder['native_asset']=name+'.mesh.json';holder['game_grip_authority']='EvaRifleKinematics/EvaUnit01GeoModel and supplied body grip pose. This scene does not assert final wielding transforms.'
    for n,part in source['parts'].items():
        raw=np.asarray(part['vertices']).reshape(-1,source['stride']);pts=((raw[:,:3]+part['pivot'])*[-1,1,1]/16)@axis.T*5
        mesh=bpy.data.meshes.new(name+'_'+n);mesh.from_pydata(pts.tolist(),[],np.arange(len(pts)).reshape(-1,3).tolist());mesh.update();obj=bpy.data.objects.new(name+'_'+n,mesh);bpy.context.collection.objects.link(obj);obj.parent=holder;obj.data.materials.append(mat);uv=mesh.uv_layers.new()
        for loop in mesh.loops:uv.data[loop.index].uv=(raw[loop.vertex_index,3],1-raw[loop.vertex_index,4])
scene['scope']='Existing weapon mesh/UV data, native authored scale conversion; presentation X offsets only. Actual attached scale, grip, aim and recoil are defined by supplied runtime code and pose JSON.'
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'weapons_reference.blend'));bpy.ops.export_scene.gltf(filepath=str(out/'weapons_reference.glb'),export_format='GLB',export_animations=False,export_extras=True)
(out/'READBACK_VERIFIED.json').write_text(json.dumps(results,indent=2),'utf8');print('Three reopened neutral hand rigs verified; weapons GLB/blend exported')
