"""Export complete authored attacks into the currently compiled schema2 owner.

This remains private. New source geometry/contact channels replace selected
clips only; inherited attacks and finisher are explicitly not newly verified.
"""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np

AXES=np.array([[1.,0,0],[0,0,-1],[0,1,0]])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--baseline-profile',type=Path,required=True)
    ap.add_argument('--body-profile',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--rig',type=int,required=True)
    ap.add_argument('--contact-surface-task-plane',action='store_true');ap.add_argument('--receipt-path',type=Path)
    args=ap.parse_args();out=args.out.resolve();fixture=json.loads((out/'fixture.json').read_text('utf8'));actor=fixture['actors'][0]
    role=json.loads((out/'paired_runtime_pose_candidate.json').read_text('utf8'))['roles'][actor['name']]
    profile=json.loads(args.baseline_profile.read_text('utf8'));body=json.loads(args.body_profile.read_text('utf8'));rig=body['rigs'][str(args.rig)]
    names=[b['name']for b in rig];contract={b['name']:b for b in role['rig_contract_r44']}
    if any(contract.get(b['name'])!=b for b in rig):raise ValueError('Current actual body rig differs from authored attack')
    index=[role['bones'].index(n)for n in names]
    if profile['bones']!=names:
        # Preserve inherited source order semantically, not by array position.
        old_names=profile['bones']
        for clip in profile['clips'].values():
            for frame in clip['frames']:
                source=dict(zip(old_names,frame['rotation_wxyz']))
                frame['rotation_wxyz']=[source.get(n,[1.,0.,0.,0.])for n in names]
    profile['bones']=names;profile['rig_contract_r44']=rig
    records=json.loads((out/'contact_pass_receipt.json').read_text('utf8'))['records']
    baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'));segments=fixture['source_motion_card']['segments'];report=[]
    points=np.asarray(actor['vertices']);ids=np.asarray(actor['influences']);weights=np.asarray(actor['weights']);owners=ids[np.arange(len(ids)),weights.argmax(axis=1)]
    bone_names=[b['name']for b in actor['bones']]
    for segment in segments:
        label='r32_'+segment['label'];previous=profile['clips'][label]
        chosen=[r['frame']-1 for r in records if r['raw_frame']is not None and segment['candidate_frames'][0]<=r['raw_frame']<=segment['candidate_frames'][1]]
        if not chosen:raise ValueError('Complete source attack missing '+label)
        frames=[];stage=[];contacts=[]
        for i in chosen:
            raw=role['frames'][i]
            frame=dict(rotation_wxyz=[raw['rotation_wxyz'][j]for j in index],root_m=raw['root_m'],
                       bone_position_xyz={n:v for n,v in raw['bone_position_xyz'].items()if n in names},
                       foot_contact=[bool(records[i]['source_contacts']['foot_'+s])for s in('l','r')])
            frames.append(frame);stage.append(raw['stage_root_blocks']);contacts.append(frame['foot_contact'])
        stage=np.asarray(stage);travel=(stage-stage[0])@AXES/35
        travel[:,0]*=-1;travel[:,1]=0
        clip=copy.deepcopy(previous);clip.update(frames=frames,trajectory_m=travel.tolist(),step_contacts=contacts,
            contact_phase=segment['runtime_contact_phase'],leading_side=segment['leading_side'],stance_locked=False,
            support='One authored whole-body contact solve over this actual rig; shared server entity travel owns the stage displacement exactly once',
            source_segment_r44=segment,source_fingers='No captured fingers; actual three-phalange target fist independently authored',
            current_native_input_contract='Existing schema2 r32 clip names / server attack progress and contact sweep; native verification pending')
        if segment['label']!='guard':
            phase=clip['contact_phase'];sample=int(round(phase*(len(chosen)-1)));i=chosen[sample];side=clip['leading_side'];hand='hand_'+side
            now=baked[i]['actors'][actor['name']]['deform'];before=baked[chosen[max(0,sample-1)]]['actors'][actor['name']]['deform']
            shape=[]
            for bone in bone_names:
                if bone==hand or bone.startswith('finger_')and bone.endswith('_'+side):
                    raw_points=points[owners==bone_names.index(bone)]
                    if not len(raw_points):continue
                    matrix=np.asarray(now[bone]);shape.append(raw_points@matrix[:3,:3].T+matrix[:3,3])
            actual=np.concatenate(shape);hand_ref=np.asarray(actor['joints']['arm_'+side]['end'])
            a=np.asarray(now[hand]);b=np.asarray(before[hand]);stroke=(a[:3,:3]@hand_ref+a[:3,3])-(b[:3,:3]@hand_ref+b[:3,3])
            if np.linalg.norm(stroke)<1e-5:stroke=np.array([0.,1.,0.])
            stroke/=np.linalg.norm(stroke);projection=actual@stroke;outer=actual[projection>=projection.max()-.025]
            instantaneous_stroke=stroke.copy()
            if args.contact_surface_task_plane:
                if 'world_task_forward_native'not in segment:raise ValueError('Contact task plane lacks the measured complete source task '+label)
                # The importer transforms the complete measured source task
                # once into canonical +Y. At maximum extension the wrist's
                # last-frame velocity can already be lateral/recoil (V4 jab
                #86.61deg); it cannot define the receiver-facing fist surface.
                stroke=np.array([0.,1.,0.]);projection=actual@stroke;outer=actual[projection>=projection.max()-.025]
            impact=outer.mean(axis=0);neutral=np.linalg.inv(a)@np.r_[impact,1.]
            model=neutral[:3]@AXES*(16/5);model[0]*=-1
            clip['contact_bone']=hand;clip['contact_point_model']=model.tolist()
            clip['actual_closed_fist_contact_r44']=dict(author_frame=i+1,selected_outer_points=len(outer),actual_world_impact=impact.tolist(),stroke_world_direction=stroke.tolist(),scope='Actual closed target hand/finger surface along the measured stroke; native collision, receiver and impact timing require current-world review')
            if args.contact_surface_task_plane:
                clip['actual_closed_fist_contact_r44'].update(reference_plane_method='Actual receiver-facing +Y surface in the complete measured source task frame; pose/body/hand rotations unchanged',
                    stroke_world_direction=instantaneous_stroke.tolist(),instantaneous_wrist_velocity_direction=instantaneous_stroke.tolist(),
                    contact_surface_projection_direction_world=stroke.tolist(),canonical_task_normal_world=[0.,1.,0.],
                    scope='Actual closed hand/finger forward surface through authored task plane. Knuckle identity, native final seam vertices, real receiver and impact require independent review; no pose/art improvement is inferred.')
        profile['clips'][label]=clip
        report.append(dict(clip=label,frames=len(frames),duration_seconds=clip['duration_seconds'],contact_phase=clip['contact_phase'],leading_side=clip['leading_side'],author_frames=[chosen[0]+1,chosen[-1]+1]))
    profile['r44_complete_attack_authoring']=dict(quality='UNAPPROVED actual schema2 candidate; full paired native/contact/art review required',
        saved_author_scene_sha256=hashlib.sha256((out/'rokoko_continuous_legs_r44.blend').read_bytes()).hexdigest(),
        baseline_profile_sha256=hashlib.sha256(args.baseline_profile.read_bytes()).hexdigest(),
        newly_authored_clips=[r['clip']for r in report],inherited_unverified_clips=[n for n in profile['clips']if n not in {r['clip']for r in report}],
        damage_health_cooldown_changed=False,stage_translation_removed_from_pose_once=True)
    args.destination.mkdir(parents=True,exist_ok=True);path=args.destination/f'eva_gameplay_r44_{args.rig}.json'
    path.write_text(json.dumps(profile,separators=(',',':'),ensure_ascii=False),'utf8')
    loaded=json.loads(path.read_text('utf8'))
    if loaded['schema']!=2 or loaded['rig_key']!=args.rig:raise ValueError('Existing native schema contract changed')
    for row in report:
        if any(len(f['rotation_wxyz'])!=len(names)for f in loaded['clips'][row['clip']]['frames']):raise ValueError('Bone channel count changed')
    receipt=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rig=args.rig,clips=report,
        actual_body_contract_sha256=hashlib.sha256(args.body_profile.read_bytes()).hexdigest(),quality=profile['r44_complete_attack_authoring']['quality'])
    receipt_path=args.receipt_path or out/'current_attack_export_receipt.json';receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
