"""Author the dash: python dash_stride.py out.json [sheet.png]

The captured sprint carries its chest 50 degrees over, its head pushed out in
front and its hands low, and its feet barely leave the space under the hips: a
crouched scuttle.  Only its pelvis height and foot contacts stay.  The pelvis
comes up to a runner's tilt, the chest stands up and turns against the stride,
the head looks ahead and the arms pump from chin to hip.  Each leg lands ahead
of the hips, drives back along the ground at the speed of travel, kicks up
behind and comes through with the knee high, so the long flight of the stride
shows two legs split wide.  Written as an overlay in the {bones, frames} form
EvaBodyPose reads.
"""
import json
import math
import sys

import numpy as np

import body as B
import gait_clip as G
import rig as R
import scene as S

PELVIS_TILT, CHEST_LEAN, HEAD_LEAN = 13.0, 17.0, 5.0     # degrees forward from upright
PELVIS_TURN, CHEST_TURN = 7.0, 13.0                      # yaw against the stride
BOUNCE = 1.5                                             # chest dips this far (degrees) at each footfall
ARM_PHASE = .04                                          # the right arm is forward as the left foot lands
HIP_LIFT = .9                                            # blocks

# One arm swing, hand from the shoulder in the chest's frame: out, up, forward.
SWING = [(.8, -6.5, 10.0), (1.6, -12.5, 2.0), (1.8, -10.0, -8.5), (1.2, -11.5, 3.0)]
BONES = ['torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']
# One stride of a leg from touchdown: phase, ankle height, ankle ahead of the entity, toes-up pitch of the sole.
# Over the stance the ankle runs back at the speed of travel: 100 blocks a cycle.
STRIDE = [(0, 6.3, 7.0, 16), (.05, 5.8, 2.0, 0), (.10, 5.9, -3.0, -8), (.16, 7.6, -9.0, -38), (.30, 17.0, -16.5, -88),
          (.46, 23.0, -5.0, -74), (.62, 19.5, 10.0, -36), (.78, 16.5, 17.0, 4), (.92, 10.0, 13.5, 16), (1.0, 6.3, 7.0, 16)]
TOUCHDOWN = {'l': .04, 'r': .60}   # phase of the cycle, the clip's own contacts


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
        lap = k // n
        q = keys[k % n]
        return np.array(q, float) + [lap, 0, 0, 0]
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
    frames, rows, legs = [], [], []
    posed = []
    for f in range(count):
        u = f / period
        rot, pos = G.frame_pose(bones, clip, f)
        raw = rig.fk(rot, pos, world)
        hip = (B.point(raw['leg_l'], pv['leg_l']) + B.point(raw['leg_r'], pv['leg_r'])) / 2
        stride = math.cos(2 * math.pi * (u - ARM_PHASE))
        footfall = math.cos(4 * math.pi * (u - ARM_PHASE))
        root_q = B.mat_rot(raw['root'])
        pelvis = B.body_q(0, PELVIS_TILT, 0, -PELVIS_TURN * stride)
        rot['torso_lower'] = R.qmul(R.qconj(root_q), pelvis)
        chest_world = B.body_q(0, CHEST_LEAN + BOUNCE * footfall, 0, CHEST_TURN * stride)
        head_world = B.body_q(0, HEAD_LEAN, 0, 0)
        neck_world = R.qslerp(chest_world, head_world, .5)
        rot['torso_upper'] = R.qmul(R.qconj(pelvis), chest_world)
        rot['aim_pitch'] = np.array([1.0, 0, 0, 0])
        rot['neck'] = R.qmul(R.qconj(chest_world), neck_world)
        rot['head'] = R.qmul(R.qconj(neck_world), head_world)
        for s, sign in (('l', -1), ('r', 1)):
            forward = stride if s == 'r' else -stride
            rot['clavicle_' + s] = R.qmul(R.qz(math.radians(sign * 1.5)), R.qy(math.radians(sign * (3 + 6 * forward))))
        # The hips stay where the legs had them, a little higher.
        posed_now = rig.fk(rot, pos, world)
        now = (B.point(posed_now['leg_l'], pv['leg_l']) + B.point(posed_now['leg_r'], pv['leg_r'])) / 2
        pos['root'] = pos['root'] + (hip + np.array([0, HIP_LIFT, 0]) - now) / S.SCALE
        for s, side in (('l', 1.0), ('r', -1.0)):
            m = rig.fk(rot, pos, world)
            ankle_y, ankle_z, pitch = stride_at(u - TOUCHDOWN[s])
            ankle = np.array([side * (4.2 + .9 * math.sin(2 * math.pi * (u - TOUCHDOWN[s]) - 1.0)), ankle_y, ankle_z])
            q_foot = B.foot_q(0, float(pitch))
            limb = solver.limbs['leg_' + s]
            pole = np.array([side * .22, .1, 1.0])
            qu, ql, qw, ang, err = limb.solve(B.point(m['torso_lower'], pv['leg_' + s]), ankle, pole, B.mat_rot(m['torso_lower']))
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['ankle_' + s] = np.array([1.0, 0, 0, 0])
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), q_foot)
            pos['shin_' + s] = R.Rig.hinge_offset(ql, pv['shin_' + s], solver.knee[s])
            legs.append((f, s, ang, err))
        for s, side in (('l', 1.0), ('r', -1.0)):
            m = rig.fk(rot, pos, world)
            chest = B.mat_rot(m['torso_upper'])
            shoulder = B.point(m['clavicle_' + s], pv['arm_' + s])
            local = swing(u - ARM_PHASE + (0 if s == 'r' else .5))
            target = shoulder + R.qmat(chest) @ np.array([side * local[0], local[1], -local[2]]) * [-1, 1, 1] * [-1, 1, 1]
            # The chest's forward is its model -z: hands go that way, elbows out and behind.
            pole = R.qmat(chest) @ np.array([side * .45, -.25, 1.0])
            limb = solver.limbs['arm_' + s]
            qu, ql, qw, ang, err = limb.solve(shoulder, target, pole, B.mat_rot(m['clavicle_' + s]))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, pv['forearm_' + s], solver.elbow[s])
            rot['wrist_' + s] = R.qx(math.radians(8))
            rot['hand_' + s] = np.array([1.0, 0, 0, 0])
            rows.append((f, s, ang, err))
        m = rig.fk(rot, pos, world)
        posed.append((rot, pos, m))
        v = B.point(m['torso_upper'], pv['neck']) - B.point(m['leg_l'], pv['leg_l']) / 2 - B.point(m['leg_r'], pv['leg_r']) / 2
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
    # Loop and speed check.
    speed = 0
    for i in range(1, count):
        for b in BONES:
            d = abs(float(np.dot(B.mat_rot(posed[i][2][b]), B.mat_rot(posed[i - 1][2][b]))))
            speed = max(speed, 2 * math.degrees(math.acos(min(1, d))))
    print('fastest joint %.1f deg/frame' % speed)
    doc = {'source': 'Project SEELE original upper body (tools/finale/dash_stride.py), MIT', 'clip': 'dash_run',
           'first_frame': 0, 'bones': BONES, 'frames': frames}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, len(frames), 'frames')
    if len(sys.argv) > 2:
        images = []
        for k in range(10):
            f = int(k * count / 10)
            m = posed[f][2]
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-100, 30, 10), (0, 28, 2), 40, (260, 320)), groups, label='frame %d' % f, ground=(-60, 60, -60, 60)))
        for k in range(0, 10, 2):
            f = int(k * count / 10)
            m = posed[f][2]
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-45, 32, 90), (0, 28, 2), 40, (260, 320)), groups, label='front %d' % f, ground=(-60, 60, -60, 60)))
        R.sheet(images, 10).save(sys.argv[2])


if __name__ == '__main__':
    main()
