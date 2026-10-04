"""Editable exchange scenes from exact existing geometry; no new animation/video."""
from pathlib import Path
import argparse,hashlib,json,sys
import bpy,numpy as np
from mathutils import Matrix,Vector

ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);root=args.root.resolve()
assets=root/'02_CURRENT_GAME/assets/projectseele';out=root/'06_EDITABLE';out.mkdir(exist_ok=True)
AX=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);C=np.eye(4);C[:3,:3]=AX
results=[]
for k in range(3):
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    name=f'eva_unit0{k}';geo=json.loads((assets/'geo'/(name+'.geo.json')).read_text());rig={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};cache={}
    def bind(n):
        if n in cache:return cache[n].copy()
        b=rig[n];p=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);angles=np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1])
        R=Matrix.Rotation(float(angles[2]),4,'Z')@Matrix.Rotation(float(angles[1]),4,'Y')@Matrix.Rotation(float(angles[0]),4,'X')
        m=Matrix.Translation(p)@R@Matrix.Translation(-p)
        if b.get('parent'):m=bind(b['parent'])@m
        cache[n]=m.copy();return m
    arm=bpy.data.armatures.new(name+'_native_contract');obj=bpy.data.objects.new(name+'_native_contract',arm);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    joint_matrices={}
    for n,b in rig.items():
        p=Vector(np.asarray(b['pivot'])*[-1,1,1]/16);m=np.asarray(bind(n)@Matrix.Translation(p));converted=C@m;converted[:3,3]*=5
        bone=arm.edit_bones.new(n);bone.head=converted[:3,3];bone.tail=bone.head+Vector(converted[:3,1])*.6;bone.matrix=Matrix(converted);bone.length=.6;joint_matrices[n]=converted
    for n,b in rig.items():
        if b.get('parent'):arm.edit_bones[n].parent=arm.edit_bones[b['parent']]
    bpy.ops.object.mode_set(mode='OBJECT');obj.show_in_front=True;arm.display_type='STICK'
    image=bpy.data.images.load(str(assets/'textures/entity'/(name+'.png')));image.pack()
    mat=bpy.data.materials.new(name+'_original_atlas');mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);bsdf.inputs['Roughness'].default_value=.45;bsdf.inputs['Alpha'].default_value=1
    meshdata=json.loads((assets/'mesh'/(name+'.mesh.json')).read_text());hands=json.loads((root/f'03_RECOVERED_ORIGINAL_HANDS/unit0{k}'/(name+'_original_hands_r45.mesh.json')).read_text())
    entries=[(n,p,meshdata,None)for n,p in meshdata['parts'].items()if n in rig and not(n.startswith('hand_')or n.startswith('finger_'))]
    entries += [(n,p,hands,hands['jointSkins'][n])for n,p in hands['parts'].items()]
    counts={};max_weight_error=0.
    for n,part,source,skin in entries:
        raw=np.asarray(part['vertices'],dtype=float).reshape(-1,source['stride']);pts=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
        if skin is None:
            m=np.asarray(bind(n));pts=pts@m[:3,:3].T+m[:3,3]
        pts=pts@AX.T*5;data=bpy.data.meshes.new(n+'_surface');data.from_pydata(pts.tolist(),[],np.arange(len(pts)).reshape(-1,3).tolist());data.update();mesh=bpy.data.objects.new(n+'_surface',data);bpy.context.collection.objects.link(mesh);mesh.data.materials.append(mat)
        uv=mesh.data.uv_layers.new(name='Original_UV')
        for loop in data.loops:uv.data[loop.index].uv=(raw[loop.vertex_index,3],1-raw[loop.vertex_index,4])
        if skin is None:
            group=mesh.vertex_groups.new(name=n);group.add(list(range(len(pts))),1,'REPLACE')
        else:
            totals=np.zeros(len(pts))
            for bone,weights in skin['influences'].items():
                group=mesh.vertex_groups.new(name=bone);ws=np.asarray(weights);totals+=ws
                for weight in np.unique(ws):
                    if weight>1e-8:group.add(np.flatnonzero(ws==weight).tolist(),float(weight),'REPLACE')
            max_weight_error=max(max_weight_error,float(np.abs(totals-1).max()))
        mod=mesh.modifiers.new('Native named skeleton reference','ARMATURE');mod.object=obj;mod.use_deform_preserve_volume=True;mesh.parent=obj;mesh['source_geometry']='Original OBJ surface/UV recovered without shape replacement'if skin else'Current game body, rigid part reference; runtime auto-seam blend is not reproduced'
        counts[n]=len(pts)//3
    scene['handoff_scope']='Exact neutral source hand surfaces and named bind skeleton. Hands use provided weights; body rigid parts are context. Native automatic joint-seam skin is supplied in Java, not certified by this exchange scene. No authored action or video.'
    scene['minecraft_world_blocks_per_blender_unit']=1.0
    # Original wrist and full-body proportions remain inspectable without a render.
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.file.pack_all();blend=out/(name+'_original_hands_workbench.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    glb=out/(name+'_original_hands_workbench.glb');bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',export_animations=False,export_extras=True,export_skins=True,export_all_influences=True)
    (out/(name+'_bind_contract.json')).write_text(json.dumps(dict(authored_geo=geo,native_model_bind_column_major={n:np.asarray(bind(n)).T.reshape(-1).tolist()for n in rig},blender_joint_rest_world={n:m.tolist()for n,m in joint_matrices.items()},blender_axes='native(x,y,z) -> (x,-z,y), multiplied5; one Blender metre = one Minecraft block',max_weight_sum_error=max_weight_error),indent=2),'utf8')
    results.append(dict(rig=k,blend=blend.name,glb=glb.name,parts=len(counts),triangles=sum(counts.values()),hand_triangles={n:counts[n]for n in ['hand_l','hand_r']},maximum_weight_sum_error=max_weight_error,animations_exported=False,native_art_passed=False))
(out/'EXPORT_RECEIPT.json').write_text(json.dumps(results,indent=2),'utf8')
(out/'说明.txt').write_text('三个场景均带完整身体比例参照、原始手部表面、原贴图、同名骨架、手部权重和bind矩阵。\n原始手部造型未用盒子或体素重建。其动作与艺术质量尚未通过，不得把此交换文件当作已修好的最终模型。\n手部为DQS权重参考；身体非手部仅做刚性分件绑定，Minecraft运行时的自动接缝蒙皮见05_CONTRACT/runtime_code/LocalTriangleMeshLayer.java。\n骨骼局部轴严格保留游戏变换约定，骨骼显示尾端不一定指向下一关节。移动/修改骨骼时要同步回传映射与inverse bind。\n单位：1 Blender米=1 Minecraft格，整机约60米。GLB由Blender转换为Y-up，原生JSON约定见05_CONTRACT。\n没有在这些场景里录制或添加新动作，姿态资料单独提供。\n','utf8')
print('Exported3editable reference rigs and GLBs')
