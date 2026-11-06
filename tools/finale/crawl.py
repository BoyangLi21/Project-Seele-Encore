"""Author the crawl: python crawl.py out.json [sheet.png|-] [armed]

The captured crawl holds the trunk still and shivers the feet: a worm.  This is
a commando crawl: the right hand reaches and plants as the left knee draws up
and out, the body hauls itself over them, then the other side.  The chest
swings and rolls towards the reaching shoulder, the pelvis swings against it,
the spine snakes between them, and the head stays up looking ahead.  Hands and
feet in contact hold still on the ground: the entity travels 12 blocks a cycle.
Armed, the hands are on the gun and the elbows on the ground, so the body stays
down on its belly and the arms do not hold it up.
Written as an overlay in the {bones, frames} form EvaBodyPose reads.
"""
import json
import math
import sys

import numpy as np

import body as B
import gait_clip as G
import rig as R
import scene as S

FRAMES = 61
STRIDE = 12.0            # blocks a cycle, set by the gait clock
BONES = ['torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']
PELVIS_PITCH, CHEST_PITCH, HEAD_LEAN = 86.0, 76.0, 6.0
PELVIS_SWING, CHEST_SWING = 9.0, 14.0     # yaw, against each other
PELVIS_ROLL, CHEST_ROLL = 8.0, 15.0       # about the spine
HIP_Y, HIP_Z = 6.8, 7.4
SURGE, HEAVE = 1.8, .8                    # two lunges a cycle: blocks forward, blocks up
HAND_FAR, HAND_OUT, HAND_Y, HAND_LIFT = 32.0, 8.2, 2.6, 4.6
FOOT_DRAWN, FOOT_OUT, FOOT_Y, FOOT_LIFT = -15.0, 10.0, 3.6, 2.4
TOE_PITCH = -128.0


ARMED = len(sys.argv) > 3 and sys.argv[3] == 'armed'
if ARMED:
    PELVIS_SWING, CHEST_SWING, PELVIS_ROLL, CHEST_ROLL = 6.0, 9.0, 6.0, 9.0
    SURGE, HEAVE, HIP_Y, CHEST_PITCH = 1.2, .4, 7.2, 78.0


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def stroke(v, far, lift):
    """Along-the-body position and lift of a limb from the moment it plants: held on the ground, then swung forward."""
    v %= 1.0
    if v < .5:
        return far - STRIDE * v, 0.0
    t = (v - .5) / .5
    return far - STRIDE * .5 + STRIDE * .5 * smooth(t), lift * math.sin(math.pi * t)


def spine(yaw, pitch, twist):
    """World rotation of a trunk lying down: swung about the vertical, pitched, rolled about its own length."""
    return R.qmul(R.qmul(B.heading_q(yaw), R.qx(-math.radians(pitch))), R.qy(math.radians(twist)))


def lowest(actors, m):
    # Armed, the rifle rig poses the arms afterwards: only the body and legs lie on the ground.
    return min(float((t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min()) for b, t, _ in actors.eva_mesh.parts
               if not ARMED or b.startswith(('leg_', 'shin_', 'foot_', 'torso_lower')))


def main():
    out = sys.argv[1]
    actors = S.Actors()
    solver = B.EvaBody(actors.eva_rig)
    rig = actors.eva_rig
    pv = rig.pivot
    data = json.load(open(G.BODY, encoding='utf8'))
    block = data['stance_clips_by_rig']['1']
    bones, clip = block['bones'], block['clips']['prone_crawl']
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    period = FRAMES - 1
    ident = np.array([1.0, 0, 0, 0])

    def pose(f, drop):
        u = f / period
        rot, pos = G.frame_pose(bones, clip, min(f, len(clip['frames']) - 1))
        raw = rig.fk(rot, pos, world)
        hands = {s: B.mat_rot(raw['hand_' + s]) for s in 'lr'}
        cycle = math.cos(2 * math.pi * u)          # +1: right arm reaching, left knee drawn
        lunge = math.sin(4 * math.pi * u + .6)
        pelvis = spine(-PELVIS_SWING * cycle, PELVIS_PITCH, PELVIS_ROLL * cycle)
        chest = spine(CHEST_SWING * cycle, CHEST_PITCH - 3 * lunge, -CHEST_ROLL * cycle)
        head = B.body_q(0, HEAD_LEAN, 0, 2 * cycle)
        neck = R.qslerp(chest, head, .5)
        root_q = B.mat_rot(raw['root'])
        rot['torso_lower'] = R.qmul(R.qconj(root_q), pelvis)
        rot['torso_upper'] = R.qmul(R.qconj(pelvis), chest)
        rot['aim_pitch'] = ident
        rot['neck'] = R.qmul(R.qconj(chest), neck)
        rot['head'] = R.qmul(R.qconj(neck), head)
        for s, sign, phase in (('l', -1, .5), ('r', 1, 0.0)):
            reach = math.cos(2 * math.pi * (u + phase))
            rot['clavicle_' + s] = R.qmul(R.qz(math.radians(sign * (3 + 5 * reach))), R.qy(math.radians(sign * (4 + 10 * reach))))
        m = rig.fk(rot, pos, world)
        hip = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
        target = np.array([.8 * cycle, HIP_Y + HEAVE * lunge - drop, HIP_Z + SURGE * lunge])
        pos['root'] = pos['root'] + (target - hip) / S.SCALE
        # Legs: the left one pushes as the right arm pulls.
        for s, side, phase in (('l', 1.0, 0.0), ('r', -1.0, .5)):
            m = rig.fk(rot, pos, world)
            v = u + phase
            along, lift = stroke(v, FOOT_DRAWN, FOOT_LIFT)
            drawn = (math.cos(2 * math.pi * v) + 1) / 2
            ankle = np.array([side * (FOOT_OUT + 3.6 * drawn), FOOT_Y + lift - drop * 0, along])
            q_foot = B.foot_q(side * 12, TOE_PITCH)
            pole = R.qmat(B.heading_q(side * (62 + 24 * drawn))) @ np.array([0, 0, -1.0]) + np.array([0, -.55, 0])
            limb = solver.limbs['leg_' + s]
            qu, ql, qw, ang, err = limb.solve(B.point(m['torso_lower'], pv['leg_' + s]), ankle, pole, B.mat_rot(m['torso_lower']))
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['ankle_' + s] = ident
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), q_foot)
            pos['shin_' + s] = R.Rig.hinge_offset(ql, pv['shin_' + s], solver.knee[s])
        # Arms: the right hand plants at the start of the cycle.
        for s, side, phase in (('l', 1.0, .5), ('r', -1.0, 0.0)):
            m = rig.fk(rot, pos, world)
            along, lift = stroke(u + phase, HAND_FAR, HAND_LIFT)
            target_hand = np.array([side * HAND_OUT, HAND_Y + lift, along])
            shoulder = B.point(m['clavicle_' + s], pv['arm_' + s])
            limb = solver.limbs['arm_' + s]
            qu, ql, qw, ang, err = limb.solve(shoulder, target_hand, np.array([side * .45, -1.0, -.2]), B.mat_rot(m['clavicle_' + s]))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, pv['forearm_' + s], solver.elbow[s])
            rot['wrist_' + s] = ident
            m = rig.fk(rot, pos, world)
            rot['hand_' + s] = R.qmul(R.qconj(B.mat_rot(m['wrist_' + s])), hands[s])
        return rot, pos, rig.fk(rot, pos, world)

    low = np.array([lowest(actors, pose(f, 0.0)[2]) for f in range(FRAMES)])
    print('lowest point by itself: %.2f .. %.2f' % (low.min(), low.max()))
    drops = low.copy()
    for width in (5, 3, 2):
        # Fit the body onto the ground, looping round the cycle.
        kernel = np.hanning(2 * width + 3)[1:-1]
        kernel /= kernel.sum()
        drops = np.convolve(np.r_[drops[-width - 1:-1], drops, drops[1:width + 1]], kernel, 'valid')
        residual = np.array([lowest(actors, pose(f, drops[f])[2]) for f in range(FRAMES)])
        drops = drops + residual
    frames, posed = [], []
    for f in range(FRAMES):
        rot, pos, m = pose(f, drops[f])
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
    fastest = 0
    for i in range(1, FRAMES):
        for b in BONES:
            d = abs(float(np.dot(B.mat_rot(posed[i][2][b]), B.mat_rot(posed[i - 1][2][b]))))
            fastest = max(fastest, 2 * math.degrees(math.acos(min(1, d))))
    print('fastest joint %.1f deg/frame, lowest point %.2f .. %.2f' % (fastest, min(lowest(actors, p[2]) for p in posed), max(lowest(actors, p[2]) for p in posed)))
    names = sorted({b for b, _, _ in actors.eva_mesh.parts})
    for f in range(0, FRAMES, 15):
        m = posed[f][2]
        low = {b: min(float((t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3])[:, 1].min()) for bb, t, _ in actors.eva_mesh.parts if bb == b) for b in names}
        print('  frame', f, sorted(((round(v, 1), k) for k, v in low.items()))[:7])
    doc = {'source': 'Project SEELE original crawl (tools/finale/crawl.py), MIT', 'clip': 'prone_crawl_armed' if ARMED else 'prone_crawl',
           'first_frame': 0, 'bones': BONES, 'frames': frames}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, FRAMES, 'frames')
    if len(sys.argv) > 2 and sys.argv[2] != '-':
        images = []
        size = (320, 240)
        for f in range(0, FRAMES - 1, 10):
            m = posed[f][2]
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-90, 30, 16), (0, 8, 4), 36, size), groups, label='side %d' % f, ground=(-70, 70, -70, 70)))
        for f in range(0, FRAMES - 1, 10):
            m = posed[f][2]
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-8, 100, 2), (0, 6, 4), 40, size, up=(0, 0, 1)), groups, label='top %d' % f, ground=(-70, 70, -70, 70)))
        for f in range(0, FRAMES - 1, 10):
            m = posed[f][2]
            groups = [actors.eva_mesh.triangles(m, np.eye(4))]
            images.append(R.render(R.Camera((-40, 26, 100), (0, 8, 10), 36, size), groups, label='front %d' % f, ground=(-70, 70, -70, 70)))
        R.sheet(images, 6).save(sys.argv[2])


if __name__ == '__main__':
    main()
