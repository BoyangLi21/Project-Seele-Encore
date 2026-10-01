"""Import the published video combat FK into an editable native Blender rig.

Exports real skeleton-only FBX/BVH, then reimports FBX to audit every joint
against the original world trajectories. No rig/foot-lock marketing claim.
"""
from pathlib import Path
import sys,json,math,argparse
import bpy,numpy as np
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source/boxing'
parser=argparse.ArgumentParser();parser.add_argument('--take',default='data6');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[]);TAKE=args.take
d=np.load(OUT/(TAKE+'_fk.npz'),allow_pickle=False);names=[str(x)for x in d['names']];parents=d['parents'];offset=d['offset'];positions=d['positions'];rotations=d['rotations'];FPS=int(d['fps']);D=Quaternion(Vector((0,0,1)),math.pi/2).to_matrix()
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.fps=FPS;scene.frame_end=len(positions);scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
arm=bpy.data.armatures.new('VIDEO_Boxing24_REST');rig=bpy.data.objects.new('VIDEO_Boxing24',arm);bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT');neutral=[]
for i,name in enumerate(names):
    head=Vector((0,0,0))if parents[i]<0 else neutral[parents[i]]+D@Vector(offset[i]);neutral.append(head)
    children=np.flatnonzero(parents==i);tail=head+D@Vector(offset[children[0]])if len(children)else head+(head-neutral[parents[i]]).normalized()*.07
    bone=arm.edit_bones.new(name);bone.head=head;bone.tail=tail;bone.use_connect=False
    if parents[i]>=0:bone.parent=arm.edit_bones[names[parents[i]]]
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True;rig['source_url']='https://github.com/SMPLOlympics/SMPLOlympics/blob/master/download_data.sh';rig['source_take']='video_boxing_afterproc_upright.pkl / '+TAKE;rig['finger_capture']='absent, 24-joint SMPL';rig['units']='metres / Z up / 30 fps; initial heading canonicalized to +Y'
for frame in range(1,len(positions)+1):
    scene.frame_set(frame);wanted={}
    for i,name in enumerate(names):
        bone=arm.bones[name];delta=Matrix(rotations[frame-1,i].tolist())@D.inverted();m=(delta@bone.matrix_local.to_3x3()).to_4x4();m.translation=Vector(positions[frame-1,i]);wanted[name]=m
        parent=bone.parent;basis=bone.matrix_local.inverted()@m if parent is None else bone.matrix_local.inverted()@parent.matrix_local@wanted[parent.name].inverted()@m
        p=rig.pose.bones[name];p.rotation_mode='QUATERNION';p.matrix_basis=basis
        for channel in('location','rotation_quaternion','scale'):p.keyframe_insert(channel,frame=frame)
    bpy.context.view_layer.update()
errors=[]
for frame in range(1,len(positions)+1):
    scene.frame_set(frame);bpy.context.view_layer.update();solved=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());errors.append(max((solved.pose.bones[n].head-Vector(positions[frame-1,i])).length for i,n in enumerate(names)))
scene['quality']='SOURCE BINDING COMPARISON ONLY. No artistic approval, measured COM, fingers or native input proof.'
scene.frame_set(34);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('A_video_boxing_'+TAKE+'_original.blend')))
bpy.ops.export_scene.fbx(filepath=str(OUT/('A_video_boxing_'+TAKE+'_original.fbx')),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,bake_anim=True,bake_anim_simplify_factor=0,use_armature_deform_only=False,axis_forward='-Z',axis_up='Y')
try:
    import addon_utils;addon_utils.enable('io_anim_bvh',default_set=False)
    bpy.ops.export_anim.bvh(filepath=str(OUT/('A_video_boxing_'+TAKE+'_original.bvh')),frame_start=1,frame_end=len(positions),global_scale=1,rotate_mode='ZXY',root_transform_only=False)
    bvh='Native Blender BVH export succeeded'
except Exception as e:bvh='No BVH exported: '+str(e)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(OUT/('A_video_boxing_'+TAKE+'_original.fbx')));restored=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');readback=[]
for frame in range(1,len(positions)+1):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solved=restored.evaluated_get(bpy.context.evaluated_depsgraph_get());readback.append(max((solved.matrix_world@solved.pose.bones[n].head-Vector(positions[frame-1,i])).length for i,n in enumerate(names)))
result=dict(source_frames=len(positions),fps=FPS,source_blender_joint_world_error_max=max(errors),exported_fbx_reimport_joint_world_error_max=max(readback),bvh=bvh,
    missing=['Finger capture','Measured COM','Contact impulses','Native EVA runtime'],quality='Actual numerical source import/export/reimport only; not visual acceptance.')
(OUT/('blender_source_readback_'+TAKE+'.json')).write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result),flush=True)
