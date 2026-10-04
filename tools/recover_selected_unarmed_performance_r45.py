"""Recover the previously selected full-body performance into a private current rig.

This is a comparison candidate, not renewed visual approval. It preserves
the selected joint performance/contact sequence and applies the current
anatomical hinge reconstruction; it never plants both feet for the clip.
"""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from author_grounded_capture_r43 import anatomy
from rebuild_stance_hinges_r41 import reconstruct, reachable_root

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rigs', default='1')
    parser.add_argument('--source-tempo', action='store_true', help='Explicit comparison using the selected source clock and the existing runtime 1.5x multiplier')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    source = ROOT/'src/main/resources/assets/projectseele/motion/eva_ordinary_attack_group_c_v1.json'
    selected = json.loads(source.read_text('utf8'))
    assert selected['human_review']['selected'] == 'ordinary_group_c'
    reports = []
    for key in map(int, args.rigs.split(',')):
        assert key in (0, 1, 2), 'UN work remains paused'
        actor = Actor(key)
        current = ROOT/f'run/projectseele-local-maps/eva_gameplay_r42_{key}.json'
        profile = json.loads(current.read_text('utf8'))
        entries=[('jab',1),('cross',2),('hook',3),('heavy',3)]
        if args.source_tempo:entries.append(('jab_loop',1))
        for name, stage in entries:
            src = selected['clips'][f'ordinary_attack_group_c_stage_{stage}'+('_loop'if name=='jab_loop'else '')]
            clip = copy.deepcopy(profile['clips']['r32_'+('jab'if name=='jab_loop'else name)])
            frames, trajectory, errors, soles, hand_tracks = [], [], [], [], []
            origin = np.asarray(src['frames'][0]['root_m'], float)
            for frame in src['frames']:
                pose = decode(actor, selected, frame)
                feet_before = [pose.point('foot_'+s).copy() for s in ('l', 'r')]
                pose = anatomy(actor, pose)
                errors.append(max(np.linalg.norm(pose.point('foot_'+s)-before)
                                  for s, before in zip(('l', 'r'), feet_before))*5/16)
                # Existing entity movement owns X/Z; retain the source's
                # vertical body displacement in the pose, never duplicate it.
                travel = np.asarray(frame['root_m'], float)-origin
                travel[1] = 0
                pose.setp('root', [0, pose.p['root'][1], 0])
                # The selected export predates the current feet and knee
                # sockets. Adapt only vertical contact to today's soles.
                # X/Z and foot orientation remain the captured performance;
                # there is deliberately no clip-long world anchor here.
                goals, orientations = {}, {}
                for i, side in enumerate(('l', 'r')):
                    orientation = R.from_matrix(pose.matrix('foot_'+side)[:3, :3])
                    goal = pose.point('foot_'+side).copy()
                    low = float((orientation.apply(actor.feet[side])+goal)[:, 1].min())
                    if frame['foot_contact'][i] or low < 0:
                        goal[1] -= low
                    goals[side], orientations[side] = goal, orientation
                reachable_root(actor, pose, goals)
                for side in ('l', 'r'):
                    reconstruct(actor, pose, side, goals[side], orientations[side], pose.q['leg_'+side])
                frames.append(actor.rig.encode(pose, tuple(frame['foot_contact']), profile['bones']))
                trajectory.append(travel.tolist())
                soles.append([float((R.from_matrix(pose.matrix('foot_'+s)[:3, :3]).apply(actor.feet[s])
                                     + pose.point('foot_'+s))[:, 1].min())*5/16 for s in ('l', 'r')])
                hand_tracks.append([pose.point('hand_'+s).tolist() for s in ('l', 'r')])
            leading = ('l' if stage == 2 else 'r')
            # Keep contact on the recorded performance. The optional source
            # clock comparison is explicit; damage is unchanged in both modes.
            clip.update(frames=frames, trajectory_m=trajectory,
                        contact_phase=src['contact_frame']/(len(frames)-1),
                        leading_side=leading, step_contacts=[f['foot_contact'] for f in frames],
                        stance_locked=False, support='selected_source_per_frame_contacts',
                        source_duration_seconds=src['duration_seconds'])
            if args.source_tempo and name != 'heavy':
                clip['duration_seconds']=src['duration_seconds']
                clip['source_timing_r45']=True
            profile['clips']['r32_'+name] = clip
            profile['sources'][name] = dict(source=str(source.relative_to(ROOT)),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(), stage=stage,
                source_ids=[r['id'] for r in selected['sources']],
                adaptation='Current anatomical hinges and vertical sole fit; source X/Z, foot orientation/contact sequence; '+('selected source timing with existing runtime speed multiplier' if args.source_tempo and name!='heavy' else 'unchanged current action duration'),
                current_visual_approval=False)
            reports.append(dict(rig=key, clip=name, source_stage=stage, frames=len(frames),
                max_hinge_foot_error_blocks=max(errors), sole_y_range_blocks=np.ptp(soles, axis=0).tolist(),
                sole_minimum_blocks=np.min(soles, axis=0).tolist(),
                source_contact_counts=np.sum([f['foot_contact'] for f in frames], axis=0).tolist(),
                source_contact_phase=clip['contact_phase'], duration_seconds=clip['duration_seconds'],
                hand_tracks_model_units=hand_tracks, joint_angles_from_selected_performance=True))
        profile['r45_selected_performance_recovery'] = dict(status='PRIVATE_COMPARISON_UNAPPROVED',
            no_fixed_dual_foot_bake=True, no_damage_change=True,
            source_tempo_comparison=args.source_tempo,
            remaining='Native support transitions, all rig surfaces, style, complete weapon/state interactions')
        (args.out/f'eva_gameplay_r42_{key}.json').write_text(json.dumps(profile, separators=(',', ':')), 'utf8')
    (args.out/'comparison_provenance.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), reports=reports,
        promoted=False, native_executed=False, visual_accepted=False), indent=2), 'utf8')
    print('Prepared private comparison:', len(reports), 'clips')


if __name__ == '__main__':
    main()
