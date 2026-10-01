"""Full body strike vocabulary from actual takes, bound to current inputs."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from bvh_motion_r12 import load_bvh

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'external-assets/incoming/mocap/accad-eva-seed-r01/third_party_normalized/source_extract/male2_bvh'
TAKES=[('guard','Male2_D1_StandToReady.bvh','l'),('jab','Male2_E1_JabLeft.bvh','l'),
       ('cross','Male2_E4_CrossRight.bvh','r'),('hook','Male2_E5_HookLeft.bvh','l'),
       ('heavy','Male2_E8_UppercutRight.bvh','r')]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--measured-strike-frame',action='store_true');args=ap.parse_args()
    out=args.out.resolve();(out/'source').mkdir(parents=True,exist_ok=True)
    profile=json.loads(args.profile.read_text('utf8'));stand=load_bvh(SOURCE/'Male2_A1_Stand.bvh');segments=[];frame=1
    for label,filename,side in TAKES:
        path=SOURCE/filename;data=load_bvh(path)
        if data['names']!=stand['names']or not np.array_equal(data['parents'],stand['parents'])or np.max(np.abs(data['offsets'][1:]-stand['offsets'][1:]))>1e-6:
            raise ValueError('Actual shared source neutral not valid for '+label)
        old=profile['clips']['r32_'+label];names=data['names'];points=data['positions']
        if label=='guard':
            first=max(0,len(points)-32);last=len(points)-1;peak=last
        else:
            bone=('Left'if side=='l'else'Right')+('Foot'if label=='stomp'else'Hand')
            relative=points[:,names.index(bone)]-points[:,names.index('Hips')]
            right=points[0,names.index('RightUpLeg')]-points[0,names.index('LeftUpLeg')]
            right[1]=0;right/=np.linalg.norm(right);forward=np.cross([0.,1.,0.],right)
            # Heading is measured from this take's own hips, not a guessed
            # fixed catalog sign. Full return surrounds the actual stroke.
            peak=int(np.argmax(relative@forward));first=max(0,peak-16);last=min(len(points)-1,peak+24)
            if label=='heavy' and 'Uppercut' in filename:
                # This take is an uppercut: its high contact target is the
                # vertical extension, not the forward-projection maximum.
                peak=int(np.argmax(relative[:,1]));first=max(0,peak-16);last=min(len(points)-1,peak+24)
            if last-first<20:raise ValueError('Too short actual fullbody strike '+label)
        duration=float(old['duration_seconds']);count=round(duration*30)+1
        contact=float(old.get('contact_phase',.45));knots=None if label=='guard'else[[0.,first],[contact,peak],[1.,last]]
        segment=dict(label=label,source_file=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_frame_range=[first,last],source_fps=data['fps'],original_window_seconds=(last-first)/data['fps'],candidate_seconds=duration,
            candidate_frames=[frame,frame+count-1],candidate_pose_interval_seconds=(count-1)/30,source_frame_knots=knots,
            runtime_contact_phase=contact,leading_side=side,source_time_preserved=False,
            timing_scope='Whole original anatomical FK remapped monotonically to existing server action/contact phase; current server attack multiplier remains unchanged',
            contact_scope='Peak source forward extension is a timing reference, not captured opponent impact. Native shared body contact sweep owns actual collision.',
            source_semantics='Actual complete windup/stroke/return body capture; feet, hips, chest and both arms retained, target fingers separately authored')
        if args.measured_strike_frame and label!='guard':
            wrist=points[:,names.index(bone)]
            stroke=wrist[peak]-wrist[max(first,peak-2)]
            planar_stroke=stroke.copy();planar_stroke[1]=0
            speed=float(np.linalg.norm(planar_stroke)*data['fps']/max(1,peak-max(first,peak-2))*.01)
            hip=points[peak,names.index('Hips')]
            foot_centres=np.asarray([points[peak,names.index(word+'ToeBase')]for word in('Left','Right')])
            support=foot_centres.mean(axis=0)
            target_root=wrist[peak]-hip;target_support=wrist[peak]-support
            root_plane=target_root.copy();root_plane[1]=0;support_plane=target_support.copy();support_plane[1]=0
            facing_right=points[peak,names.index('RightUpLeg')]-points[peak,names.index('LeftUpLeg')]
            facing_right[1]=0;facing_right/=np.linalg.norm(facing_right)
            body_forward=np.cross([0.,1.,0.],facing_right)
            approach_lo=max(first,peak-8);approach_hi=max(approach_lo+1,peak-3)
            approach=wrist[approach_hi]-wrist[approach_lo];approach[1]=0
            approach_speed=float(np.linalg.norm(approach)*data['fps']/(approach_hi-approach_lo)*.01)
            approach_alignment=None
            if np.linalg.norm(approach)>1e-5 and np.linalg.norm(root_plane)>1e-5:
                approach_alignment=float(np.degrees(np.arccos(np.clip(approach@root_plane/(np.linalg.norm(approach)*np.linalg.norm(root_plane)),-1,1))))
            if label in('jab','cross')and approach_speed>.25 and approach_alignment is not None and approach_alignment<30:
                # Maximum extension is a turning point; its last two frames
                # can already be tangent/recoil (jab V3 was74deg off target).
                task=approach;method='Measured complete pre-contact straight approach secant, cross-checked against actual contact target'
            else:
                # Hook velocity is tangent to its contact arc; uppercut
                # horizontal velocity can approach zero. Their target plane
                # comes from the actual contact endpoint over the support.
                task=support_plane;method='Actual arc/vertical contact endpoint relative to shared foot support centre'
                if np.linalg.norm(task)*.01<.12:
                    task=np.mean(wrist[max(first,peak-6):peak+1]-points[max(first,peak-6):peak+1,names.index('Hips')],axis=0);task[1]=0
                    method='Seven-frame contact approach mean endpoint relative to pelvis; weak planar endpoint fallback'
                if np.linalg.norm(task)*.01<.12:task=body_forward;method='Measured actual body heading fallback; contact direction inferred and flagged'
            if np.linalg.norm(task)<1e-5:raise ValueError('No stable source task vector '+label)
            task=task/np.linalg.norm(task)
            segment['world_task_forward_native']=task.tolist()
            segment['world_task_frame_r44']=dict(measured_source_frames=[max(first,peak-2),peak],
                method=method,source_contact_point_cm=wrist[peak].tolist(),source_pelvis_cm=hip.tolist(),
                source_both_toe_support_centre_cm=support.tolist(),support_scope='Mean of both actual source ToeBase joint centres, geometric support reference; force/plant capture not asserted',
                source_target_relative_root_cm=target_root.tolist(),source_target_relative_support_cm=target_support.tolist(),
                source_planar_approach_speed_metres_per_second=speed,source_body_forward_native=body_forward.tolist(),
                stable_approach_source_frames=[approach_lo,approach_hi],stable_approach_planar_speed_metres_per_second=approach_speed,
                stable_approach_vs_root_target_degrees=approach_alignment,stable_approach_vector_native=approach.tolist(),
                basis='Whole captured performer, limbs, root travel and orientations share this source strike line; target forward is canonical+Y before retarget. Source hip/chest relative twists are retained.',
                first_error='V1 inferred target heading from opening hip transverse axis. Native cross root consequently rotates into its off-axis source strike; authored layer first owns the mismatch. No uniform attack angle or per-bone multiplier is applied.')
        if label=='stomp':segment['source_semantics']='Captured forward left push kick, distinct from a downward stomp; requires matching input/contact direction before native approval'
        segments.append(segment);frame+=count
        np.savez_compressed(out/'source'/(label+'.npz'),**{k:data[k]for k in('names','parents','positions','rotations','fps','offsets')})
    np.savez_compressed(out/'source/calibration_stand.npz',**{k:stand[k]for k in('names','parents','positions','rotations','fps','offsets')})
    card=dict(schema='projectseele.continuous-leg-source.r44',source_kind='Actual ACCAD full-body martial arts capture',fps=30,frames=frame-1,
        segments=segments,source_license='ACCAD / Ohio State University Open Motion Project CC BY 3.0',source_url='https://accad.osu.edu/research/motion-lab/mocap-system-and-data',
        calibration='Actual same-actor Male2_A1_Stand frame0; exact hierarchy and nonroot offsets checked',quality='UNAPPROVED complete attack authoring input; current source aliases do not certify combat role or final performance')
    fixture=json.loads((ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v5_run_seam_study/fixture.json').read_text('utf8'))
    fixture['source_motion_card']=card;fixture['duration']=(frame-1)/30
    (out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8');(out/'source_card.json').write_text(json.dumps(card,indent=2),'utf8')
    print(json.dumps(dict(frames=frame-1,clips=[s['label']for s in segments])))


if __name__=='__main__':main()
