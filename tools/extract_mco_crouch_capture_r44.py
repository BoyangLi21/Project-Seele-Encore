"""Read actual MCO FBX FK and its own neutral, without the old R05 retarget."""
from pathlib import Path
import argparse, hashlib, json, sys
import bpy, numpy as np
from mathutils import Matrix, Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve();(out/'source').mkdir(parents=True,exist_ok=True)
base=ROOT/'external-assets/incoming/mocap/mco-demo-v2/UE4/MCO_Demo_Pack/Source/FBX'
axes=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
aliases={'pelvis':'Hips','spine_03':'Spine1','head':'Head'}
for side,word in (('l','Left'),('r','Right')):
    aliases.update({a+'_'+side:word+b for a,b in [('upperarm','Arm'),('lowerarm','ForeArm'),('hand','Hand'),('thigh','UpLeg'),('calf','Leg'),('foot','Foot'),('ball','ToeBase')]})

def read(filename):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=base/filename;bpy.ops.import_scene.fbx(filepath=str(path),automatic_bone_orientation=False)
    rig=next(obj for obj in bpy.data.objects if obj.type=='ARMATURE');scene=bpy.context.scene
    action=rig.animation_data.action;first,last=map(round,action.frame_range)
    selected=set(aliases)|{'spine_01','spine_02','neck_01','clavicle_l','clavicle_r'}
    # Independent UE IK helpers and the scene root have animated local
    # translations. They are not anatomical joints; the actual pelvis world
    # trajectory is the capture root, including the original stage travel.
    bones=[b for b in rig.data.bones if b.name in selected]
    names=[aliases.get(b.name,'MCO_'+b.name) for b in bones]
    index={b.name:i for i,b in enumerate(bones)}
    def parent_index(bone):
        parent=bone.parent
        while parent and parent.name not in index:parent=parent.parent
        return index[parent.name]if parent else -1
    parents=np.asarray([parent_index(b)for b in bones])
    points=[];quats=[]
    for frame in range(first,last+1):
        scene.frame_set(frame);bpy.context.view_layer.update();solved=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        points.append([list(axes@(rig.matrix_world@solved.pose.bones[b.name].head)*100)for b in bones])
        quats.append([list((axes@((rig.matrix_world@solved.pose.bones[b.name].matrix).to_3x3())).to_quaternion())for b in bones])
    points=np.asarray(points);quats=np.asarray(quats)[:,:,[1,2,3,0]]
    quats/=np.linalg.norm(quats,axis=2,keepdims=True)
    # Foot endpoint is the real imported ball-bone tail, explicitly a bone
    # endpoint rather than a measured force-plate contact marker.
    for side,word in (('l','Left'),('r','Right')):
        parent=index['ball_'+side];extra=[]
        for frame in range(first,last+1):
            scene.frame_set(frame);bpy.context.view_layer.update();p=rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['ball_'+side]
            extra.append(list(axes@(rig.matrix_world@p.tail)*100))
        names.append(word+'ToeBase_End');parents=np.r_[parents,parent]
        points=np.concatenate((points,np.asarray(extra)[:,None,:]),axis=1)
        quats=np.concatenate((quats,quats[:,parent:parent+1,:]),axis=1)
    required=['Hips','Spine1','Head']+[word+n for word in ('Left','Right')for n in ('Arm','ForeArm','Hand','UpLeg','Leg','Foot','ToeBase','ToeBase_End')]
    if not all(n in names for n in required):raise ValueError('Missing actual MCO anatomical joint '+str(set(required)-set(names)))
    return dict(names=names,parents=parents,positions=points,rotations=quats,fps=scene.render.fps/scene.render.fps_base),dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),first_frame=first,last_frame=last,scene_fps=scene.render.fps/scene.render.fps_base,bones=len(names),bone_endpoint_scope='ToeBase_End is imported ball bone tail, not force/contact capture')

capture,receipt=read('MOB1_CrouchWalk_F.fbx')
stand,stand_receipt=read('W2_Stand_Relaxed_Idle_v2.fbx')
if capture['names']!=stand['names'] or not np.array_equal(capture['parents'],stand['parents']):raise ValueError('Capture and calibration source hierarchies differ')
offsets=np.zeros((len(stand['names']),3))
for i,parent in enumerate(stand['parents']):
    if parent>=0:
        q=stand['rotations'][0,parent]
        offsets[i]=Quaternion((q[3],q[0],q[1],q[2])).inverted()@Vector(stand['positions'][0,i]-stand['positions'][0,parent])
maximum=0.
for i,parent in enumerate(capture['parents']):
    if parent>=0:
        q=capture['rotations'][:,parent];v=np.broadcast_to(offsets[i],(len(q),3));twice=2*np.cross(q[:,:3],v)
        reconstructed=capture['positions'][:,parent]+v+q[:,3,None]*twice+np.cross(q[:,:3],twice)
        maximum=max(maximum,float(np.linalg.norm(reconstructed-capture['positions'][:,i],axis=1).max()*.01))
if maximum>.001:raise ValueError('Actual FBX bone positions cannot use a fixed-offset source FK: '+str(maximum))
for filename,data in [('crouch_walk',capture),('calibration_stand',stand)]:
    data['offsets']=offsets
    if filename=='calibration_stand':data=dict(data,positions=data['positions'][:1],rotations=data['rotations'][:1])
    np.savez_compressed(out/'source'/(filename+'.npz'),**data)
frames=len(capture['positions']);duration=(frames-1)/capture['fps'];count=round(duration*30)+1
segment=dict(label='crouch_walk',source_file=receipt['path'],source_sha256=receipt['sha256'],source_frame_range=[0,frames-1],original_fbx_frame_range=[receipt['first_frame'],receipt['last_frame']],source_fps=capture['fps'],original_window_seconds=duration,candidate_seconds=(count-1)/30,candidate_frames=[1,count],candidate_pose_interval_seconds=(count-1)/30,source_time_preserved=True,source_semantics='Actual complete MCO crouch walk root-motion performance; exact main anatomical FK retained. Independent UE scene/IK helper bones excluded; target fingers remain separately authored')
card=dict(schema='projectseele.continuous-leg-source.r44',fps=30,frames=count,segments=[segment],source_kind='Actual Motus Digital MoCap Online Demo FBX full-body crouch walking capture',source_license='Private local study under existing demo-pack provenance; not cleared for redistribution',source_url='https://mocaponline.com/',source_aliases=aliases,calibration='Own W2_Stand_Relaxed_Idle_v2 actual frame0; fixed offsets checked against captured FBX',source_timing_preserved=True,quality='UNREVIEWED private source; no retarget/native/art acceptance')
fixture=json.loads((ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v5_run_seam_study/fixture.json').read_text('utf8'));fixture['source_motion_card']=card;fixture['duration']=count/30
(out/'source_card.json').write_text(json.dumps(card,indent=2),'utf8');(out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
(out/'actual_fbx_readback.json').write_text(json.dumps(dict(capture=receipt,standing=stand_receipt,maximum_fixed_offset_FK_error_metres=maximum,source_world_units='actual FBX meters converted to cm / Y up before existing reader',quality='Source extraction only'),indent=2),'utf8')
print(json.dumps(dict(frames=count,source_seconds=duration,maximum_fixed_offset_FK_error_metres=maximum)))
