"""Author Unit-01's standing idle: python idle.py out.json [preview.png]

A heavy, settled stance instead of a frozen mid-stride: feet under the shoulders
with the left a little ahead, soft knees, a slight slouch, arms hanging with
their own weight, breathing and a slow weight shift on a four second loop.
Written in the stance-clip format ({bones, clips}) for EvaBodyPose.
"""
import json
import math
import sys

import numpy as np

import body as B
import chor
import gait_clip as G
import rig as R
import scene as S

SECONDS = 4.0
FRAMES = 61


def controls(u):
    a = 2 * math.pi * u
    breath = math.sin(a)
    shift = math.sin(a + 0.8)
    c = {k: np.atleast_1d(np.asarray(v, float)) for k, v in chor.EVA_DEFAULTS.items()}
    hip = (0.30 * shift, 35.05 - 0.10 * (breath + 1), 0.75)
    return dict(c, **{k: np.atleast_1d(np.asarray(v, float)) for k, v in dict(
        hip=hip,
        pelvis_rot=(0, 5.0, -0.6 * shift),
        chest=(0.8 * shift, 9.0 - 0.9 * breath, 0.5 * shift),
        head=(1.5 * math.sin(a * 0.5 + 1), 6.0 + 0.5 * breath, 0),
        shoulder_l=(0.9 + 0.9 * breath, 4), shoulder_r=(0.9 + 0.9 * breath, 4),
        foot_l=(6.5, 0, 4.9), foot_r=(-6.5, 0, 2.2), foot_l_rot=(9, 0, 0), foot_r_rot=(-11, 0, 0),
        knee_l=9.0, knee_r=-9.0,
        hand_l=(9.3 + 0.1 * breath, 28.2 + 0.25 * breath, 5.2 + 0.15 * shift),
        hand_r=(-9.3 - 0.1 * breath, 28.2 + 0.25 * breath, 4.8 - 0.15 * shift),
        elbow_l=(0.75, 0.0, -1.0), elbow_r=(-0.75, 0.0, -1.0),
        wrist_l=(10, 0, 0), wrist_r=(10, 0, 0)).items()})


def main():
    out = sys.argv[1]
    a = S.Actors()
    solver = B.EvaBody(a.eva_rig)
    data = json.load(open(G.BODY, encoding='utf8'))
    block = data['stance_clips_by_rig']['1']
    bones = block['bones']
    old = block['clips']['idle']['frames'][0]
    frames = []
    for f in range(FRAMES):
        u = f / (FRAMES - 1)
        rot, pos, mats, info = solver.solve(controls(u))
        row = {'root_m': None, 'rotation_wxyz': [], 'bone_position_xyz': {}}
        for i, n in enumerate(bones):
            if n in rot:
                row['rotation_wxyz'].append([round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))])
            else:
                row['rotation_wxyz'].append(old['rotation_wxyz'][i])
        p = pos['root']
        row['root_m'] = [round(float(x), 6) for x in np.array([-p[0], p[1], p[2]]) * 16 / 112]
        for n in ('shin_l', 'shin_r', 'forearm_l', 'forearm_r'):
            t = pos[n]
            row['bone_position_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    doc = {'bones': bones, 'source': 'Project SEELE original keyed idle (tools/finale/idle.py), MIT',
           'clips': {'idle': {'duration_seconds': SECONDS, 'loop': True, 'frames': frames}}}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, FRAMES, 'frames')
    if len(sys.argv) > 2:
        rot, pos, mats, info = solver.solve(controls(0.0))
        print({k: round(v, 2) for k, v in info.items() if 'knee' in k or 'elbow_' in k or 'err' in k})
        groups = [a.eva_mesh.triangles(mats, np.eye(4))]
        size = (420, 520)
        cams = [R.Camera((-100, 36, 2), (0, 30, 2), 38, size), R.Camera((0, 36, 100), (0, 30, 2), 38, size),
                R.Camera((-62, 34, 70), (0, 30, 2), 40, size), R.Camera((62, 34, -60), (0, 30, 2), 40, size)]
        R.sheet([R.render(c, groups, ground=(-48, 48, -48, 48)) for c in cams], 4).save(sys.argv[2])


if __name__ == '__main__':
    main()
