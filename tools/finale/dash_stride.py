"""Author the dash: python dash_stride.py out.json [sheet.png]

Long, low and heavy.  The body leans into the run with the chest open and the
head up.  Each leg reaches far ahead close to the ground, comes down under
the body, drives back until it is straight and swings through low: the knee
never climbs and the heel never kicks up.  The arms stay tight to the ribs,
elbows bent, pumping straight fore and aft.  The wildness is in the length of
the stride and the ground thrown up behind it, not in flung limbs.  Only the
channels the game does not pose (fingers, weapons) stay captured.  Written as
an overlay in the {bones, frames} form EvaBodyPose reads.
"""
import json
import math
import sys

import numpy as np

import body as B
import gait_clip as G
import rig as R
import scene as S

STRIDE_BLOCKS = 64.0        # EvaSprintR50.STRIDE_BLOCKS: travel per cycle, so a planted foot stays planted
STANCE = .2                 # share of the cycle a foot is down
TOUCHDOWN = {'l': .04, 'r': .54}
PELVIS_TILT, CHEST_LEAN, HEAD_LEAN = 20.0, 29.0, 9.0     # degrees forward from upright
PELVIS_TURN, CHEST_TURN = 8.0, 12.0                      # yaw against each other
PELVIS_ROLL, CHEST_ROLL = 3.0, 3.0                       # the side of the stance foot drops
BOUNCE = 2.0                                             # chest dips this far (degrees) at each footfall
HIP_MEAN, HIP_SWING, HIP_SURGE = 33.2, 1.5, .8           # blocks

# One arm swing from the forward extreme, hand from the shoulder in the chest's frame: out, up, forward.
SWING = [(.2, -7.5, 7.5), (.9, -11.0, .5), (1.2, -10.5, -6.5), (.9, -11.0, .5)]
ARM_PHASE = .04             # the right arm is forward as the left foot lands
BONES = ['torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']
# One stride of a leg from touchdown: phase, ankle height, ankle ahead of the entity, toes-up pitch of the sole.
ON_GROUND = STRIDE_BLOCKS * STANCE
STRIDE = [(0, 6.2, 6.5, 8), (.07, 5.8, 6.5 - ON_GROUND * .35, 0), (.14, 6.7, 6.5 - ON_GROUND * .7, -14),
          (.2, 8.0, 6.5 - ON_GROUND, -42), (.31, 10.5, -16.5, -68), (.43, 12.5, -15.5, -84), (.57, 11.5, -3.0, -66),
          (.7, 11.0, 12.0, -20), (.84, 10.5, 17.5, 8), (.94, 7.4, 12.5, 10), (1.0, 6.2, 6.5, 8)]


def swing(v):
    """Closed Catmull-Rom through the swing keys; v wraps at 1."""
    v = (v % 1.0) * len(SWING)
    i = int(v)
    t = v - i
    p = [np.array(SWING[(i + k) % len(SWING)], float) for k in (-1, 0, 1, 2)]
    return .5 * (2 * p[1] + (p[2] - p[0]) * t + (2 * p[0] - 5 * p[1] + 4 * p[2] - p[3]) * t * t
                 + (3 * p[1] - p[0] - 3 * p[2] + p[3]) * t * t * t)


def stride_at(p):
    """Ankle height, ankle ahead, sole pitch at a leg's own phase."""
    p %= 1.0
    keys = STRIDE
    i = max(k for k in range(len(keys) - 1) if keys[k][0] <= p)

    def key(k):
        # Wrapped neighbours: the first and last keys are the same pose.
        n = len(keys) - 1
        q = keys[k % n]
        return np.array(q, float) + [k // n, 0, 0, 0]
    a, b, c, d = key(i - 1), key(i), key(i + 1), key(i + 2)
    h = c[0] - b[0]
    t = (p - b[0]) / h
    m1 = (c[1:] - a[1:]) / (c[0] - a[0]) * h
    m2 = (d[1:] - b[1:]) / (d[0] - b[0]) * h
    return ((2 * t**3 - 3 * t**2 + 1) * b[1:] + (t**3 - 2 * t**2 + t) * m1
            + (-2 * t**3 + 3 * t**2) * c[1:] + (t**3 - t**2) * m2)


def lowest(actors, m, name):
    return min(float((t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min()) for b, t, _ in actors.eva_mesh.parts if b == name)


def main():
    out = sys.argv[1]
    actors = S.Actors()
    solver = B.EvaBody(actors.eva_rig)
    rig = actors.eva_rig
    pv = rig.pivot
    data = json.load(open(G.BODY, encoding='utf8'))
    block = data['stance_clips_by_rig']['1']
    bones, clip = block['bones'], block['clips']['dash_run']
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    count = len(clip['frames'])
    period = count - 1
    frames, rows, legs, posed = [], [], [], []
    ident = np.array([1.0, 0, 0, 0])
    for f in range(count):
        u = f / period
        rot, pos = G.frame_pose(bones, clip, f)
        raw = rig.fk(rot, pos, world)
        arm = math.cos(2 * math.pi * (u - ARM_PHASE))              # +1: right arm forward
        low = math.cos(4 * math.pi * (u - TOUCHDOWN['l'] - STANCE * .55))     # +1: mid-stance of either foot
        stance_left = math.cos(2 * math.pi * (u - TOUCHDOWN['l'] - STANCE * .55))
        root_q = B.mat_rot(raw['root'])
        pelvis = B.body_q(0, PELVIS_TILT, PELVIS_ROLL * stance_left, -PELVIS_TURN * arm)
        rot['torso_lower'] = R.qmul(R.qconj(root_q), pelvis)
        chest = B.body_q(0, CHEST_LEAN + BOUNCE * low, -CHEST_ROLL * stance_left, CHEST_TURN * arm)
        head = B.body_q(0, HEAD_LEAN, 0, 3 * arm)
        neck = R.qslerp(chest, head, .5)
        rot['torso_upper'] = R.qmul(R.qconj(pelvis), chest)
        rot['aim_pitch'] = ident
        rot['neck'] = R.qmul(R.qconj(chest), neck)
        rot['head'] = R.qmul(R.qconj(neck), head)
        for s, sign in (('l', -1), ('r', 1)):
            forward = arm if s == 'r' else -arm
            rot['clavicle_' + s] = R.qmul(R.qz(math.radians(sign * (2.5 + 4 * forward))), R.qy(math.radians(sign * (3 + 12 * forward))))
        m = rig.fk(rot, pos, world)
        now = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
        target = np.array([.9 * stance_left, HIP_MEAN - HIP_SWING * low, 1.0 + HIP_SURGE * math.sin(4 * math.pi * (u - TOUCHDOWN['l']))])
        pos['root'] = pos['root'] + (target - now) / S.SCALE
        for s, side in (('l', 1.0), ('r', -1.0)):
            m = rig.fk(rot, pos, world)
            ankle_y, ankle_z, pitch = stride_at(u - TOUCHDOWN[s])
            ankle = np.array([side * (3.6 + 1.2 * math.sin(2 * math.pi * (u - TOUCHDOWN[s]) - 1.0)), ankle_y, ankle_z])
            limb = solver.limbs['leg_' + s]
            pole = np.array([side * .25, .15, 1.0])
            qu, ql, qw, ang, err = limb.solve(B.point(m['torso_lower'], pv['leg_' + s]), ankle, pole, B.mat_rot(m['torso_lower']))
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['ankle_' + s] = ident
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), B.foot_q(0, float(pitch)))
            pos['shin_' + s] = R.Rig.hinge_offset(ql, pv['shin_' + s], solver.knee[s])
            legs.append((f, s, ang, err))
        for s, side in (('l', 1.0), ('r', -1.0)):
            m = rig.fk(rot, pos, world)
            basis = R.qmat(B.mat_rot(m['torso_upper']))
            shoulder = B.point(m['clavicle_' + s], pv['arm_' + s])
            local = swing(u - ARM_PHASE + (0 if s == 'r' else .5))
            # The chest's forward is its model -z, its left is model -x.
            target_hand = shoulder + basis @ np.array([-side * local[0], local[1], -local[2]])
            pole = basis @ np.array([-side * .25, -.2, 1.0])
            limb = solver.limbs['arm_' + s]
            qu, ql, qw, ang, err = limb.solve(shoulder, target_hand, pole, B.mat_rot(m['clavicle_' + s]))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, pv['forearm_' + s], solver.elbow[s])
            rot['wrist_' + s] = R.qx(math.radians(10))
            rot['hand_' + s] = ident
            rows.append((f, s, ang, err))
        m = rig.fk(rot, pos, world)
        posed.append((rot, pos, m))
        p = pos['root']
        row = {'root_m': [round(float(x), 6) for x in np.array([-p[0], p[1], p[2]]) * 16 / 112], 'rotation_wxyz': [],
               'bone_position_xyz': {}}
        for n in BONES:
            row['rotation_wxyz'].append([round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))])
        for n in ('forearm_l', 'forearm_r', 'shin_l', 'shin_r'):
            t = pos[n]
            row['bone_position_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    a = np.array([(r[2], r[3]) for r in rows])
    print('elbow bend %.0f..%.0f  worst reach error %.2f' % (a[:, 0].min(), a[:, 0].max(), a[:, 1].max()))
    a = np.array([(r[2], r[3]) for r in legs])
    print('knee bend %.0f..%.0f  worst reach error %.2f' % (a[:, 0].min(), a[:, 0].max(), a[:, 1].max()))
    for f in range(0, count, 5):
        m = posed[f][2]
        print('  frame %2d soles %5.2f %5.2f  hip %.1f' % (f, lowest(actors, m, 'foot_l'), lowest(actors, m, 'foot_r'), B.point(m['leg_l'], pv['leg_l'])[1]))
    fastest = (0, '')
    for i in range(1, count):
        for b in BONES:
            d = abs(float(np.dot(B.mat_rot(posed[i][2][b]), B.mat_rot(posed[i - 1][2][b]))))
            fastest = max(fastest, (2 * math.degrees(math.acos(min(1, d))), '%s@%d' % (b, i)))
    print('fastest joint %.1f deg/frame %s' % fastest)
    doc = {'source': 'Project SEELE original dash (tools/finale/dash_stride.py), MIT', 'clip': 'dash_run',
           'first_frame': 0, 'bones': BONES, 'frames': frames}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, len(frames), 'frames')
    if len(sys.argv) > 2:
        images = []
        for k in range(10):
            f = int(k * count / 10)
            groups = [actors.eva_mesh.triangles(posed[f][2], np.eye(4))]
            images.append(R.render(R.Camera((-100, 30, 10), (0, 28, 2), 40, (260, 320)), groups, label='frame %d' % f, ground=(-60, 60, -60, 60)))
        for k in range(10):
            f = int(k * count / 10)
            groups = [actors.eva_mesh.triangles(posed[f][2], np.eye(4))]
            images.append(R.render(R.Camera((-48, 30, 92), (0, 28, 2), 40, (260, 320)), groups, label='front %d' % f, ground=(-60, 60, -60, 60)))
        R.sheet(images, 10).save(sys.argv[2])


if __name__ == '__main__':
    main()
