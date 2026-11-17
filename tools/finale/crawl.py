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

2026-11-17. This is the crawl of 2026-11-06 again (in the packs R60 to R62), which the owner chose over the one that
lay the body on its belly with its knees and elbows turned out (2026-11-13, R63), with the three things he said of
it mended: "the ankles, certainly; the hands must not look as if they felt their way forward; the back and the
stride must not writhe so: human and reasonable will do."
  ankles  A foot was held at one heading in the world while its shin rolled with the knee that was drawn up and
          out: the ankle was twisted by the difference, 50 to 74 degrees. A foot now lies in line with its own shin,
          toes back, and can only be pointed. The legs trail nearly straight and are drawn up 4 blocks where they
          were drawn 6: the knee of a leg drawn further has nowhere to go but out to the side (it cannot go into
          the ground), which is the frog's leg. So the feet no longer hold still on the ground: they are dragged 2
          blocks of every 6, as the legs of a body pulled along on its arms are.
  hands   A hand was lifted 4.6 blocks, reached forward and patted down with the forearm in the air behind it. The
          body is now pulled along on its forearms: the hand is set down ahead of the shoulder, towards the body's
          middle, and stays where it is while the body goes over it; the forearm lies on the ground behind it and
          the elbow rests on the ground, outside the shoulder, where the two bones of the arm put it; then the arm
          is carried forward close to the ground.
  trunk   The chest swung 14 degrees either way and rolled 15, the pelvis 9 and 8 against it. Now 5 and 6, 3 and 3:
          a body that turns a little into each pull and is otherwise straight.
The armed crawl is as it was.
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
SHOULDER = np.zeros(3)   # half the distance between the shoulders, their height, how far ahead they are (found in main)
STRIDE = 12.0            # blocks a cycle, set by the gait clock
BONES = ['torso_lower', 'torso_upper', 'neck', 'head', 'clavicle_l', 'clavicle_r', 'arm_l', 'forearm_l', 'wrist_l',
         'hand_l', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'leg_l', 'shin_l', 'ankle_l', 'foot_l',
         'leg_r', 'shin_r', 'ankle_r', 'foot_r']
PELVIS_PITCH, CHEST_PITCH, HEAD_LEAN = 86.0, 76.0, 6.0
PELVIS_SWING, CHEST_SWING = 3.0, 5.0      # yaw, against each other (9 and 14 up to R62)
CHEST_LEAD = 0.0                          # degrees the left shoulder is held forward
PELVIS_ROLL, CHEST_ROLL = 3.0, 6.0        # about the spine (8 and 15 up to R62)
HIP_Y, HIP_Z = 8.0, 7.4                   # (the hips' height before the body is set on the ground: 6.8 up to R62)
SWAY = .4                                 # blocks the hips go to the side (.8 up to R62)
SURGE, HEAVE = 1.2, .4                    # two lunges a cycle: blocks forward, blocks up (1.8 and .8 up to R62)
HAND_FAR, HAND_OUT, HAND_Y, HAND_LIFT = 32.0, 8.2, 2.6, 4.6      # the armed crawl's, and the crawl's up to R62
FOOT_DRAWN, FOOT_OUT, FOOT_Y, FOOT_LIFT = -15.0, 10.0, 3.6, 2.4
TOE_PITCH = -128.0
# The crawl on the forearms. Where the wrist is set down: ahead of where the shoulder is carried, and from the
# body's middle; how high the wrist's centre and the elbow's lie over the ground; how high they are carried forward.
# (The elbow's centre at 2.8, the forearm level: the game then lifts the elbow by 1.2, since the elbow's own
# surface is under the ground at that. 3.9 is the elbow lying on the ground; the forearm slopes 8 degrees to it.)
WRIST_AHEAD, WRIST_OUT, WRIST_Y, ELBOW_Y = 10.5, 3.6, 2.6, 3.9
WRIST_LIFT, ELBOW_LIFT = 1.8, 1.2
# The legs: how far behind the hips the ankle of a drawn leg is and how far it goes back from there; how far apart
# the feet trail, and how much further out a drawn foot is; the ankle's height; the heading of a knee from straight
# down the body's length, how much further out it is drawn, and how high its centre stays over the ground (it is
# turned out until it does); how far the foot is turned down from square to its shin (90: in line with it).
LEG_DRAWN, LEG_STROKE, FEET_OUT, FEET_DRAW, ANKLE_Y = -25.6, 3.5, 6.0, 1.5, 3.0
KNEE_OUT, KNEE_DRAW, KNEE_Y = 25.0, 30.0, 2.4
FOOT_POINT = 84.0


ARMED = len(sys.argv) > 3 and sys.argv[3] == 'armed'
if ARMED:
    # The left hand is on the fore-end, far ahead: the arm is nearly straight, and with
    # a straight arm the elbow cannot come down.  A rifleman lies turned onto the gun,
    # left shoulder forward, and the chest stays near that as the body crawls.
    PELVIS_SWING, CHEST_SWING, PELVIS_ROLL, CHEST_ROLL = 6.0, 5.0, 6.0, 6.0
    CHEST_LEAD = 8.0
    SURGE, HEAVE, HIP_Y, CHEST_PITCH = 1.2, .4, 7.2, 78.0
    SWAY = .8


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
        info = {}
        rot, pos = G.frame_pose(bones, clip, min(f, len(clip['frames']) - 1))
        raw = rig.fk(rot, pos, world)
        hands = {s: B.mat_rot(raw['hand_' + s]) for s in 'lr'}
        cycle = math.cos(2 * math.pi * u)          # +1: right arm reaching, left knee drawn
        lunge = math.sin(4 * math.pi * u + .6)
        pelvis = spine(-PELVIS_SWING * cycle, PELVIS_PITCH, PELVIS_ROLL * cycle)
        chest = spine(CHEST_SWING * cycle - CHEST_LEAD, CHEST_PITCH - 3 * lunge, -CHEST_ROLL * cycle)
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
            # (The shoulder goes forward with its arm: 10 degrees up to R62 and armed, 5 now.)
            rot['clavicle_' + s] = R.qmul(R.qz(math.radians(sign * (3 + (5 if ARMED else 3) * reach))), R.qy(math.radians(sign * (4 + (10 if ARMED else 5) * reach))))
        m = rig.fk(rot, pos, world)
        hip = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
        target = np.array([SWAY * cycle, HIP_Y + HEAVE * lunge - drop, HIP_Z + SURGE * lunge])
        pos['root'] = pos['root'] + (target - hip) / S.SCALE
        # Legs: the left one pushes as the right arm pulls.
        for s, side, phase in (('l', 1.0, 0.0), ('r', -1.0, .5)):
            m = rig.fk(rot, pos, world)
            v = u + phase
            along, lift = stroke(v, FOOT_DRAWN, FOOT_LIFT)
            drawn = (math.cos(2 * math.pi * v) + 1) / 2
            if ARMED:
                ankle = np.array([side * (FOOT_OUT + 3.6 * drawn), FOOT_Y + lift - drop * 0, along])
                pole = R.qmat(B.heading_q(side * (62 + 24 * drawn))) @ np.array([0, 0, -1.0]) + np.array([0, -.55, 0])
            else:
                # The ankle goes back LEG_STROKE from where it is drawn to while the ground goes back 6, and is
                # drawn forward again: so many blocks behind the hips, which go on and back with the body's lunges.
                back = LEG_STROKE * (1 - drawn)
                hip_now = B.point(m['torso_lower'], pv['leg_' + s])
                ankle = np.array([side * (FEET_OUT + FEET_DRAW * drawn), ANKLE_Y + .6 * lift / max(FOOT_LIFT, 1e-6), hip_now[2] + LEG_DRAWN - back])
                pole = R.qmat(B.heading_q(side * (KNEE_OUT + KNEE_DRAW * drawn))) @ np.array([0, 0, -1.0]) + np.array([0, -.55, 0])
            limb = solver.limbs['leg_' + s]
            hip_at = B.point(m['torso_lower'], pv['leg_' + s])
            qu, ql, qw, ang, err = limb.solve(hip_at, ankle, pole, B.mat_rot(m['torso_lower']))
            if not ARMED:
                # A knee cannot go into the ground: it is turned out until its centre is over it.
                def knee_at(turn):
                    aim = R.qmat(B.heading_q(side * (KNEE_OUT + KNEE_DRAW * drawn + turn))) @ np.array([0, 0, -1.0]) + np.array([0, -.55 * (1 - turn / 70), 0])
                    found = limb.solve(hip_at, ankle, aim, B.mat_rot(m['torso_lower']))
                    probe = dict(rot)
                    probe['leg_' + s], probe['shin_' + s] = found[0], found[1]
                    return B.point(rig.fk(probe, pos, world)['leg_' + s], solver.knee[s])[1], found
                turn = 0.0
                height, found = knee_at(0.0)
                if height < KNEE_Y:
                    lo_t, hi_t = 0.0, 70.0
                    for _ in range(18):
                        turn = (lo_t + hi_t) / 2
                        height, found = knee_at(turn)
                        if height < KNEE_Y:
                            lo_t = turn
                        else:
                            hi_t = turn
                    turn = hi_t
                    height, found = knee_at(turn)
                qu, ql, qw, ang, err = found
                info['knee_out_' + s], info['knee_y_' + s] = KNEE_OUT + KNEE_DRAW * drawn + turn, height
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['ankle_' + s] = ident
            # Armed, the foot is held at a heading in the world. Otherwise it lies in line with its own shin, turned
            # down from square to it and no other way: an ankle that only points the foot cannot be twisted.
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), B.foot_q(side * 12, TOE_PITCH)) if ARMED else R.qx(-math.radians(FOOT_POINT))
            info['knee_' + s], info['leg_err_' + s] = ang, err
            pos['shin_' + s] = R.Rig.hinge_offset(ql, pv['shin_' + s], solver.knee[s])
        # Arms: the right hand plants at the start of the cycle.
        for s, side, phase in (('l', 1.0, .5), ('r', -1.0, 0.0)):
            m = rig.fk(rot, pos, world)
            shoulder = B.point(m['clavicle_' + s], pv['arm_' + s])
            limb = solver.limbs['arm_' + s]
            if ARMED:
                along, lift = stroke(u + phase, HAND_FAR, HAND_LIFT)
                target_hand = np.array([side * HAND_OUT, HAND_Y + lift, along])
                pole = np.array([side * .45, -1.0, -.2])
            else:
                # The wrist is set down and stays where it is on the ground while the body goes over it (in the
                # entity's own frame it goes back at the body's pace), then goes forward. The elbow lies on the
                # ground where the upper arm from the shoulder and the forearm from the wrist meet, outside them.
                along, lift = stroke(u + phase, SHOULDER[2] + WRIST_AHEAD, 1.0)
                target_hand = np.array([side * WRIST_OUT, WRIST_Y + WRIST_LIFT * lift, along])
                ey = ELBOW_Y + ELBOW_LIFT * lift
                upper, fore = limb.reach(0.0)[0] * 0 + np.linalg.norm(limb.a) * S.SCALE, np.linalg.norm(limb.b) * S.SCALE
                r1 = math.sqrt(max(.01, upper ** 2 - (shoulder[1] - ey) ** 2))
                r2 = math.sqrt(max(.01, fore ** 2 - (target_hand[1] - ey) ** 2))
                c1, c2 = np.array([shoulder[0], shoulder[2]]), np.array([target_hand[0], target_hand[2]])
                d = float(np.linalg.norm(c2 - c1))
                d = min(max(d, abs(r1 - r2) + .05), r1 + r2 - .05)
                along_line = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
                off = math.sqrt(max(0.0, r1 * r1 - along_line * along_line))
                line = (c2 - c1) / max(float(np.linalg.norm(c2 - c1)), 1e-6)
                across = np.array([line[1], -line[0]])
                if across[0] * side < 0:
                    across = -across
                spot = c1 + line * along_line + across * off
                elbow = np.array([spot[0], ey, spot[1]])
                pole = elbow - shoulder
            qu, ql, qw, ang, err = limb.solve(shoulder, target_hand, pole, B.mat_rot(m['clavicle_' + s]))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, pv['forearm_' + s], solver.elbow[s])
            rot['wrist_' + s] = ident
            m = rig.fk(rot, pos, world)
            if ARMED:
                rot['hand_' + s] = R.qmul(R.qconj(B.mat_rot(m['wrist_' + s])), hands[s])
            else:
                # The hand lies flat as the capture's does, turned the way its forearm points.
                at = B.point(m['forearm_' + s], solver.elbow[s])
                fore = B.point(m['wrist_' + s], pv['wrist_' + s]) - at
                rot['hand_' + s] = R.qmul(R.qconj(B.mat_rot(m['wrist_' + s])), R.qmul(R.qy(math.atan2(fore[0], fore[2])), hands[s]))
                info['elbow_y_' + s], info['elbow_off_' + s] = float(at[1]), float(np.linalg.norm(at - elbow))
                info['planted_' + s] = (u + phase) % 1.0 < .5
            info['elbow_' + s], info['arm_err_' + s] = ang, err
        return rot, pos, rig.fk(rot, pos, world), info

    # Where the shoulders are carried, the body lying still: the arms are set down from there.
    SHOULDER[:] = 0
    still = pose(0, 0.0)[2]
    both = [B.point(still['clavicle_' + s], pv['arm_' + s]) for s in 'lr']
    SHOULDER[:] = [abs(both[0][0] - both[1][0]) / 2, (both[0][1] + both[1][1]) / 2, (both[0][2] + both[1][2]) / 2]
    print('shoulders carried %.1f apart, %.1f high, %.1f ahead' % (2 * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
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
        rot, pos, m, info = pose(f, drops[f])
        posed.append((rot, pos, m, info))
        p = pos['root']
        row = {'root_m': [round(float(x), 6) for x in np.array([-p[0], p[1], p[2]]) * 16 / 112], 'rotation_wxyz': [],
               'bone_position_xyz': {}}
        for n in BONES:
            row['rotation_wxyz'].append([round(float(x), 6) for x in R.baked_to_clip(R.qnorm(rot[n]))])
        for n in ('forearm_l', 'forearm_r', 'shin_l', 'shin_r'):
            t = pos[n]
            row['bone_position_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    fastest, quick = 0, ''
    for i in range(1, FRAMES):
        for b in BONES:
            d = abs(float(np.dot(B.mat_rot(posed[i][2][b]), B.mat_rot(posed[i - 1][2][b]))))
            if 2 * math.degrees(math.acos(min(1, d))) > fastest:
                fastest, quick = 2 * math.degrees(math.acos(min(1, d))), '%s at frame %d' % (b, i)
    print('fastest joint %.1f deg/frame (%s), lowest point %.2f .. %.2f' % (fastest, quick, min(lowest(actors, p[2]) for p in posed), max(lowest(actors, p[2]) for p in posed)))
    if not ARMED:
        on = [p[3] for p in posed]
        for side in 'lr':
            down = [i['elbow_y_' + side] for i in on if i['planted_' + side]]
            print('  arm_%s: elbow bent %.0f..%.0f; while it bears its centre is %.2f..%.2f over the ground, %.2f at most from where it was set; out of reach by %.2f at most' % (
                side, min(i['elbow_' + side] for i in on), max(i['elbow_' + side] for i in on), min(down), max(down),
                max(i['elbow_off_' + side] for i in on if i['planted_' + side]), max(i['arm_err_' + side] for i in on)))
            print('  leg_%s: knee bent %.0f..%.0f, turned out %.0f..%.0f, its centre %.2f..%.2f over the ground; out of reach by %.2f at most' % (
                side, min(i['knee_' + side] for i in on), max(i['knee_' + side] for i in on), min(i['knee_out_' + side] for i in on), max(i['knee_out_' + side] for i in on),
                min(i['knee_y_' + side] for i in on), max(i['knee_y_' + side] for i in on), max(i['leg_err_' + side] for i in on)))
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
