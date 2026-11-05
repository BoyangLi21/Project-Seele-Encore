"""Replay in-game pose records (review client poses.jsonl) through the offline rig.

python replay.py <capture dir> [sheet.png every_n]

Each record carries the bone fields GeckoLib drew (rotX/Y/Z radians, posX/Y/Z
px) after every runtime layer, the entity's drawn position and body yaw.  The
QA mirrors qa.py: ground penetration, planted-foot slide, single-frame joint
flips, thigh roll; results are grouped by the tour segment key.
"""
import json
import math
import sys

import numpy as np

import rig as R
import scene as S

SKIP = ('r45', 'finger', 'r37', 'dorsal', 'knife', 'cannon', 'lance', 'n2', 'horn', 'plug', 'entry', 'pylon')


def load(path):
    rows = []
    seen = set()
    for line in open(path, encoding='utf8'):
        r = json.loads(line)
        if r['tick'] in seen:
            continue
        seen.add(r['tick'])
        rows.append(r)
    return rows


def pose(actors, r):
    rot, pos = {}, {}
    for name, v in r['bones'].items():
        if name not in actors.eva_rig.pivot:
            continue
        rot[name] = R.qzyx(v[2], v[1], v[0])
        pos[name] = np.array([-v[3], v[4], v[5]]) / 16
    world = R.entity_matrix(r['drawnPosition'], r['bodyYaw'], S.SCALE)
    return actors.eva_rig.fk(rot, pos, world)


def main():
    cap = sys.argv[1]
    actors = S.Actors()
    rows = load(cap + '/poses.jsonl')
    ground = min(r['drawnPosition'][1] for r in rows)
    prev_rot, prev_ball = None, {}
    stats = {}
    sheet = []
    every = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    sole = {}
    for side in 'lr':
        ank = actors.eva_rig.pivot['ankle_' + side]
        sole[side] = np.array([ank[0], 0, -8.5 / 16, 1.0])
    for idx, r in enumerate(rows):
        mats = pose(actors, r)
        key = r.get('key', '?')
        st = stats.setdefault(key, {'n': 0, 'pen': 0.0, 'slide': 0.0, 'pop': (0.0, ''), 'frames': []})
        st['n'] += 1
        st['frames'].append(r['tick'])
        for side in 'lr':
            v = np.concatenate([t.reshape(-1, 3) @ mats[b][:3, :3].T + mats[b][:3, 3]
                                for b, t, _ in actors.eva_mesh.parts if b == 'foot_' + side])
            low = v[:, 1].min() - ground
            st['pen'] = max(st['pen'], -low)
            ball = (mats['foot_' + side] @ sole[side])[:3]
            if side in prev_ball and ball[1] - ground < 0.3 and prev_ball[side][1] - ground < 0.3:
                dt = max(1, r['tick'] - prev_ball[side][3]) / 20.0
                st['slide'] = max(st['slide'], np.linalg.norm((ball - prev_ball[side][:3])[[0, 2]]) / dt)
            prev_ball[side] = np.r_[ball, r['tick']]
        world = {b: R.matq(m[:3, :3] / np.linalg.norm(m[:3, 0])) for b, m in mats.items() if not b.startswith(SKIP)}
        # dislocation: the hinge centre seen from the upper and from the lower bone must coincide
        for side in 'lr':
            for up, lo, c in (('arm_', 'forearm_', S.elbow_centre(side)),
                              ('leg_', 'shin_', actors.eva_rig.pivot['shin_' + side] + np.array([0, S.KNEE_LIFT, 0]))):
                gap = np.linalg.norm(mats[up + side][:3, :3] @ c + mats[up + side][:3, 3] - mats[lo + side][:3, :3] @ c - mats[lo + side][:3, 3])
                if gap > st.get('gap', (0.0, ''))[0]:
                    st['gap'] = (gap, '%s%s@%d' % (lo, side, r['tick']))
        if prev_rot is not None:
            dt = max(1, r['tick'] - prev_rot[1])
            for b, q in world.items():
                if b in prev_rot[0]:
                    d = 2 * math.degrees(math.acos(min(1.0, abs(float(np.dot(q, prev_rot[0][b])))))) / dt
                    if d > st['pop'][0]:
                        st['pop'] = (d, '%s@%d' % (b, r['tick']))
        prev_rot = (world, r['tick'])
        if every and idx % every == 0:
            groups = [actors.eva_mesh.triangles(mats, np.eye(4))]
            c = np.array(r['drawnPosition'], float)
            cam = R.Camera(c + np.array([-110, 30 + 0 * c[1], 20]) - np.array([0, 0, 0]), c + np.array([0, 26, 0]), 42, (300, 260))
            img = R.render(cam, groups, label='%d %s' % (r['tick'], key[:22]), ground=(c[0] - 60, c[0] + 60, c[2] - 60, c[2] + 60))
            sheet.append(img)
    print('%-22s %4s %6s %8s  %-26s %s' % ('segment', 'n', 'pen', 'slide/s', 'max joint speed (deg/tick)', 'max hinge gap (blocks)'))
    for key, st in stats.items():
        g = st.get('gap', (0.0, ''))
        print('%-22s %4d %6.2f %8.2f  %4.0f %-21s %5.2f %s' % (key[:22], st['n'], st['pen'], st['slide'], st['pop'][0], st['pop'][1], g[0], g[1]))
    if sheet:
        R.sheet(sheet, 6).save(sys.argv[2])


if __name__ == '__main__':
    main()
