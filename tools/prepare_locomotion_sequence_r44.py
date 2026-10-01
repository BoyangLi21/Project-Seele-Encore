"""Private original-source continuous legs study; source clips are not shipped."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from bvh_motion_r12 import load_bvh

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'external-assets/incoming/mocap/accad-eva-seed-r01/third_party_normalized/source_extract/male2_bvh'
OUT=ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v1'
# Real transition takes, not a loop cut pretending to be a start or brake.
CLIPS=[('stand_to_walk','Male2_B1_StandToWalk.bvh',125,350,1.9),
       ('walk','Male2_B3_Walk.bvh',189,309,1.25),
       ('walk_to_run','Male2_C5_WalkToRun.bvh',8,75,2.2),
       ('run','Male2_C3_Run.bvh',27,50,1.15),
       ('brake','Male2_C2_RunToStand.bvh',0,55,1.85),
       ('jump_land','Male2_C19_RunToJumpToWalk.bvh',0,76,2.55),
       ('crouch','Male2_A7_Crouch.bvh',140,402,2.2),
       ('to_prone','Male2_A8_CrouchToLie.bvh',21,142,4.05),
       ('from_prone','Male2_A10_LieToCrouch.bvh',16,85,2.3),
       ('stand','Male2_D13_CrouchToReady.bvh',25,80,1.85)]


def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--compatible-jump',action='store_true');ap.add_argument('--floor-states',action='store_true');ap.add_argument('--source-timing',action='store_true');ap.add_argument('--run-window',nargs=2,type=int);args=ap.parse_args();OUT=args.out.resolve()
    clips=list(CLIPS)
    if args.run_window:
        first,last=args.run_window
        if first<0 or last-first!=23:raise ValueError('Source run-window study keeps the original23-frame interval/cadence')
        clips[3]=('run','Male2_C3_Run.bvh',first,last,clips[3][4])
    if args.compatible_jump:clips[5]=('jump_land','Male2_B18_WalkToLeapToWalk.bvh',45,113,2.55)
    if args.floor_states:
        clips[8:8]=[('prone_hold','Male2_A9_Lie.bvh',0,93,94/30),('crawl','Male2_A11_Crawl.bvh',0,372,373/30)]
    OUT.mkdir(parents=True,exist_ok=True);source_out=OUT/'source';source_out.mkdir(exist_ok=True)
    fixture=json.loads((ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v13/fixture.json').read_text('utf8'));fixture['actors']=[fixture['actors'][0]];fixture['quality']='UNREVIEWED full-body legs sequence. Current rejected locomotion is not inherited as accepted motion.';fixture['duration']=sum(c[4]for c in clips)
    (OUT/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8');rows=[];frame=1;reference=load_bvh(SOURCE/'Male2_A1_Stand.bvh');bind_audit=[]
    for label,file,first,last,duration in clips:
        path=SOURCE/file;data=load_bvh(path);np.savez_compressed(source_out/(label+'.npz'),names=data['names'],parents=data['parents'],positions=data['positions'],rotations=data['rotations'],fps=data['fps'],offsets=data['offsets'])
        original_seconds=(last-first)/data['fps']
        if args.source_timing:duration=original_seconds
        same_names=data['names']==reference['names'];same_parents=same_names and np.array_equal(data['parents'],reference['parents']);error=float(np.max(np.abs(data['offsets'][1:]-reference['offsets'][1:])))if same_names else None
        audit=dict(take=label,same_joint_order=same_names,same_parents=same_parents,maximum_nonroot_offset_vector_error_cm=error,shared_stand_calibration_valid=bool(same_names and same_parents and error<1e-6));bind_audit.append(audit)
        if args.compatible_jump and not audit['shared_stand_calibration_valid']:raise ValueError('Shared standing bind invalid: '+label)
        semantics='Official A8: crouch to lie, explicitly not completely flat; transition only' if label=='to_prone' else 'Official A9 Lie down; independently verified chest/pelvis anterior normal points downward (dot up ~ -0.995), head looking ahead' if label=='prone_hold' else 'Official A11 Crawl forward; actual alternating forearm/elbow and hand trajectory, not four-foot crawling' if label=='crawl' else 'Original labeled captured transition'
        count=round(duration*30)+(1 if args.source_timing else 0);rows.append(dict(label=label,source_file=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_frame_range=[first,last],source_fps=data['fps'],original_window_seconds=original_seconds,candidate_seconds=duration,candidate_frames=[frame,frame+count-1],candidate_pose_interval_seconds=(count-1)/30,candidate_movie_exposure_seconds=count/30,source_time_preserved=args.source_timing,bind_audit=audit,source_semantics=semantics,official_catalog='https://accad.osu.edu/sites/accad.osu.edu/files/ACCAD_mocap_Data_Male_2.pdf',notes='Source-timing mode preserves actual take duration and includes both endpoint samples; 30Hz quantization is explicit. Physical adaptation/artistic acceptance remains separate.' if args.source_timing else 'Historical deliberately remapped timing; not captured original cadence or artistic acceptance.'));frame+=count
    stand=load_bvh(SOURCE/'Male2_A1_Stand.bvh');np.savez_compressed(source_out/'calibration_stand.npz',names=stand['names'],parents=stand['parents'],positions=stand['positions'],rotations=stand['rotations'],fps=stand['fps'],offsets=stand['offsets'])
    cadence=json.loads((ROOT/'artifacts/rebuild_r44/combat/cadence_audit.json').read_text('utf8'));baseline=next(r for r in cadence['rigs']if r['rig']==1)
    cycles={r['label']:r['original_window_seconds'] if args.source_timing else r['candidate_seconds'] for r in rows if r['label']in('walk','run')}
    card=dict(schema='projectseele.continuous-leg-source.r44',fps=30,frames=frame-1,segments=rows,calibration='Actual ACCAD Male2_A1_Stand frame0; zero-channel OFFSET is not this actor neutral',source_license='ACCAD / Ohio State University Open Motion Project, CC BY 3.0',source_url='https://accad.osu.edu/research/motion-lab/mocap-system-and-data',baseline_native=baseline,latest_run_speed_blocks_per_tick=2.102,latest_speed_scope='Existing stride_world_anchors witness; the 1.5x variant1 difference from baseline3.146 remains unresolved. No speed constant changed.',candidate_cycle_seconds=cycles,source_timing_preserved=args.source_timing,quality='Source/body/sole study only. Walk/run/stop/jump/low poses and transitions require actual skin and native review.')
    fixture['duration']=(frame-1)/30;fixture['source_motion_card']=card;(OUT/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
    (OUT/'source_card.json').write_text(json.dumps(card,indent=2),'utf8');print(json.dumps(dict(frames=card['frames'],seconds=fixture['duration'],segments=[r['label']for r in rows]),indent=2))
    (OUT/'source_bind_audit.json').write_text(json.dumps(bind_audit,indent=2),'utf8')


if __name__=='__main__':main()
