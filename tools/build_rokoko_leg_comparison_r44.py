"""Real pinned Rokoko local retarget on measured EVA anatomical joints.

No world-target/IK authoring is reused: target constraints are disabled before
the upstream operator runs. The source neutral is the real ACCAD stand frame,
and CURRENT source/target calibration is explicit. Original runtime untouched.
"""
from pathlib import Path
import argparse,json,sys,math,hashlib
import bpy,numpy as np
from mathutils import Matrix,Vector,Quaternion

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v1');ap.add_argument('--fixture',type=Path);ap.add_argument('--neutral-root-calibration',action='store_true');args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=args.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
BASE=args.source.resolve();fixture=json.loads((args.fixture.resolve()if args.fixture else BASE/'fixture.json').read_text('utf8'));card=json.loads((BASE/'source_card.json').read_text('utf8'));fixture['source_motion_card']=card;(OUT/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
original_argv=sys.argv;sys.argv=[str(ROOT/'tools/build_tv_exchange_r44.py'),'--','--out',str(OUT)]
import build_tv_exchange_r44 as dcc
sys.argv=original_argv
import blender_rokoko_offline_r44 as plugin
import blender_action_legacy_adapter_r44 as slots_adapter


def frame_basis(points,names):
    idx={n:i for i,n in enumerate(names)};right=Vector(points[idx['RightUpLeg']]-points[idx['LeftUpLeg']]);right.y=0;right.normalize();up=Vector((0,1,0));forward=up.cross(right).normalized();basis=Matrix((right,forward,up))
    if abs(basis.determinant()-1)>.00001:raise ValueError('Source basis is not a proper rotation')
    return basis


def sample(data,index):
    lo=int(index);hi=min(lo+1,len(data['positions'])-1);u=index-lo
    qa=[Quaternion((v[3],v[0],v[1],v[2]))for v in data['rotations'][lo]];qb=[Quaternion((v[3],v[0],v[1],v[2]))for v in data['rotations'][hi]];p=np.empty_like(data['positions'][lo]);q=[]
    for i,parent in enumerate(data['parents']):
        if parent<0:
            q.append(qa[i].slerp(qb[i],u));p[i]=data['positions'][lo,i]*(1-u)+data['positions'][hi,i]*u
        else:
            # Interpolate local rotations, then perform FK. Interpolating
            # world child positions separately shortened a fast jump chain
            # by 1.52 cm before it ever reached the retarget operator.
            local=(qa[parent].inverted()@qa[i]).slerp(qb[parent].inverted()@qb[i],u);q.append(q[parent]@local);p[i]=p[parent]+np.asarray(q[parent]@Vector(data['offsets'][i]))
    return p,q


def source_rig():
    stand=np.load(BASE/'source/calibration_stand.npz',allow_pickle=False);names=[str(n)for n in stand['names']];reference=stand['positions'][0];basis=frame_basis(reference,names);hip=reference[names.index('Hips')].copy();hip[1]=0;neutral=np.asarray([list(basis@Vector(p-hip))for p in reference])*.01
    # Exact source hierarchy comes from the licensed BVH; calibrated stand
    # positions replace its folded zero-channel OFFSET shape.
    parents=stand['parents'];arm=bpy.data.armatures.new('ACCAD_measured_neutral');rig=bpy.data.objects.new('ACCAD_continuous_original',arm);bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for i,name in enumerate(names):
        head=Vector(neutral[i]);children=np.flatnonzero(parents==i);tail=Vector(neutral[children[0]])if len(children)else head+Vector((0,0,.03));bone=arm.edit_bones.new(name);bone.head=head;bone.tail=tail if(tail-head).length>.001 else head+Vector((0,0,.03));bone.use_connect=False
        if parents[i]>=0:bone.parent=arm.edit_bones[names[parents[i]]]
    bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False);rig.show_in_front=True;rig.rotation_mode='QUATERNION';raw_reference=[Quaternion((q[3],q[0],q[1],q[2]))for q in stand['rotations'][0]];records=[];previous={};stage=Vector((0,0,0))
    def key_pose(frame,points,rotations,align):
        desired={}
        for i,name in enumerate(names):
            rest=arm.bones[name];delta=align.to_quaternion()@rotations[i]@raw_reference[i].inverted()@basis.to_quaternion().inverted();matrix=(delta@rest.matrix_local.to_quaternion()).to_matrix().to_4x4();matrix.translation=Vector(points[i]);desired[name]=matrix;parent=rest.parent;local=rest.matrix_local.inverted()@matrix if parent is None else rest.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@matrix;pose=rig.pose.bones[name];pose.rotation_mode='QUATERNION';pose.matrix_basis=local
            if name in previous and pose.rotation_quaternion.dot(previous[name])<0:pose.rotation_quaternion.negate()
            previous[name]=pose.rotation_quaternion.copy()
            for channel in('location','rotation_quaternion','scale'):pose.keyframe_insert(channel,frame=frame)
        records.append(dict(frame=frame,points=points.tolist()))
    key_pose(0,neutral,raw_reference,basis)
    def canonical_sample(data,index):
        p,q=sample(data,index);lookup={str(n):i for i,n in enumerate(data['names'])};points=[];rotations=[]
        for i,n in enumerate(names):
            if n in lookup:points.append(p[lookup[n]]);rotations.append(q[lookup[n]])
            elif n=='ToSpine':
                # This jump take omits the stand actor's intermediary dummy.
                # It is not retargeted; reconstruct only that exact reference
                # offset under Hips so all recorded real joints remain intact.
                parent=names.index('Hips');source_parent=lookup['Hips'];delta=q[source_parent]@raw_reference[parent].inverted();points.append(p[source_parent]+np.asarray(delta@Vector(reference[i]-reference[parent])));rotations.append(delta@raw_reference[i])
            else:raise ValueError('Actual source joint missing: '+n)
        return np.asarray(points),rotations
    for segment in card['segments']:
        source=np.load(BASE/'source'/(segment['label']+'.npz'),allow_pickle=False);first,last=segment['source_frame_range'];a,_=canonical_sample(source,first);align=frame_basis(a,names)
        task=segment.get('world_task_forward_native')
        if task is not None:
            forward=Vector(task);forward.y=0
            if forward.length<1e-6:raise ValueError('Measured strike task direction has no horizontal component')
            forward.normalize();up=Vector((0,1,0));right=forward.cross(up).normalized()
            align=Matrix((right,forward,up))
            if abs(align.determinant()-1)>.00001:raise ValueError('Source task frame is not a proper whole-performer rotation')
        origin=a[names.index('Hips')].copy();origin[1]=0;begin,end=segment['candidate_frames']
        for frame in range(begin,end+1):
            u=(frame-begin)/max(1,end-begin)
            knots=segment.get('source_frame_knots')
            source_frame=float(np.interp(u,[k[0]for k in knots],[k[1]for k in knots]))if knots else first+(last-first)*u
            p,q=canonical_sample(source,source_frame);points=np.asarray([list(align@Vector(v-origin))for v in p])*.01+np.asarray(stage);key_pose(frame,points,q,align)
        stage=Vector(points[names.index('Hips')]);stage.z=0
    rig['source']='ACCAD ten actual transition takes; measured standing calibration; no zero-OFFSET T-pose assumption';rig['source_card_sha256']=hashlib.sha256((BASE/'source_card.json').read_bytes()).hexdigest();return rig,records


bpy.ops.wm.read_factory_settings(use_empty=True);scene=dcc.setup_scene();scene.frame_start=0;scene.frame_end=card['frames'];scene.render.fps=30
floor=bpy.data.objects['Contact floor'];floor.scale=(8,8,8)
data=fixture['actors'][0];deform,mesh=dcc.deform_rig(data);target,controls,aliases,hips=dcc.motion_rig(data)
for bone in target.pose.bones:
    for constraint in list(bone.constraints):bone.constraints.remove(constraint)
for obj in controls.values():obj.hide_viewport=True
source,source_records=source_rig();source_checks=[]
for row in source_records:
    scene.frame_set(row['frame']);bpy.context.view_layer.update();evaluated=source.evaluated_get(bpy.context.evaluated_depsgraph_get());head_error=0.;tail_error=0.
    for i,bone in enumerate(source.data.bones):
        pose=evaluated.pose.bones[bone.name];head_error=max(head_error,(pose.head-Vector(row['points'][i])).length)
        if bone.children:
            child=bone.children[0]
            if(child.head_local-bone.head_local).length>.001:tail_error=max(tail_error,(pose.tail-evaluated.pose.bones[child.name].head).length)
    source_checks.append(dict(frame=row['frame'],source_world_head_error_metres=head_error,source_world_tail_to_child_error_metres=tail_error))
(OUT/'source_import_readback.json').write_text(json.dumps(dict(maximum_head_error_metres=max(r['source_world_head_error_metres']for r in source_checks),maximum_tail_to_child_error_metres=max(r['source_world_tail_to_child_error_metres']for r in source_checks),basis_determinant=1.,samples=source_checks,scope='Actual source head and tail/child FK before retarget; all selected v2 sources share exact standing bind.'),indent=2),'utf8')
if max(r['source_world_tail_to_child_error_metres']for r in source_checks)>.001:raise ValueError('Source real FK tail does not match child before official retarget')
scene.frame_set(0);bpy.context.view_layer.update();plugin.main();slots_receipt=slots_adapter.install()
# Naming-scheme persistence is disabled in this private process; upstream code
# and algorithm remain unchanged, and its pinned LGPL source is never written.
import importlib
schemes=importlib.import_module(plugin.PACKAGE+'.core.custom_schemes_manager');schemes.save_retargeting_to_list=lambda:None
scene.rsl_retargeting_armature_source=source;scene.rsl_retargeting_armature_target=target;scene.rsl_retargeting_auto_scaling=True;scene.rsl_retargeting_use_pose='CURRENT'
detected=bpy.ops.rsl.build_bone_list();scene.rsl_retargeting_bone_list.clear();mapping={'Hips':'pelvis','Spine1':'chest','Head':'head'}
for side,word in(('l','Left'),('r','Right')):
    mapping.update({word+'Arm':'arm_'+side,word+'ForeArm':'forearm_'+side,word+'Hand':'hand_'+side,word+'UpLeg':'leg_'+side,word+'Leg':'shin_'+side,word+'Foot':'foot_'+side})
for original,wanted in mapping.items():
    item=scene.rsl_retargeting_bone_list.add();item.bone_name_source=original;item.bone_name_target=wanted;item.bone_name_key='hip'if original=='Hips'else'';item.is_custom=True
scene.frame_set(0);bpy.context.view_layer.update();result=bpy.ops.rsl.retarget_animation()
if result!={'FINISHED'}:raise RuntimeError('Real upstream retarget did not finish: '+repr(result))
scene.frame_set(0);bpy.context.view_layer.update();raw_neutral=target.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['pelvis'].head.copy();neutral_delta=hips-raw_neutral
if args.neutral_root_calibration:
    # CURRENT calibrates angular rest differences, but upstream root COPY
    # LOCATION still uses its source-scaled absolute hip height. Align exactly
    # once to the actual target neutral; do not derive a per-frame floor lift.
    delta_local=target.data.bones['pelvis'].matrix_local.to_3x3().inverted()@neutral_delta;original_locations=[]
    for frame in range(0,card['frames']+1):scene.frame_set(frame);original_locations.append(target.pose.bones['pelvis'].location.copy())
    for frame,location in enumerate(original_locations):
        scene.frame_set(frame);target.pose.bones['pelvis'].location=location+delta_local;target.pose.bones['pelvis'].keyframe_insert('location',frame=frame)
(OUT/'neutral_calibration_receipt.json').write_text(json.dumps(dict(raw_upstream_neutral_root=list(raw_neutral),actual_target_neutral_root=list(hips),uniform_world_offset=list(neutral_delta),applied=args.neutral_root_calibration,scope='One actual neutral-position calibration only; no per-frame sole/root lowering, no game speed or world changes.'),indent=2),'utf8')
rows=[];before=[];previous={}
for frame in range(1,card['frames']+1):
    scene.frame_set(frame);bpy.context.view_layer.update();solved=target.evaluated_get(bpy.context.evaluated_depsgraph_get());matrices={n:solved.pose.bones[n].matrix@target.data.bones[n].matrix_local.inverted()for n in target.data.bones.keys()};desired={n:matrices[aliases[n]]@deform.data.bones[n].matrix_local for n in aliases}
    for bone in deform.data.bones:
        n=bone.name;parent=bone.parent;local=bone.matrix_local.inverted()@desired[n]if parent is None else bone.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@desired[n];pose=deform.pose.bones[n];pose.rotation_mode='QUATERNION';pose.matrix_basis=local
        if n in previous and pose.rotation_quaternion.dot(previous[n])<0:pose.rotation_quaternion.negate()
        previous[n]=pose.rotation_quaternion.copy()
        for channel in('location','rotation_quaternion','scale'):pose.keyframe_insert(channel,frame=frame)
    root=solved.pose.bones['pelvis'].head-hips;root.z=0;camera=scene.camera;camera.location=root+Vector((112,-58,55));camera.rotation_euler=(root+Vector((0,2,31))-camera.location).to_track_quat('-Z','Y').to_euler();camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame)
    rows.append(dict(frame=frame,time=(frame-1)/30,actors={data['name']:dict(root=list(root),yaw=0,deform={n:[list(r)for r in matrices[aliases[n]]]for n in aliases},controls={})}))
source.hide_render=True;scene.frame_start=1;scene.frame_set(1);scene['source_manifest']=json.dumps(dict(design='rokoko_continuous_leg_comparison_r44',source='Ten full-body ACCAD transition takes',retarget='Actual official v1.4.3 local operator, CURRENT measured neutral calibration, manual map',world_target_ik_reused=False,limited_contact_correction='None applied until raw FK/skin failures are measured',quality='UNREVIEWED. Not installed.'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'rokoko_continuous_legs_r44.blend'));(OUT/'baked_world_matrices.json').write_text(json.dumps(rows,separators=(',',':')),'utf8');(OUT/'operator_receipt.json').write_text(json.dumps(dict(upstream_version='1.4.3',blender=bpy.app.version_string,detect_result=list(detected),retarget_result=list(result),manual_mapping=mapping,calibration='CURRENT at source measured Stand frame0 / target actual rig neutral; target IK and COPY constraints removed',frames=len(rows),source_control_world_readback_frames=len(source_records),source_finger_capture=False,account_connected=False,production_installed=False,quality='Real operator execution and saved actual model; artistic/native/end-to-end acceptance unverified'),indent=2),'utf8');print('Saved actual upstream retarget continuous legs',len(rows),flush=True)
