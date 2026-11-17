"""Author the kick: python kick.py out.json [sheet.png|-] [table]

The kick the frames core had was drawn by the old live-combat code: a hop that changed the feet over and a leg
thrown up to the height of the head in seven ticks, which then stood at its highest through the hold and came down
at a crawl. The owner (2026-11-17): "现在整个踢腿动作感觉卡顿感严重，我想要的是流畅的符合人体而且速度合理的踢腿，
不是踢过去卡一下这种感觉". This is one motion from a stand and back to it, the way a body kicks straight ahead:

  shift    the weight goes over the right foot (the pelvis across, the right knee giving a little), and the left
           heel peels off the ground;
  chamber  the left knee comes up ahead to the height of the hip, the shin folded under it, the pelvis tucking
           under and turning its left side forward, the trunk staying over the standing foot, the right arm
           coming forward and the left going back as they do in a stride;
  thrust   the hip drives forward and the knee opens: the sole goes out ahead at the height of the hip, toes
           drawn back, the trunk leaning away from it as far as keeps the weight over the standing foot;
  fold     the knee closes again nearly as quickly as it opened, the thigh still up (the leg turns round at its
           length without standing there);
  down     the thigh comes down, the foot is set on the ground where it stood, toes first, and the weight comes
           back between the feet.

The standing foot is flat on the ground from first to last and does not move: the right leg is solved to it at
every frame. Nothing is frozen and nothing is thrown: every joint's speed goes up and comes down again.

In the original a Unit's kick is the whole body's: Unit-02's kicks at the Seventh Angel and at the Eva series are
driven from the hip with the trunk thrown back against the leg, and land with the sole. This follows that, on the
ground and from a stand; what it does not have is their run-up and leap.

The feet are where the Unit has them when it stands (STAND, measured from a capture of it standing: the blows'
own clips each stand somewhere else, and a foot slid four blocks over the ground as a blow began), so that a
kick begun from a stand begins with both feet where they are.

Built on the first frame of the knife's forward thrust in Unit-01's private profile (rig 1): its trunk, head and
hands. That frame is not this project's to publish, so what is written is only how each frame differs from it,
bone by bone (the game puts it back on: EvaGameplayMotionR32.addClipsR64).

The frames are laid on the clip so that the row that plays it (EvaMoveTableR64 "kick": start-up, live and
recovery ticks along EvaRowClockR64's curve) gives every part of the motion the time it is written with here, in
ticks at the pilot's speed of one.
"""
import json
import math
import os
import sys

import numpy as np

import body as B
import profile_clip as P
import rig as R
import scene as S

D = math.radians
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])    # the Unit's left, up, ahead
ONE = np.array([1.0, 0, 0, 0])

# The row as EvaMoveTableR64 has it, and where its live part lies about the clip's contact.
STARTUP, LIVE, RECOVERY, LEAD, TAIL = 7, 4, 13, .078, .142
SECONDS, CONTACT, FRAMES = 1.2, .37, 73
# How the Unit stands (a capture of Unit-01 standing, 2026-11-18): each ankle to the left of and ahead of the
# middle, and its height; the hips' height and how far ahead of the middle they and the head are. Toes a little out.
STAND = dict(ankle={'l': (6.0, 2.0), 'r': (-5.9, -.7)}, ankle_high=5.8, toes_out=8.0, hip_high=35.0, hips_ahead=.75, head_ahead=3.9)
BALL = 3.7      # from under the ankle to the ball of the foot, ahead


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ---- the row's curve (EvaRowClockR64.phase, smooth) ---------------------------------------------------------------

def _inner(before, after, pace_before, pace_after):
    if pace_before * pace_after <= 0:
        return 0.0
    a, b = 2 * after + before, after + 2 * before
    return (a + b) / (a / pace_before + b / pace_after)


def _edge(own, nxt, pace_own, pace_next):
    m = ((2 * own + nxt) * pace_own - own * pace_next) / (own + nxt)
    if m * pace_own <= 0:
        return 0.0
    return 3 * pace_own if abs(m) > 3 * abs(pace_own) else m


def row_phase(place, startup=STARTUP, live=LIVE, recovery=RECOVERY, open_=CONTACT - LEAD, close=CONTACT + TAIL):
    end = startup + live + max(1, recovery)
    if place <= 0:
        return 0.0
    if place >= end:
        return 1.0
    x, y = [0, startup, startup + live, end], [0, open_, close, 1]
    h = [x[1] - x[0], x[2] - x[1], x[3] - x[2]]
    d = [(y[1] - y[0]) / h[0], (y[2] - y[1]) / h[1], (y[3] - y[2]) / h[2]]
    m = [_edge(h[0], h[1], d[0], d[1]), _inner(h[0], h[1], d[0], d[1]), _inner(h[1], h[2], d[1], d[2]), _edge(h[2], h[1], d[2], d[1])]
    i = 0 if place <= x[1] else 1 if place <= x[2] else 2
    t = (place - x[i]) / h[i]
    t2, t3 = t * t, t * t * t
    return min(1.0, max(0.0, (2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h[i] * m[i + 1]))


def row_place(phase):
    lo, hi = 0.0, float(STARTUP + LIVE + RECOVERY)
    for _ in range(48):
        mid = .5 * (lo + hi)
        if row_phase(mid) < phase:
            lo = mid
        else:
            hi = mid
    return .5 * (lo + hi)


# ---- the motion, by the tick ---------------------------------------------------------------------------------------
# flex    the left thigh, degrees ahead of straight down; knee: how far the left knee is closed (None: as it stands)
# toe     the left foot's toes above its heel, degrees from the way it stands on the ground
# plant   how much the left foot is on the ground where it stood (on its ball when its toes are down); the thigh
#         and knee are then what reaching it takes
# hip     the pelvis's place added: to the Unit's left, ahead; give: how much further the right knee is closed
#         than it stands, which sets the pelvis's height
# yaw     the pelvis turned to its left; tuck: its top tipped back; hike: its left side lifted
# chest   the chest turned to its left on top of the pelvis; lean: its top tipped back on top of the pelvis
# arm_l, arm_r   the wrist's place added to where it hangs, in the chest's own left, up, ahead
REST = dict(flex=None, knee=None, toe=0, plant=1, hip=(0, 0), give=0, yaw=0, tuck=0, hike=0, chest=0, lean=0, arm_l=(0, 0, 0), arm_r=(0, 0, 0))


def keys(t_out):
    return [
        (0.0, dict(REST)),
        # the weight going over the right foot, the left heel off the ground
        (t_out - 6.2, dict(REST, toe=-24, hip=(-2.3, -.2), give=3, hike=1.0, arm_l=(.3, .3, -1.0), arm_r=(0, .4, 1.2))),
        # the foot leaving the ground, the knee coming forward
        (t_out - 4.7, dict(REST, flex=24, knee=52, toe=-20, plant=0, hip=(-3.9, -.4), give=5, yaw=-1, tuck=2, hike=3, chest=2, lean=1,
                           arm_l=(.9, .8, -2.4), arm_r=(-.3, 1.9, 3.0))),
        # the knee up ahead, the shin folded under it
        (t_out - 3.0, dict(REST, flex=72, knee=110, toe=6, plant=0, hip=(-4.8, -.5), give=7, yaw=-5, tuck=7, hike=5, chest=7, lean=3,
                           arm_l=(1.6, 1.5, -4.0), arm_r=(-.6, 4.0, 5.5))),
        # out: the sole ahead at the height of the hip
        (t_out, dict(REST, flex=88, knee=9, toe=58, plant=0, hip=(-4.7, 1.1), give=5, yaw=-13, tuck=13, hike=7, chest=11, lean=8,
                     arm_l=(2.4, 2.2, -6.0), arm_r=(-.4, 5.5, 7.0))),
        # (No key holds it there. With one, a tick at its length, the leg stood out for as long as the row holds
        # both bodies at a hit: the row slows the clip then, and the clip was at its stillest.)
        # folded again, the thigh still up
        (t_out + 3.6, dict(REST, flex=70, knee=104, toe=10, plant=0, hip=(-4.8, -.3), give=7, yaw=-5, tuck=7, hike=5, chest=6, lean=3,
                           arm_l=(1.4, 1.4, -3.6), arm_r=(-.5, 3.6, 4.8))),
        # coming down under the hip
        (t_out + 8.0, dict(REST, flex=24, knee=48, toe=-8, plant=0, hip=(-3.4, -.2), give=5, yaw=-1, tuck=2, hike=2.0, chest=2, lean=1,
                           arm_l=(.6, .5, -1.3), arm_r=(-.2, 1.3, 1.7))),
        # set down, toes first
        (t_out + 11.4, dict(REST, toe=-10, hip=(-1.0, 0), give=3, arm_l=(.1, .1, -.3), arm_r=(0, .3, .4))),
        (float(STARTUP + LIVE + RECOVERY), dict(REST)),
    ]


def main():
    out = sys.argv[1]
    data = P.load()
    bones = data['bones']
    base = data['clips']['r32_knife_forward']
    actors = S.Actors()
    rig = actors.eva_rig
    body = B.EvaBody(rig)
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    rot0, pos0 = P.frame_pose(bones, base, 0)
    m0 = rig.fk(rot0, pos0, world)

    def pt(m, name, pivot=None):
        return m[name][:3, :3] @ (rig.pivot[name] if pivot is None else pivot) + m[name][:3, 3]

    def wq(m, name):
        return B.mat_rot(m[name])

    def turned(m, name, q_world):
        """The bone's own rotation once it is turned by this in the world, about its pivot."""
        parent = rig.parent[name]
        pw = wq(m, parent) if parent else R.qconj(R.qy(0))
        return R.qnorm(R.qmul(R.qconj(pw), R.qmul(q_world, wq(m, name))))

    def shift(pos, by):
        """The whole body moved by this in the world."""
        pos['root'] = pos['root'] + np.array([-by[0], by[1], -by[2]]) / S.SCALE

    def knee_for(limb, length):
        lo, hi = limb.lo, limb.hi
        for _ in range(48):
            mid = .5 * (lo + hi)
            if limb.reach(mid)[0] > length:
                lo = mid
            else:
                hi = mid
        return .5 * (lo + hi)

    leg, leg_r = body.limbs['leg_l'], body.limbs['leg_r']
    # ---- the stand: the base frame's trunk, head and hands, facing ahead, on the feet where the Unit stands ----
    rot_s, pos_s = dict(rot0), dict(pos0)
    ahead = R.qrot(wq(m0, 'torso_lower'), -Z)           # the model looks along its own -z
    rot_s['torso_lower'] = turned(m0, 'torso_lower', R.qaxis(Y, -math.atan2(ahead[0], ahead[2])))
    m = rig.fk(rot_s, pos_s, world)
    # the chest tipped until the head is as far ahead of the hips as the Unit carries it
    chest_was = rot_s['torso_upper']
    lo, hi = -25.0, 25.0
    for _ in range(40):
        mid = .5 * (lo + hi)
        rot_s['torso_upper'] = chest_was
        m = rig.fk(rot_s, pos_s, world)
        rot_s['torso_upper'] = turned(m, 'torso_upper', R.qaxis(X, D(mid)))
        m = rig.fk(rot_s, pos_s, world)
        hips = .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))
        if pt(m, 'head')[2] - hips[2] < STAND['head_ahead'] - STAND['hips_ahead']:
            lo = mid
        else:
            hi = mid
    hips = .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))
    shift(pos_s, np.array([-hips[0], STAND['hip_high'] - hips[1], STAND['hips_ahead'] - hips[2]]))
    m_s = rig.fk(rot_s, pos_s, world)
    flat = rig.fk({n: ONE for n in rig.pivot}, {}, world)
    ankle_s = {s: np.array([STAND['ankle'][s][0], STAND['ankle_high'], STAND['ankle'][s][1]]) for s in 'lr'}
    foot_w = {'l': R.qmul(R.qaxis(Y, D(STAND['toes_out'])), wq(flat, 'foot_l')), 'r': R.qmul(R.qaxis(Y, -D(STAND['toes_out'])), wq(flat, 'foot_r'))}
    stand_knee = knee_for(leg_r, float(np.linalg.norm(ankle_s['r'] - pt(m_s, 'leg_r'))))
    # the left leg as it stands
    d0 = ankle_s['l'] - pt(m_s, 'leg_l')
    ang_of = lambda v: math.atan2(-v[2], -v[1])     # in the leg's own plane, from straight down towards ahead
    a_rest = ang_of(leg.a)
    knee_rest = knee_for(leg, float(np.linalg.norm(d0)))
    flex_rest = math.degrees(math.atan2(d0[2], -d0[1]) - (ang_of(leg.reach(knee_rest)[1]) - a_rest))
    side_rest = float(d0[0])
    # where the left wrist hangs and the way its elbow points, in the chest's own space; the right arm's the same
    # across the chest's middle (in the base it is bent to carry the knife)
    chest_s = m_s['torso_upper']
    chest_inv = np.linalg.inv(chest_s)
    wrist_l, shoulder_l, elbow_l = pt(m_s, 'wrist_l'), pt(m_s, 'arm_l'), pt(m_s, 'forearm_l', body.elbow['l'])
    line = unit(wrist_l - shoulder_l)
    pole_l = unit((elbow_l - shoulder_l) - line * np.dot(elbow_l - shoulder_l, line))
    middle = .5 * (rig.pivot['arm_l'][0] + rig.pivot['arm_r'][0])
    hang = chest_inv[:3, :3] @ wrist_l + chest_inv[:3, 3]
    rest_local = {'l': hang, 'r': np.array([2 * middle - hang[0], hang[1], hang[2]])}
    pole_local = {'l': unit(chest_s[:3, :3].T @ pole_l)}
    pole_local['r'] = pole_local['l'] * np.array([-1.0, 1.0, 1.0])
    mirror = lambda q: np.array([q[0], q[1], -q[2], -q[3]])
    for n in ('wrist_r', 'hand_r'):
        rot_s[n] = mirror(rot0[n.replace('_r', '_l')])
    knee_r_pole = unit(pt(m_s, 'shin_r', body.knee['r']) - pt(m_s, 'leg_r'))

    def leg_line(flex, knee):
        """The direction and length hip to ankle of the left leg with the thigh this far ahead of down and the knee this far closed."""
        length, w = leg.reach(knee)
        line = D(flex) + ang_of(w) - a_rest
        return np.array([0, -math.cos(line), math.sin(line)]), length

    t_out = row_place(CONTACT)
    ks = keys(t_out)
    for _, k in ks:
        if k['flex'] is None:
            k['flex'], k['knee'] = flex_rest, knee_rest
        for name in ('hip', 'arm_l', 'arm_r'):
            k[name] = np.asarray(k[name], float)
    names = ('flex', 'knee', 'toe', 'plant', 'give', 'yaw', 'tuck', 'hike', 'chest', 'lean', 'hip', 'arm_l', 'arm_r')

    def at(t):
        """The keys' values at a tick, along a curve through the keys (a cubic with the mean of the slopes either
        side at each key, none at the ends and none where a value turns round): no value stops at a key it is
        only passing."""
        t = min(max(t, ks[0][0]), ks[-1][0])
        i = max(j for j, (kt, _) in enumerate(ks) if kt <= t + 1e-9)
        if i >= len(ks) - 1:
            return {n: ks[-1][1][n] for n in names}
        (ta, a), (tb, b) = ks[i], ks[i + 1]
        u = (t - ta) / (tb - ta)
        res = {}
        for n in names:
            p1, p2 = a[n], b[n]

            def slope(j):
                if j <= 0 or j >= len(ks) - 1:
                    return 0 * p1
                before = (ks[j][1][n] - ks[j - 1][1][n]) / (ks[j][0] - ks[j - 1][0])
                after = (ks[j + 1][1][n] - ks[j][1][n]) / (ks[j + 1][0] - ks[j][0])
                both = .5 * (before + after)
                return np.where(np.asarray(before) * np.asarray(after) <= 0, 0.0, both) if np.ndim(both) else (0.0 if before * after <= 0 else both)
            m1, m2 = slope(i) * (tb - ta), slope(i + 1) * (tb - ta)
            u2, u3 = u * u, u * u * u
            res[n] = (2 * u3 - 3 * u2 + 1) * p1 + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * p2 + (u3 - u2) * m2
        return res

    def pose(t):
        c = at(t)
        rot, pos = dict(rot_s), dict(pos_s)
        info = {}
        # pelvis: shifted and turned where it stands, at the height that closes the right knee as far as the key has it
        shift(pos, np.array([c['hip'][0], 0, c['hip'][1]]))
        m = rig.fk(rot, pos, world)
        turn = R.qmul(R.qaxis(Y, D(c['yaw'])), R.qmul(R.qaxis(X, -D(c['tuck'])), R.qaxis(Z, D(c['hike']))))
        rot['torso_lower'] = turned(m, 'torso_lower', turn)
        m = rig.fk(rot, pos, world)
        d = ankle_s['r'] - pt(m, 'leg_r')
        need = leg_r.reach(stand_knee + c['give'])[0]
        info['hip_y'] = d[1] + math.sqrt(max(0.0, need * need - d[0] * d[0] - d[2] * d[2]))
        shift(pos, np.array([0, info['hip_y'], 0]))
        m = rig.fk(rot, pos, world)
        # chest: turned back against the pelvis, and tipped
        rot['torso_upper'] = turned(m, 'torso_upper', R.qmul(R.qaxis(Y, D(c['chest'])), R.qaxis(X, -D(c['lean']))))
        m = rig.fk(rot, pos, world)
        # head: on what is ahead
        back = R.qmul(R.qaxis(Y, -D(.5 * (c['yaw'] + c['chest']))), R.qaxis(X, D(.5 * (c['tuck'] + c['lean']))))
        rot['neck'] = turned(m, 'neck', R.qslerp(ONE, back, .5))
        m = rig.fk(rot, pos, world)
        rot['head'] = turned(m, 'head', R.qslerp(ONE, back, .5))
        m = rig.fk(rot, pos, world)
        parent_q = wq(m, 'torso_lower')
        # right leg: to the foot where it stands
        qu, ql, qw_, ang, err = leg_r.solve(pt(m, 'leg_r'), ankle_s['r'], knee_r_pole + .3 * Z - .1 * X, parent_q)
        rot['leg_r'], rot['shin_r'] = qu, ql
        rot['ankle_r'] = R.qmul(R.qconj(R.qmul(qw_, ql)), R.qmul(foot_w['r'], R.qconj(rot0['foot_r'])))
        pos['shin_r'] = R.Rig.hinge_offset(ql, rig.pivot['shin_r'], body.knee['r'])
        info['knee_r'], info['leg_err_r'] = ang, err
        # left leg: by its thigh and knee, from the hip where the pelvis has it, or to where it stood; the foot by its toes
        hip = pt(m, 'leg_l')
        line, length = leg_line(c['flex'], c['knee'])
        swing = smooth(min(1.0, (c['flex'] - flex_rest) / 20.0)) if c['flex'] > flex_rest else 0.0
        aside = side_rest * (1 - swing)
        free = hip + line * math.sqrt(max(0.0, length * length - aside * aside)) + X * aside
        down = D(max(0.0, -c['toe']))
        stood = ankle_s['l'] + Y * BALL * math.sin(down) + Z * BALL * (1 - math.cos(down))
        plant = min(1.0, max(0.0, c['plant']))
        target = free + (stood - free) * plant
        thigh = np.array([0, -math.cos(D(c['flex'])), math.sin(D(c['flex']))])
        qu, ql, qw_, ang, err = leg.solve(hip, target, thigh + .3 * Z + .1 * X * plant, parent_q)
        rot['leg_l'], rot['shin_l'] = qu, ql
        toes = R.qmul(R.qaxis(X, -D(c['toe'])), foot_w['l'])
        rot['ankle_l'] = R.qmul(R.qconj(R.qmul(qw_, ql)), R.qmul(toes, R.qconj(rot0['foot_l'])))
        pos['shin_l'] = R.Rig.hinge_offset(ql, rig.pivot['shin_l'], body.knee['l'])
        info['knee_l'], info['leg_err_l'] = ang, err
        # arms: the wrists by where they hang from the chest
        m = rig.fk(rot, pos, world)
        chest = m['torso_upper']
        rel = R.qmul(wq(m, 'torso_upper'), R.qconj(wq(m_s, 'torso_upper')))
        for s in 'lr':
            limb = body.limbs['arm_' + s]
            wrist = chest[:3, :3] @ rest_local[s] + chest[:3, 3] + R.qrot(rel, c['arm_' + s])
            qu, ql, qw_, ang, err = limb.solve(pt(m, 'arm_' + s), wrist, chest[:3, :3] @ pole_local[s], wq(m, 'clavicle_' + s))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, rig.pivot['forearm_' + s], body.elbow[s])
            info['elbow_' + s], info['arm_err_' + s] = ang, err
        m = rig.fk(rot, pos, world)
        return rot, pos, m, info

    total = STARTUP + LIVE + RECOVERY
    times = [row_place(f / (FRAMES - 1)) for f in range(FRAMES)]
    times[0], times[-1] = 0.0, float(total)
    posed = [pose(t) for t in times]

    # ---- what it is, in numbers ----
    rot, pos, m, info = posed[0]
    hips = .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))
    print('the stand: ankles %s %s; hips %s; head %s; knees %.1f %.1f; left thigh %.1f ahead of down' % (
        np.round(pt(m, 'ankle_l'), 1), np.round(pt(m, 'ankle_r'), 1), np.round(hips, 1), np.round(pt(m, 'head'), 1), info['knee_l'], info['knee_r'], flex_rest))
    print('the leg is first out at tick %.2f of %d (the clip at %.3f); the live part is ticks %d to %d' % (t_out, total, CONTACT, STARTUP, STARTUP + LIVE))
    ank = np.array([pt(p[2], 'ankle_l') for p in posed])
    far = int(np.argmax(ank[:, 2]))
    print('left ankle furthest ahead %.1f at tick %.1f, %.1f high; highest %.1f; never below %.2f (it stands at %.2f)' % (
        ank[far, 2], times[far], ank[far, 1], ank[:, 1].max(), ank[:, 1].min(), ankle_s['l'][1]))
    print('right ankle moves at most %.3f; leg errors at most %.2f (left) %.2f (right), arms %.2f' % (
        max(np.linalg.norm(pt(p[2], 'ankle_r') - ankle_s['r']) for p in posed), max(p[3]['leg_err_l'] for p in posed),
        max(p[3]['leg_err_r'] for p in posed), max(max(p[3]['arm_err_l'], p[3]['arm_err_r']) for p in posed)))
    print('knees: left %.0f..%.0f, right %.0f..%.0f; elbows %.0f..%.0f / %.0f..%.0f' % (
        min(p[3]['knee_l'] for p in posed), max(p[3]['knee_l'] for p in posed), min(p[3]['knee_r'] for p in posed), max(p[3]['knee_r'] for p in posed),
        min(p[3]['elbow_l'] for p in posed), max(p[3]['elbow_l'] for p in posed), min(p[3]['elbow_r'] for p in posed), max(p[3]['elbow_r'] for p in posed)))
    mid = np.array([.5 * (pt(p[2], 'leg_l') + pt(p[2], 'leg_r')) for p in posed])
    head = np.array([pt(p[2], 'head') for p in posed])
    air = [i for i in range(FRAMES) if ank[i, 1] > ankle_s['l'][1] + .8]
    print('left foot off the ground ticks %.1f to %.1f; then the hips are %.1f..%.1f to the left of the right ankle, %.1f..%.1f ahead of it; the head %.1f..%.1f ahead' % (
        times[air[0]], times[air[-1]], (mid[air, 0] - ankle_s['r'][0]).min(), (mid[air, 0] - ankle_s['r'][0]).max(),
        (mid[air, 2] - ankle_s['r'][2]).min(), (mid[air, 2] - ankle_s['r'][2]).max(), (head[air, 2] - ankle_s['r'][2]).min(), (head[air, 2] - ankle_s['r'][2]).max()))
    # speeds by the tick, from a fine sampling of the motion itself
    fine = [pose(t) for t in np.arange(0, total + 1e-9, .25)]
    watch = ('torso_lower', 'torso_upper', 'leg_l', 'shin_l', 'ankle_l', 'leg_r', 'shin_r', 'arm_l', 'forearm_l', 'arm_r', 'forearm_r', 'head')
    speed = np.array([[4 * 2 * math.degrees(math.acos(min(1, abs(float(np.dot(wq(fine[i][2], b), wq(fine[i - 1][2], b))))))) for b in watch] for i in range(1, len(fine))])
    foot_speed = 4 * np.linalg.norm(np.diff(np.array([pt(p[2], 'ankle_l') for p in fine]), axis=0), axis=1)
    worst = np.unravel_index(int(np.argmax(speed)), speed.shape)
    jump = np.abs(np.diff(speed, axis=0)).max(axis=0)
    print('fastest joint %.0f degrees a tick (%s at tick %.2f); the left foot at most %.1f a tick (tick %.2f); most a joint\'s speed changes in a quarter tick: %s' % (
        speed.max(), watch[worst[1]], .25 * (worst[0] + 1), foot_speed.max(), .25 * (int(np.argmax(foot_speed)) + 1),
        ', '.join('%s %.0f' % (b, j) for b, j in sorted(zip(watch, jump), key=lambda x: -x[1])[:4])))
    if len(sys.argv) > 3:
        print(' tick  phase  thigh knee  toe  | ankle ahead high left | hips left, up, ahead of the right ankle | head ahead of it | knee_r | foot speed')
        for t in np.arange(0, total + 1e-9, 1.0):
            c = at(t)
            rot, pos, m, info = pose(t)
            a = pt(m, 'ankle_l')
            hips = .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))
            print(' %4.1f  %.3f  %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f | %5.1f | %5.1f | %5.1f' % (
                t, row_phase(t), c['flex'], info['knee_l'], c['toe'], a[2], a[1], a[0], hips[0] - ankle_s['r'][0], info['hip_y'],
                hips[2] - ankle_s['r'][2], pt(m, 'head')[2] - ankle_s['r'][2], info['knee_r'], foot_speed[min(len(foot_speed) - 1, int(t * 4))]))

    # ---- written as what each frame differs by from the base frame ----
    moved = [n for n in bones if n in rot0 and any(R.qangle(R.qmul(R.qnorm(rot[n]), R.qconj(R.qnorm(rot0[n])))) > 1e-5 for rot, _, _, _ in posed)]
    shifted = [n for n in pos0 if any(np.linalg.norm(pos[n] - pos0[n]) > 1e-7 for _, pos, _, _ in posed)]
    shifted += [n for n in posed[0][1] if n not in pos0]
    frames = []
    for i, (rot, pos, m, info) in enumerate(posed):
        row = {'rotation_delta_wxyz': [], 'position_delta_xyz': {}, 'foot_contact': [bool(ank[i, 1] <= ankle_s['l'][1] + .8), True]}
        for n in moved:
            delta = R.qnorm(R.qmul(R.baked_to_clip(R.qnorm(rot[n])), R.qconj(R.baked_to_clip(R.qnorm(rot0[n])))))
            row['rotation_delta_wxyz'].append([round(float(x), 6) for x in delta])
        for n in shifted:
            t = pos[n] - pos0.get(n, np.zeros(3))
            if n == 'root':
                row['root_delta_m'] = [round(float(x), 6) for x in np.array([-t[0], t[1], t[2]]) * 16 / 112]
            else:
                row['position_delta_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
        frames.append(row)
    clip = {'duration_seconds': SECONDS, 'loop': False, 'leading_side': 'l', 'contact_phase': CONTACT,
            'trajectory_m': [[0.0, 0.0, 0.0]] * FRAMES, 'step_contacts': [f['foot_contact'] for f in frames],
            'contact_bone': 'foot_l', 'bones': moved, 'frames': frames}
    print('%d frames; %d bones turned from the base frame: %s; offsets changed: %s' % (FRAMES, len(moved), ' '.join(moved), ' '.join(shifted)))
    doc = {'source': 'Project SEELE original kick (tools/finale/kick.py), MIT', 'sample_rate': 60,
           'form': 'each frame as its difference from the first frame of r32_knife_forward',
           'row': {'startup': STARTUP, 'live': LIVE, 'recovery': RECOVERY, 'lead': LEAD, 'tail': TAIL},
           'clips': {'r32_kick_r64': clip}}
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, os.path.getsize(out), 'bytes')
    if len(sys.argv) > 2 and sys.argv[2] != '-':
        shown = [0.0] + [k[0] for k in ks[1:-1]] + [.5 * (ks[3][0] + ks[4][0]), .5 * (ks[4][0] + ks[5][0]), .5 * (ks[5][0] + ks[6][0]), float(total)]
        shown = sorted(set(round(t, 2) for t in shown))
        images = [P.views(actors, pose(t)[2], 'kick %.1f' % t, knife=False) for t in shown]
        R.sheet([row[v] for v in range(2) for row in images], len(shown)).save(sys.argv[2])
        print('wrote', sys.argv[2])


if __name__ == '__main__':
    main()
