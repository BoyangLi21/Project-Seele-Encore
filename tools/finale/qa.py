"""Physical QA over the whole clip: python qa.py

Reports ground penetration, planted-foot sliding, joint pops (per-frame angular
speed) and limb reach misses, worst first.
"""
import math

import numpy as np

import chor
import mesh_check
import rig as R
import scene as S

FPS = 30


def foot_vertices(actors, mats, side):
    out = []
    for bone, tris, _ in actors.eva_mesh.parts:
        if bone == 'foot_' + side:
            m = mats[bone]
            out.append(tris.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(out)


def main():
    # numbers measured on a mesh the game does not draw are worth nothing
    if not mesh_check.report():
        raise SystemExit(1)
    actors = S.Actors()
    sc = chor.Scene(actors)
    n = 23 * FPS + 1
    prev_rot, prev_sole = None, {}
    pen, slide, pops, miss, weak, kneedir, twists = [], [], [], [], [], [], []
    for i in range(n):
        t = i / FPS
        s = sc.solve(t)
        rot, pos, mats, info, ctl = s['eva']
        world = {b: R.matq(m[:3, :3] / np.linalg.norm(m[:3, 0])) for b, m in mats.items()
                 if not b.startswith(('r45', 'finger', 'r37', 'dorsal', 'knife', 'cannon', 'lance', 'n2'))}
        for side in 'lr':
            v = foot_vertices(actors, mats, side)
            low = v[:, 1].min()
            pen.append((-low, t, 'foot_' + side))
            ball = mats['foot_' + side] @ np.r_[sc.eva_body.sole[side]['ball'], 1.0]
            ball = ball[:3]
            if side in prev_sole and ball[1] < 0.3 and prev_sole[side][1] < 0.3:
                d = np.linalg.norm((ball - prev_sole[side])[[0, 2]]) * FPS
                slide.append((d, t, 'foot_' + side))
            prev_sole[side] = ball
            # thigh roll about its own axis relative to the pelvis (hip rotation range ~ +-60 deg)
            ql = R.qmul(R.qconj(world['torso_lower']), world['leg_' + side])
            ax = R.qmat(ql) @ np.array([0, -1.0, 0])
            if ax[1] < 0.2:
                tw = R.qmul(R.qconj(R.q_between(np.array([0, -1.0, 0]), ax)), ql)
                kneedir.append((abs((math.degrees(2 * math.atan2(tw[2], tw[0])) + 180) % 360 - 180), t, 'leg_' + side))
            # upper-arm twist about its own axis, relative to rest (shoulder rotation range)
            qa = R.qmul(R.qconj(world['clavicle_' + side]), world['arm_' + side])
            axis = R.qmat(qa) @ np.array([0, -1.0, 0])
            swing = R.q_between(np.array([0, -1.0, 0]), axis)
            twist = R.qmul(R.qconj(swing), qa)
            tw = math.degrees(2 * math.atan2(twist[2], twist[0]))
            tw = (tw + 180) % 360 - 180
            if axis[1] < 0.5:
                twists.append((abs(tw), t, 'arm_' + side))
        if prev_rot is not None:
            for b, q in world.items():
                if b in prev_rot:
                    d = 2 * math.degrees(math.acos(min(1.0, abs(float(np.dot(q, prev_rot[b]))))))
                    pops.append((d, t, b))
        prev_rot = world
        for k, v in info.items():
            if 'err' in k:
                miss.append((v, t, k))
            if 'pole' in k:
                weak.append((1 - v, t, k))
    def report(name, rows, unit, limit, count=8):
        rows = sorted(rows, reverse=True)
        bad = [r for r in rows if r[0] > limit]
        print('%s: %d frames over %.2f %s' % (name, len(bad), limit, unit))
        for v, t, k in bad[:count]:
            print('   %7.2f %s at %5.2f s  %s' % (v, unit, t, k))
    report('ground penetration', pen, 'blocks', 0.4)
    report('planted foot slide', slide, 'blocks/s', 1.5)
    report('joint speed', pops, 'deg/frame', 25.0, 12)
    report('reach miss', miss, 'blocks', 0.6)
    report('pole near limb axis (1-strength)', weak, '', 0.8)
    report('thigh roll', kneedir, 'deg', 60.0)
    report('upper-arm twist', twists, 'deg', 100.0)


if __name__ == '__main__':
    main()
