"""Correct measured neutral arm placement and match knife action entry/exit.

Only NERV upper-body channels change. Accepted legs, captured travel, clocks,
hands, and the supplied knife surface remain intact. No world mutation.
"""
from pathlib import Path
import argparse
import copy
import json
import subprocess
import sys
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from calibrated_arm_r49 import solve
from author_combat_bundle_r44 import maintain_joint_centres
from hand_surface_r49 import natural_carry

ROOT = Path(__file__).resolve().parents[1]


def ease(t):
    t = float(np.clip(t, 0, 1))
    return t*t*t*(10+t*(-15+6*t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--assets', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    body_path = args.runtime/'eva_body_r44.json'
    before = args.out/'before_eva_body_r44.json'
    if not before.exists():
        before.write_bytes(body_path.read_bytes())
    body = json.loads(before.read_text(encoding='utf-8'))
    common.BODY = body
    common.NAMES = body['motion']['bones']
    proof = []
    for key in range(3):
        actor = Actor(key)
        hand_contract=json.loads((args.assets/'hand_rigs'/f'unit0{key}'/'hand_rig_contract.json').read_text(encoding='utf-8'))
        doc = body['stance_clips_by_rig'][str(key)]
        names = doc['bones']
        for frame_index, frame in enumerate(doc['clips']['idle']['frames']):
            pose = actor.rig.decode(frame, names)
            original = copy.deepcopy(pose)
            chest = pose.matrix('torso_upper')
            for side, sign in (('l', -1), ('r', 1)):
                shoulder = pose.point('arm_'+side)
                # The R48 mocap arm basis put both wrists 14-18 model pixels
                # behind the shoulder plane. Place a relaxed near-extended
                # arm alongside the actual torso, with a forward elbow bend.
                # Gravity is world-down; applying the bent chest basis to the
                # entire arm length would reproduce the backward lean.
                goal = shoulder + np.array([sign*5.5, -58.5, -1.5])
                solve(pose, actor.P, 'arm_'+side, 'forearm_'+side, 'hand_'+side,
                      actor.elbows[side], goal, [sign*.12, 0, 1], [1, 0, 0])
                pose.setq('wrist_'+side, original.q['wrist_'+side])
                pose.setq('hand_'+side, original.q['hand_'+side])
                if frame_index == 0:
                    proof.append(dict(unit=key, side=side,
                                      before_shoulder=shoulder.tolist(),
                                      before_hand=original.point('hand_'+side).tolist(),
                                      after_hand=pose.point('hand_'+side).tolist()))
            maintain_joint_centres(actor, pose)
            natural_carry(pose,hand_contract,actor.elbows,actor.P)
            doc['clips']['idle']['frames'][frame_index] = actor.rig.encode(pose, (True, True), names)
        doc['clips']['idle']['r49_arm_basis'] = 'anatomical neutral beside torso; lower body retained'
    body['r49_neutral_arm_repair'] = proof
    body_path.write_text(json.dumps(body, separators=(',', ':')), encoding='utf-8')

    # Author full-body retrieval against the corrected neutral and the same
    # shoulder cassette. The free arm returns to a closer forward ready pose.
    for key in range(3):
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'tools/author_weapon_handling_r45.py'),
                        '--body', str(body_path), '--profiles', str(args.runtime),
                        '--hand', str(args.assets/'hand_rigs'/f'unit0{key}'),
                        '--out', str(args.runtime), '--in-place',
                        '--ready-centre', '17', '113', '-35',
                        '--ready-pole', '.12', '0', '1', '--calibrated-arm-r49'], check=True, cwd=ROOT)

    common.BODY = body
    for key in range(3):
        actor = Actor(key)
        path = args.runtime/f'eva_gameplay_r44_{key}.json'
        profile = json.loads(path.read_text(encoding='utf-8'))
        names = profile['bones']
        recovered = ROOT/'artifacts/rebuild_r45/motion/weapon_motion_candidate_v1'/f'eva_gameplay_r43_{key}.json'
        if not recovered.exists():
            recovered = ROOT/'artifacts/rebuild_r44/combat/motion'/f'eva_gameplay_r44_{key}.json'
        if not all(n in profile['clips'] for n in ('r32_knife_forward', 'r32_knife_reverse')):
            source = json.loads(recovered.read_text(encoding='utf-8'))
            if not set(names).issubset(source['bones']):
                raise ValueError('Restore only the matching complete NERV knife rig')
            order = [source['bones'].index(n) for n in names]
            for name in ('r32_knife_forward', 'r32_knife_reverse'):
                profile['clips'][name] = copy.deepcopy(source['clips'][name])
                for frame in profile['clips'][name]['frames']:
                    frame['rotation_wxyz'] = [frame['rotation_wxyz'][i] for i in order]
                    if 'bone_position_xyz' in frame:
                        frame['bone_position_xyz'] = {n:p for n,p in frame['bone_position_xyz'].items() if n in names}
            profile['r49_restored_knife_performance'] = str(recovered.relative_to(ROOT))
        ready = actor.rig.decode(profile['clips']['r32_knife_draw']['frames'][-1], names)
        changed = []
        for name, clip in profile['clips'].items():
            if 'knife' not in name or name in ('r32_knife_draw', 'r32_knife_stow'):
                continue
            for i, frame in enumerate(clip['frames']):
                t = i/max(1, len(clip['frames'])-1)
                w = float(np.clip(max(1-ease(t/.18), ease((t-.78)/.22)), 0, 1))
                pose = actor.rig.decode(frame, names)
                for side,sign in (('l',-1),('r',1)):
                    shoulder=pose.point('arm_'+side);hand=pose.point('hand_'+side)
                    elbow=pose.point('forearm_'+side,actor.elbows[side]);pole=elbow-shoulder
                    orientation=R.from_matrix(pose.matrix('hand_'+side)[:3,:3])
                    checked=solve(pose,actor.P,'arm_'+side,'forearm_'+side,'hand_'+side,
                                  actor.elbows[side],hand,pole,[1,0,0],orientation)
                    if not checked['axial_guard_passed']:
                        raise ValueError(('Knife action requires whole-body repositioning',key,name,i,side,checked))
                if w>0:
                    for bone in ('arm_r', 'forearm_r', 'wrist_r', 'hand_r'):
                        pose.setq(bone, Slerp([0, 1], R.concatenate([pose.q[bone], ready.q[bone]]))(w))
                        pose.setp(bone, pose.p[bone]*(1-w)+ready.p[bone]*w)
                maintain_joint_centres(actor, pose)
                encoded = actor.rig.encode(pose, frame.get('foot_contact', (False, False)), names)
                frame.update({k: encoded[k] for k in ('rotation_wxyz', 'bone_position_xyz', 'root_m')})
            clip['r49_ready_transition'] = 'same fitted arm chain as knife_draw final pose; attack contact unchanged'
            changed.append(name)
        path.write_text(json.dumps(profile, separators=(',', ':')), encoding='utf-8')
        proof.append(dict(unit=key, knife_ready_hand=ready.point('hand_r').tolist(),
                          knife_ready_elbow=ready.point('forearm_r', actor.elbows['r']).tolist(),
                          transitioned_clips=changed))
    (args.out/'REPORT.json').write_text(json.dumps(dict(changes=proof, native_verified=False,
            unchanged=['lower-body travel', 'attack contact phase', 'damage', 'knife geometry', 'future user motion']), indent=2), encoding='utf-8')
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == '__main__':
    main()
