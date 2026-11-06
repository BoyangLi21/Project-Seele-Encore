"""Author the legs of the armed kneel-to-prone: python rifle_stance.py out.json [sheet.png]

The capture's stance clip folds the front leg up behind the hip, the foot passing
through the far thigh, and leaves the rear leg hanging in the air.  Here the upper
body stays as captured and only the pelvis height and the legs are replaced from
stance 1 (kneeling) to stance 3 (prone): the weight goes forward, the front foot
rolls onto its toes and drags back along the ground beside the rear leg until both
knees are down, then the hips lower and both legs lie out behind.

Everything is relative to the ground at y=0, so the clip stands where it is drawn
and the runtime has nothing to correct.  Written as an overlay of the pelvis and
leg channels only, in the {bones, frames} form EvaBodyPose reads.
"""
import json
import math
import sys

import numpy as np

import body as B
import gait_clip as G
import rig as R
import scene as S

FIRST, LAST = 60, 180       # clip frames of stance 1 and stance 3
FRAMES_PER_STANCE = 60
KNEE_REST, ANKLE_REST = 4.4, 3.4   # heights of a knee and ankle lying on the ground
BONES = ['leg_l', 'shin_l', 'ankle_l', 'foot_l', 'leg_r', 'shin_r', 'ankle_r', 'foot_r']


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def curve(keys, s):
    """Catmull-Rom through (s, value) keys, flat at both ends."""
    xs = [k[0] for k in keys]
    if s <= xs[0]:
        return np.asarray(keys[0][1], float)
    if s >= xs[-1]:
        return np.asarray(keys[-1][1], float)
    i = max(j for j in range(len(xs) - 1) if xs[j] <= s)
    p = [np.asarray(keys[max(0, min(len(keys) - 1, j))][1], float) for j in (i - 1, i, i + 1, i + 2)]
    x0, x1 = xs[i], xs[i + 1]
    u = (s - x0) / (x1 - x0)
    # Tangents per unit stance, so uneven keys stay smooth.
    t1 = (p[2] - p[0]) / (xs[min(i + 1, len(xs) - 1)] - xs[max(i - 1, 0)] or 1)
    t2 = (p[3] - p[1]) / (xs[min(i + 2, len(xs) - 1)] - xs[i] or 1)
    h = x1 - x0
    return ((2 * u**3 - 3 * u**2 + 1) * p[1] + (u**3 - 2 * u**2 + u) * h * t1
            + (-2 * u**3 + 3 * u**2) * p[2] + (u**3 - u**2) * h * t2)


class Path:
    def __init__(self, raw):
        # Pelvis height above the ground.
        self.hip_y = [(1.0, raw['hip'][0]), (1.3, raw['hip'][0] - .9), (1.7, 16.6), (2.0, 14.6),
                      (2.4, 10.6), (2.75, 8.2), (3.0, 7.2)]
        # Front foot: stays down, heel lifts, then drags back on its toes beside the rear leg.
        a, b = raw['ankle_l']
        self.ankle_l = [(1.0, a), (1.14, a + [0, .1, -.2]), (1.3, (6.0, 6.6, 7.6)), (1.5, (6.4, 7.2, 1.0)),
                        (1.7, (6.7, 6.6, -7.4)), (1.9, (6.9, 4.9, -14.4)), (2.1, (7.0, 3.7, -18.0)),
                        (2.6, (7.2, 3.6, -19.6)), (3.0, (7.5, 3.6, -20.4))]
        a, b = raw['ankle_r']
        self.ankle_r = [(1.0, a), (1.5, (-6.1, 2.5, -18.0)), (2.0, (-6.7, 3.3, -18.6)), (2.6, (-7.2, 3.6, -19.6)), (3.0, (-7.5, 3.6, -20.4))]
        # Toes-up pitch of the sole in the world: flat, onto the toes, over onto the instep.
        self.pitch_l = [(1.0, 0), (1.14, -6), (1.3, -38), (1.5, -72), (1.7, -108), (1.9, -122), (2.2, -132), (3.0, -132)]
        self.pitch_r = [(1.0, raw['pitch'][0]), (2.2, -132), (3.0, -132)]
        # Knee aim: forward over a raised thigh, swinging down under a thigh lying back.
        # Lying, the knees turn out: on their armour they would hold the belly off the ground.
        self.pole_l = [(1.0, (.05, .25, 1)), (1.5, (.2, -.1, 1)), (1.9, (.4, -.9, .7)), (2.4, (.9, -.8, .2)), (3.0, (1.0, -.55, .05))]
        self.pole_r = [(1.0, (-.2, -.7, .7)), (1.9, (-.4, -.9, .6)), (2.4, (-.9, -.8, .2)), (3.0, (-1.0, -.55, .05))]


def measure(actors, solver, clip, bones, world, f):
    rot, pos = G.frame_pose(bones, clip, f)
    m = actors.eva_rig.fk(rot, pos, world)
    pv = actors.eva_rig.pivot
    return rot, pos, m, (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2


def lowest(actors, m, name):
    return min(float((t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min()) for b, t, _ in actors.eva_mesh.parts if b == name)


def pitch_of(q):
    """Toes-up pitch of a foot rotation, by where the toes (model -z) point."""
    f = R.qmat(q) @ np.array([0, 0, -1.0])
    return math.degrees(math.atan2(f[1], f[2]))


def solve_leg(actors, solver, side, rot, pos, world, ankle, q_foot, pole):
    m = actors.eva_rig.fk(rot, pos, world)
    limb = solver.limbs['leg_' + side]
    hip = B.point(m['torso_lower'], actors.eva_rig.pivot['leg_' + side])
    qu, ql, qw, ang, err = limb.solve(hip, ankle, pole, B.mat_rot(m['torso_lower']))
    rot['leg_' + side], rot['shin_' + side] = qu, ql
    # The foot bone carries it, as in the capture: the runtime rests a lying foot relative to the ankle bone.
    rot['ankle_' + side] = np.array([1.0, 0, 0, 0])
    rot['foot_' + side] = R.qmul(R.qconj(R.qmul(qw, ql)), q_foot)
    pos['shin_' + side] = R.Rig.hinge_offset(ql, actors.eva_rig.pivot['shin_' + side], solver.knee[side])
    return ang, err


def main():
    out = sys.argv[1]
    actors = S.Actors()
    solver = B.EvaBody(actors.eva_rig)
    data = json.load(open(G.BODY, encoding='utf8'))
    block = data['stance_clips_by_rig']['1']
    bones, clip = block['bones'], block['clips']['rifle_stance']
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    pv = actors.eva_rig.pivot

    def ends(f):
        rot, pos, m, hip = measure(actors, solver, clip, bones, world, f)
        ground = min(lowest(actors, m, b) for b in ('foot_l', 'foot_r', 'shin_l', 'shin_r'))
        return {'hip': hip[1] - ground, 'ground': ground,
                'ankle_l': B.point(m['ankle_l'], pv['ankle_l']) - [0, ground, 0],
                'ankle_r': B.point(m['ankle_r'], pv['ankle_r']) - [0, ground, 0],
                'q_l': B.mat_rot(m['foot_l']), 'q_r': B.mat_rot(m['foot_r'])}

    first, last = ends(FIRST), ends(LAST)
    raw = {'hip': (first['hip'], last['hip']),
           'ankle_l': (first['ankle_l'], last['ankle_l'] * [1, 0, 1] + [0, 3.6, 0]),
           'ankle_r': (first['ankle_r'], last['ankle_r'] * [1, 0, 1] + [0, 3.6, 0]),
           'pitch': (pitch_of(first['q_r']), pitch_of(last['q_r']))}
    print('kneel: hip %.2f ankle_l %s ankle_r %s rear pitch %.0f; prone: hip %.2f pitch %.0f' % (
        first['hip'], np.round(first['ankle_l'], 2), np.round(first['ankle_r'], 2), raw['pitch'][0], last['hip'], raw['pitch'][1]))
    path = Path(raw)

    def lying_ankle(side, hip):
        """Where the ankle lies with the knee on the ground under this hip: reachable by construction."""
        limb = solver.limbs['leg_' + side]
        thigh, shin = np.linalg.norm(limb.a) * S.SCALE, np.linalg.norm(limb.b) * S.SCALE
        sign = 1 if side == 'l' else -1
        kx, ax = sign * 9.5, sign * 10.5
        kz = hip[2] - math.sqrt(max(0.0, thigh**2 - (hip[1] - KNEE_REST)**2 - (hip[0] - kx)**2))
        return np.array([ax, ANKLE_REST, kz - math.sqrt(max(0.0, shin**2 - (KNEE_REST - ANKLE_REST)**2 - (ax - kx)**2))])

    def pose(f, offset):
        """Solve one frame with the pelvis dropped by offset; feet are set on the ground as they arrive."""
        s = f / FRAMES_PER_STANCE
        rot, pos, m, hip = measure(actors, solver, clip, bones, world, f)
        pos['root'] = pos['root'] + np.array([0, (float(curve(path.hip_y, s)) - offset - hip[1]) / S.SCALE, 0])
        q_l = R.qslerp(first['q_l'], B.foot_q(0, float(curve(path.pitch_l, s))), smooth((s - 1) / .12))
        q_r = R.qslerp(first['q_r'], B.foot_q(0, float(curve(path.pitch_r, s))), smooth((s - 1) / .3))
        info = {}
        for side, q, ankle, pole in (('l', q_l, path.ankle_l, path.pole_l), ('r', q_r, path.ankle_r, path.pole_r)):
            hip_at = B.point(actors.eva_rig.fk(rot, pos, world)['torso_lower'], pv['leg_' + side])
            at = curve(ankle, s) + (lying_ankle(side, hip_at) - curve(ankle, s)) * smooth((s - 1.85) / .6)
            for _ in range(2):
                info[side] = solve_leg(actors, solver, side, rot, pos, world, at, q, curve(pole, s))
                posed = actors.eva_rig.fk(rot, pos, world)
                low = min(lowest(actors, posed, 'foot_' + side), lowest(actors, posed, 'shin_' + side))
                # Never under the ground; lying, resting on it.
                at[1] -= min(low, 0) + max(low, 0) * smooth((s - 1.85) / .25)
            info[side] = solve_leg(actors, solver, side, rot, pos, world, at, q, curve(pole, s))
        return rot, pos, actors.eva_rig.fk(rot, pos, world), info

    LEGS = ('foot_l', 'foot_r', 'shin_l', 'shin_r', 'leg_l', 'leg_r')
    offsets = np.zeros(LAST - FIRST + 1)
    for width in (7, 4, 2):
        low = np.array([min(lowest(actors, pose(f, offsets[f - FIRST])[2], b) for b in LEGS) for f in range(FIRST, LAST + 1)])
        low[0] = 0
        print('fit width', width, 'low at s=2,2.5,3:', np.round(low[[60, 90, 120]], 2), 'offsets', np.round(offsets[[60, 90, 120]], 2))
        kernel = np.hanning(2 * width + 3)[1:-1]
        kernel /= kernel.sum()
        offsets += np.convolve(np.pad(low, width, mode='edge'), kernel, 'valid') * np.minimum(1, np.arange(len(low)) / 6)
    frames, rows = [], []
    prev = None
    for f in range(FIRST, LAST + 1):
        s = f / FRAMES_PER_STANCE
        rot, pos, m, info = pose(f, offsets[f - FIRST])
        low = {b: lowest(actors, m, b) for b in LEGS}
        w = {b: B.mat_rot(m[b]) for b in BONES if b in m}
        speed = 0 if prev is None else max(2 * math.degrees(math.acos(min(1, abs(float(np.dot(w[b], prev[b])))))) for b in w)
        if prev is not None and speed > 6:
            print('   fast s %.2f' % s, {b: round(2 * math.degrees(math.acos(min(1, abs(float(np.dot(w[b], prev[b])))))), 1) for b in w})
        prev = w
        rows.append((s, min(low.values()), speed, info['l'][0], info['l'][1], info['r'][0], info['r'][1], low['leg_l'], low['leg_r'], low['shin_l'], low['shin_r'], low['foot_l'], low['foot_r'],
                     B.point(m['leg_l'], pv['leg_l'])[1]))
        p = pos['root']
        row = {'root_m': [round(float(x), 6) for x in np.array([-p[0], p[1], p[2]]) * 16 / 112], 'rotation_wxyz': [],
               'bone_position_xyz': {}}
        for n in BONES:
            row['rotation_wxyz'].append([round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))])
        for n in ('shin_l', 'shin_r'):
            t = pos[n]
            row['bone_position_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    a = np.array(rows)
    print('lowest leg point %.2f .. %.2f   fastest joint %.1f deg/frame   worst reach error l %.2f r %.2f' % (
        a[:, 1].min(), a[:, 1].max(), a[:, 2].max(), a[:, 4].max(), a[:, 6].max()))
    for row in rows[::10]:
        print('  s %.2f low %5.2f speed %4.1f knee l %5.1f r %5.1f  thigh %5.1f %5.1f shin %5.1f %5.1f foot %5.1f %5.1f hip %5.1f' % (row[0], row[1], row[2], row[3], row[5], row[7], row[8], row[9], row[10], row[11], row[12], row[13]))
    doc = {'source': 'Project SEELE original legs (tools/finale/rifle_stance.py), MIT', 'clip': 'rifle_stance',
           'first_frame': FIRST, 'bones': BONES, 'frames': frames}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, len(frames), 'frames')
    if len(sys.argv) > 2:
        images = []
        size = (320, 280)
        for f in list(range(FIRST, LAST + 1, 10)) + [LAST]:
            s = f / FRAMES_PER_STANCE
            rot, pos, m, hip = measure(actors, solver, clip, bones, world, f)
            row = frames[f - FIRST]
            p = np.array(row['root_m']) * 112
            pos['root'] = np.array([-p[0], p[1], p[2]]) / 16
            for i, n in enumerate(BONES):
                rot[n] = R.clip_to_baked(row['rotation_wxyz'][i])
            for n, v in row['bone_position_xyz'].items():
                pos[n] = np.array([-v[0], v[1], v[2]]) / 16
            m = actors.eva_rig.fk(rot, pos, world)
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-100, 26, 20), (0, 14, 0), 42, size), groups, label='s=%.2f' % s, ground=(-64, 64, -64, 64)))
            images.append(R.render(R.Camera((-40, 60, -90), (0, 10, 0), 42, size), groups, label='rear s=%.2f' % s, ground=(-64, 64, -64, 64)))
        R.sheet(images, 6).save(sys.argv[2])


if __name__ == '__main__':
    main()
