"""Measure a gait clip as authored: hip height and sole heights over one cycle.

python gait_clip.py [clip ...]   (default walk run dash_run)
"""
import json
import sys

import numpy as np

import body as B
import rig as R
import scene as S

BODY = 'F:/eva/.claude/motion-work/review_client/projectseele-local-maps/eva_body_r44.json'


def frame_pose(bones, clip, f):
    rot, pos = {}, {}
    fr = clip['frames'][f]
    for i, n in enumerate(bones):
        rot[n] = R.clip_to_baked(fr['rotation_wxyz'][i])
    p = np.array(fr['root_m']) * 112
    pos['root'] = np.array([-p[0], p[1], p[2]]) / 16
    for n, v in (fr.get('bone_position_xyz') or {}).items():
        pos[n] = np.array([-v[0], v[1], v[2]]) / 16
    return rot, pos


def main():
    actors = S.Actors()
    data = json.load(open(BODY, encoding='utf8'))
    print('keys', list(data.keys())[:12])
    block = data['stance_clips_by_rig']['1']
    bones, clips = block['bones'], block['clips']
    print('clips', list(clips.keys()))
    names = sys.argv[1:] or ['walk', 'run', 'dash_run']
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    pv = actors.eva_rig.pivot
    for name in names:
        c = clips[name]
        print(name, {k: (v if isinstance(v, (int, float, str)) else (type(v).__name__, len(v))) for k, v in c.items()})
        n = len(c['frames'])
        rows = []
        for f in range(n):
            rot, pos = frame_pose(bones, c, f)
            m = actors.eva_rig.fk(rot, pos, world)
            hip = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
            soles = []
            for s in 'lr':
                v = np.concatenate([t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3]
                                    for b, t, _ in actors.eva_mesh.parts if b == 'foot_' + s])
                soles.append(v[:, 1].min())
            rows.append((hip[1], soles[0], soles[1], m['root'][1, 3]))
        a = np.array(rows)
        low = a[:, 1:3].min(1)
        print('  frames %d  hip %.2f..%.2f  lowest sole %.2f..%.2f  max frame hip jump %.3f' % (
            n, a[:, 0].min(), a[:, 0].max(), low.min(), low.max(), np.abs(np.diff(a[:, 0])).max()))
        step = max(1, n // 24)
        print('  hip  ', ' '.join('%.1f' % x for x in a[::step, 0]))
        print('  soleL', ' '.join('%.1f' % x for x in a[::step, 1]))
        print('  soleR', ' '.join('%.1f' % x for x in a[::step, 2]))


if __name__ == '__main__':
    main()
