"""Turn a Mesh2Motion run retargeted to Unit-01 into a clip overlay: python sprint_overlay.py sprint.json out.json

The Sprint cycle (Mesh2Motion human-base-animations.glb, CC0) goes in whole, at
its own full stride.  Warped down to the distance the EVA covers it became a
crouched shuffle, and every hand-keyed replacement read worse than the capture.
Prints each foot's support window for EvaBodyPose.gaitFootDownR59.
"""
import json
import sys

import numpy as np

import gait_clip as G
import rig as R
import scene as S

BONES = ['torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']


def main():
    doc = json.load(open(sys.argv[1], encoding='utf8'))
    bones = doc['bones']
    name, clip = list(doc['clips'].items())[0]
    at = [bones.index(b) for b in BONES]
    frames = []
    for f in clip['frames']:
        frames.append({'root_m': f['root_m'], 'rotation_wxyz': [f['rotation_wxyz'][i] for i in at],
                       'bone_position_xyz': {b: v for b, v in (f.get('bone_position_xyz') or {}).items() if b in BONES}})
    out = {'source': 'Mesh2Motion human-base-animations.glb: %s (CC0), retargeted to Unit-01 at full stride' % name,
           'clip': 'dash_run', 'first_frame': 0, 'bones': BONES, 'frames': frames}
    json.dump(out, open(sys.argv[2], 'w', encoding='utf8'), separators=(',', ':'))
    actors = S.Actors()
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    soles = {'l': [], 'r': []}
    for f in range(len(clip['frames'])):
        rot, pos = G.frame_pose(bones, clip, f)
        m = actors.eva_rig.fk(rot, pos, world)
        for s in soles:
            soles[s].append(min(float((t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min())
                                for b, t, _ in actors.eva_mesh.parts if b == 'foot_' + s))
    low = min(min(v) for v in soles.values())
    n = len(clip['frames']) - 1
    for s, v in soles.items():
        down = [i for i in range(n) if v[i] - low < 1.6]
        print(s, 'frames down', down, 'as phase %.3f..%.3f' % (down[0] / n, down[-1] / n), 'contact mask', [i for i in range(n) if clip['frames'][i]['foot_contact'][0 if s == 'l' else 1]])
    print('wrote', sys.argv[2], len(frames))


if __name__ == '__main__':
    main()
