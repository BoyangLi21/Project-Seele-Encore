"""What Unit-01's own blows are written on: from the way it stands, through the blow, and back to the stand.

tools/finale/kick.py wrote one blow this way (2026-11-17). This is the same made general, for the blows of the
attack plan (tools/finale/unarmed.py): a blow is a list of keys, each a tick of its row and what the body is doing
then; between keys every value goes along a curve through them; the frames are laid on the clip so that the row
that plays it (EvaMoveTableR64, along EvaRowClockR64's curve) gives every part the time it is written with.

A key says, all in blocks and degrees, x to the Unit's left, y up, z ahead:

  adv           how far ahead of where the row began the body has gone over the ground (never back)
  hip, high     the hips' place from where they are in the stand: (left, ahead), and up
  yaw tuck hike the pelvis: turned to its left (its RIGHT side forward; negative brings the left side forward),
                tucked under, hiked
  chest lean side  the chest against the pelvis: turned the same way, tipped BACK (forward is negative), bent to its
                right (negative: to its left)
  nod           the head tipped down more than it is to keep looking ahead
  for each foot (l..., r...):
    lat         where the ankle is over the ground from where it stood, (left, ahead): in the world, so a foot that
                stays where it is while the body goes on keeps (0, 0)
    lup         how high it is off the ground
    ltoe        toes drawn up (+), or the heel lifted on the ball of the foot (-)
    lfree       0: the leg goes to that place; 1: the leg is given by its thigh and knee instead
    lflex lknee the thigh ahead of straight down, and how far the knee is closed
    lon         1 while the foot is stood on (a foot the game holds where it is in the world)
  A foot's steps can be given apart from the keys instead (Stage.clip's steps): for each, the ticks it leaves the
  ground and is set down again, where it is set down (as lat), and how high it is carried. Between steps it stays
  where it was set down, however the keys fall.
  for each arm (l..., r...):
    larm        the wrist from where it hangs, (left, up, ahead), carried with the chest
    lreach      0: there; 1: the wrist is at lhand instead
    lhand       the wrist from its own shoulder, (left, up, ahead) as the world has them (not turned with the chest).
                (A place in the world was tried first: the body goes past it, and between two keys the wrist went
                through its own shoulder.)
    lelbow      the way the elbow points, added to the way it points in the stand (chest's space)

Built on the first frame of the knife's forward thrust in Unit-01's private profile (rig 1): its trunk, head and
hands. That frame is not this project's to publish, so a clip is written as what each frame differs by from it
(the game puts it back on: EvaGameplayMotionR32.addClipsR64).
"""
import json
import math
import os

import numpy as np

import body as B
import profile_clip as P
import rig as R
import scene as S

D = math.radians
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])    # the Unit's left, up, ahead
ONE = np.array([1.0, 0, 0, 0])
# How the Unit stands (as tools/finale/kick.py has it, from a capture of Unit-01 standing).
STAND = dict(ankle={'l': (4.78, 0.0), 'r': (-4.78, 0.0)}, ankle_high=5.76, toes_out=3.0, hip_high=35.07, hips_ahead=0.0, head_ahead=3.0)
# The point of a foot the game holds to the ground (the profile's support_toes): ahead of the ankle and below it. A
# foot whose heel comes up turns about that point, so its ankle goes forward as well as up.
TOE, SOLE = 5.38, 5.8
BLOCKS_A_METRE = 35.0       # a clip's root path is in metres: 112 / 16 * the Unit's scale of 5


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


class Row:
    """A row's ticks and where its live part lies on its clip (EvaMoveTableR64: start-up, live, recovery, lead, tail)."""

    def __init__(self, startup, live, recovery, lead, tail, contact):
        self.startup, self.live, self.recovery, self.lead, self.tail, self.contact = startup, live, recovery, lead, tail, contact
        self.total = startup + live + recovery
        self.open, self.close = contact - lead, contact + tail

    def phase(self, place):
        end = self.startup + self.live + max(1, self.recovery)
        if place <= 0:
            return 0.0
        if place >= end:
            return 1.0
        x, y = [0, self.startup, self.startup + self.live, end], [0, self.open, self.close, 1]
        h = [x[1] - x[0], x[2] - x[1], x[3] - x[2]]
        d = [(y[1] - y[0]) / h[0], (y[2] - y[1]) / h[1], (y[3] - y[2]) / h[2]]
        m = [_edge(h[0], h[1], d[0], d[1]), _inner(h[0], h[1], d[0], d[1]), _inner(h[1], h[2], d[1], d[2]), _edge(h[2], h[1], d[2], d[1])]
        i = 0 if place <= x[1] else 1 if place <= x[2] else 2
        t = (place - x[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return min(1.0, max(0.0, (2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h[i] * m[i + 1]))

    def place(self, phase):
        lo, hi = 0.0, float(self.total)
        for _ in range(48):
            mid = .5 * (lo + hi)
            if self.phase(mid) < phase:
                lo = mid
            else:
                hi = mid
        return .5 * (lo + hi)


# ---- keys ---------------------------------------------------------------------------------------------------------

REST = dict(adv=0, hip=(0, 0), high=0, yaw=0, tuck=0, hike=0, chest=0, lean=0, side=0, nod=0,
            lat=(0, 0), lup=0, ltoe=0, lfree=0, lflex=0, lknee=0, lon=1,
            rat=(0, 0), rup=0, rtoe=0, rfree=0, rflex=0, rknee=0, ron=1,
            larm=(0, 0, 0), lreach=0, lhand=(0, 0, 0), lelbow=(0, 0, 0),
            rarm=(0, 0, 0), rreach=0, rhand=(0, 0, 0), relbow=(0, 0, 0))


def key(**over):
    unknown = [n for n in over if n not in REST]
    if unknown:
        raise KeyError('no such value in a key: %s' % unknown)
    return dict(REST, **over)


class Keys:
    """The keys' values at a tick, along a curve through the keys: a cubic with the mean of the slopes either side at
    each key, none at the ends and none where a value turns round, so no value stops at a key it is only passing."""

    def __init__(self, keys):
        self.ks = [(float(t), {n: np.asarray(v, float) for n, v in k.items()}) for t, k in keys]
        self.names = list(REST)

    def at(self, t):
        ks = self.ks
        t = min(max(t, ks[0][0]), ks[-1][0])
        i = max(j for j, (kt, _) in enumerate(ks) if kt <= t + 1e-9)
        if i >= len(ks) - 1:
            return {n: ks[-1][1][n] for n in self.names}
        (ta, a), (tb, b) = ks[i], ks[i + 1]
        u = (t - ta) / (tb - ta)
        res = {}
        for n in self.names:
            p1, p2 = a[n], b[n]

            def slope(j):
                if j <= 0 or j >= len(ks) - 1:
                    return 0 * p1
                before = (ks[j][1][n] - ks[j - 1][1][n]) / (ks[j][0] - ks[j - 1][0])
                after = (ks[j + 1][1][n] - ks[j][1][n]) / (ks[j + 1][0] - ks[j][0])
                return np.where(before * after <= 0, 0.0, .5 * (before + after))
            m1, m2 = slope(i) * (tb - ta), slope(i + 1) * (tb - ta)
            u2, u3 = u * u, u * u * u
            res[n] = (2 * u3 - 3 * u2 + 1) * p1 + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * p2 + (u3 - u2) * m2
        return res


class _Stepped:
    """Keys whose feet go by their steps where steps are given."""

    def __init__(self, keys, feet):
        self.keys, self.feet = keys, feet

    def at(self, t):
        c = self.keys.at(t)
        for s, foot in self.feet.items():
            place, up, on = foot(t)
            c[s + 'at'], c[s + 'on'] = place, np.asarray(on)
            # a foot that is carried by its thigh and knee (lfree) is only said to be off the ground
            c[s + 'up'] = np.asarray(up)
        return c


# ---- the body -----------------------------------------------------------------------------------------------------

def stepping(steps):
    """Steps of one foot [(off, on, (left, ahead), lift), ...] -> a function of the tick giving where the foot is over
    the ground from where it stood, how high it is carried, and whether it is stood on."""
    steps = sorted(steps)

    def at(t):
        place = np.zeros(2)
        for off, on, to, lift in steps:
            to = np.asarray(to, float)
            if t >= on:
                place = to
                continue
            if t > off:
                u = (t - off) / (on - off)
                return place + (to - place) * smooth(u), lift * math.sin(math.pi * u) ** 1.2, 0.0
            break
        return place, 0.0, 1.0
    return at


class Stage:
    def __init__(self):
        data = P.load()
        self.bones = data['bones']
        base = data['clips']['r32_knife_forward']
        self.actors = S.Actors()
        self.rig = rig = self.actors.eva_rig
        self.body = body = B.EvaBody(rig)
        self.world = world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
        self.rot0, self.pos0 = rot0, pos0 = P.frame_pose(self.bones, base, 0)
        m0 = rig.fk(rot0, pos0, world)
        pt, wq, turned = self.pt, self.wq, self.turned
        # the stand: the base frame's trunk, head and hands, facing ahead, on the feet where the Unit stands
        rot_s, pos_s = dict(rot0), dict(pos0)
        ahead = R.qrot(wq(m0, 'torso_lower'), -Z)           # the model looks along its own -z
        rot_s['torso_lower'] = turned(m0, 'torso_lower', R.qaxis(Y, -math.atan2(ahead[0], ahead[2])))
        chest_was = rot_s['torso_upper']
        lo, hi = -25.0, 25.0
        for _ in range(40):         # the chest tipped until the head is as far ahead of the hips as the Unit carries it
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
        self.shift(pos_s, np.array([-hips[0], STAND['hip_high'] - hips[1], STAND['hips_ahead'] - hips[2]]))
        mirror = lambda q: np.array([q[0], q[1], -q[2], -q[3]])
        for n in ('wrist_r', 'hand_r'):         # in the base the right hand is bent to carry the knife
            rot_s[n] = mirror(rot0[n.replace('_r', '_l')])
        self.rot_s, self.pos_s = rot_s, pos_s
        self.m_s = m_s = rig.fk(rot_s, pos_s, world)
        flat = rig.fk({n: ONE for n in rig.pivot}, {}, world)
        self.ankle_s = {s: np.array([STAND['ankle'][s][0], STAND['ankle_high'], STAND['ankle'][s][1]]) for s in 'lr'}
        self.foot_w = {'l': R.qmul(R.qaxis(Y, D(STAND['toes_out'])), wq(flat, 'foot_l')), 'r': R.qmul(R.qaxis(Y, -D(STAND['toes_out'])), wq(flat, 'foot_r'))}
        self.legs = {s: body.limbs['leg_' + s] for s in 'lr'}
        self.ang_of = lambda v: math.atan2(-v[2], -v[1])     # in the leg's own plane, from straight down towards ahead
        self.a_rest = {s: self.ang_of(self.legs[s].a) for s in 'lr'}
        self.side_rest = {s: float((self.ankle_s[s] - pt(m_s, 'leg_' + s))[0]) for s in 'lr'}
        self.knee_pole = {s: unit(pt(m_s, 'shin_' + s, body.knee[s]) - pt(m_s, 'leg_' + s)) for s in 'lr'}
        # where each wrist hangs and the way its elbow points, in the chest's own space; the right arm's the same
        # across the chest's middle (in the base it is bent to carry the knife)
        chest_s = m_s['torso_upper']
        chest_inv = np.linalg.inv(chest_s)
        wrist_l, shoulder_l, elbow_l = pt(m_s, 'wrist_l'), pt(m_s, 'arm_l'), pt(m_s, 'forearm_l', body.elbow['l'])
        line = unit(wrist_l - shoulder_l)
        pole_l = unit((elbow_l - shoulder_l) - line * np.dot(elbow_l - shoulder_l, line))
        middle = .5 * (rig.pivot['arm_l'][0] + rig.pivot['arm_r'][0])
        hang = chest_inv[:3, :3] @ wrist_l + chest_inv[:3, 3]
        self.rest_local = {'l': hang, 'r': np.array([2 * middle - hang[0], hang[1], hang[2]])}
        self.pole_local = {'l': unit(chest_s[:3, :3].T @ pole_l)}
        self.pole_local['r'] = self.pole_local['l'] * np.array([-1.0, 1.0, 1.0])

    # -- small things
    def pt(self, m, name, pivot=None):
        return m[name][:3, :3] @ (self.rig.pivot[name] if pivot is None else pivot) + m[name][:3, 3]

    @staticmethod
    def wq(m, name):
        return B.mat_rot(m[name])

    def turned(self, m, name, q_world):
        """The bone's own rotation once it is turned by this in the world, about its pivot."""
        parent = self.rig.parent[name]
        pw = self.wq(m, parent) if parent else R.qconj(R.qy(0))
        return R.qnorm(R.qmul(R.qconj(pw), R.qmul(q_world, self.wq(m, name))))

    @staticmethod
    def shift(pos, by):
        """The whole body moved by this in the world."""
        pos['root'] = pos['root'] + np.array([-by[0], by[1], -by[2]]) / S.SCALE

    def leg_line(self, s, flex, knee):
        """The direction and length hip to ankle of a leg with the thigh this far ahead of down and the knee this far closed."""
        length, w = self.legs[s].reach(knee)
        line = D(flex) + self.ang_of(w) - self.a_rest[s]
        return np.array([0, -math.cos(line), math.sin(line)]), length

    # -- a pose
    def pose(self, c):
        """A key's values (Keys.at) -> the rig's rotations and offsets, its matrices in the body's own frame (the body
        standing where it began: its advance is the game's to make), and what was measured on the way."""
        rig, body, world = self.rig, self.body, self.world
        pt, wq, turned = self.pt, self.wq, self.turned
        rot, pos = dict(self.rot_s), dict(self.pos_s)
        info = {}
        adv = float(c['adv'])
        self.shift(pos, np.array([c['hip'][0], float(c['high']), c['hip'][1]]))
        m = rig.fk(rot, pos, world)
        rot['torso_lower'] = turned(m, 'torso_lower', R.qmul(R.qaxis(Y, D(c['yaw'])), R.qmul(R.qaxis(X, -D(c['tuck'])), R.qaxis(Z, D(c['hike'])))))
        m = rig.fk(rot, pos, world)
        rot['torso_upper'] = turned(m, 'torso_upper', R.qmul(R.qaxis(Y, D(c['chest'])), R.qmul(R.qaxis(X, -D(c['lean'])), R.qaxis(Z, D(c['side'])))))
        m = rig.fk(rot, pos, world)
        # the head: on what is ahead (half of what the trunk has turned and tipped is given back by the neck, half by the head)
        back = R.qmul(R.qaxis(Y, -D(.5 * (c['yaw'] + c['chest']))), R.qaxis(X, D(.5 * (c['tuck'] + c['lean']) + .5 * c['nod'])))
        rot['neck'] = turned(m, 'neck', R.qslerp(ONE, back, .5))
        m = rig.fk(rot, pos, world)
        rot['head'] = turned(m, 'head', R.qslerp(ONE, back, .5))
        m = rig.fk(rot, pos, world)
        parent_q = wq(m, 'torso_lower')
        for s in 'lr':
            leg, sign = self.legs[s], (1.0 if s == 'l' else -1.0)
            hip = pt(m, 'leg_' + s)
            down = D(max(0.0, -float(c[s + 'toe'])))
            # where it is over the ground (the world's place, seen from a body that has gone adv ahead), up on the
            # ball of the foot where the heel is lifted
            stood = (self.ankle_s[s] + X * c[s + 'at'][0] + Z * (c[s + 'at'][1] - adv) + Y * (float(c[s + 'up']) + TOE * math.sin(down) - SOLE * (1 - math.cos(down)))
                     + Z * (TOE * (1 - math.cos(down)) + SOLE * math.sin(down)))
            free_w = min(1.0, max(0.0, float(c[s + 'free'])))
            target, thigh = stood, self.knee_pole[s]
            if free_w > 0:
                line, length = self.leg_line(s, float(c[s + 'flex']), float(c[s + 'knee']))
                aside = self.side_rest[s] * (1 - smooth(float(c[s + 'flex']) / 40.0))
                free = hip + line * math.sqrt(max(0.0, length * length - aside * aside)) + X * aside
                target = stood + (free - stood) * free_w
                bent = np.array([0, -math.cos(D(c[s + 'flex'])), math.sin(D(c[s + 'flex']))])
                thigh = unit(self.knee_pole[s] * (1 - free_w) + bent * free_w)
            # (the knee goes ahead over the toes as it bends: by the way the thigh hangs in the stand alone it went out to the side)
            qu, ql, qw_, ang, err = leg.solve(hip, target, thigh + .9 * Z + .05 * X * sign * (1 - free_w), parent_q)
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            toes = R.qmul(R.qaxis(X, -D(c[s + 'toe'])), self.foot_w[s])
            rot['ankle_' + s] = R.qmul(R.qconj(R.qmul(qw_, ql)), R.qmul(toes, R.qconj(self.rot0['foot_' + s])))
            pos['shin_' + s] = R.Rig.hinge_offset(ql, rig.pivot['shin_' + s], body.knee[s])
            info['knee_' + s], info['leg_err_' + s] = ang, err
        m = rig.fk(rot, pos, world)
        chest = m['torso_upper']
        rel = R.qmul(wq(m, 'torso_upper'), R.qconj(wq(self.m_s, 'torso_upper')))
        for s in 'lr':
            limb = body.limbs['arm_' + s]
            wrist = chest[:3, :3] @ self.rest_local[s] + chest[:3, 3] + R.qrot(rel, c[s + 'arm'])
            shoulder = pt(m, 'arm_' + s)
            reach = min(1.0, max(0.0, float(c[s + 'reach'])))
            if reach > 0:
                wrist = wrist + (shoulder + c[s + 'hand'] - wrist) * reach
            pole = chest[:3, :3] @ unit(self.pole_local[s] + c[s + 'elbow'])
            # the wrist no further from the shoulder than leaves the elbow a little bent, and no nearer than the arm
            # folds: at its full length the arm has no way for its elbow to point, and turned over in a frame
            far, near = .94 * limb.reach(limb.lo)[0], 1.04 * limb.reach(limb.hi)[0]
            d = wrist - shoulder
            dist = float(np.linalg.norm(d))
            info['arm_pull_' + s] = max(0.0, dist - far, near - dist)
            wrist = shoulder + d * (min(far, max(near, dist)) / max(dist, 1e-9))
            qu, ql, qw_, ang, err = limb.solve(shoulder, wrist, pole, wq(m, 'clavicle_' + s))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            pos['forearm_' + s] = R.Rig.hinge_offset(ql, rig.pivot['forearm_' + s], body.elbow[s])
            info['elbow_' + s], info['arm_err_' + s] = ang, err
        m = rig.fk(rot, pos, world)
        return rot, pos, m, info

    # -- a clip
    def clip(self, name, row, keys, contact_bone, contact_point=None, frames=None, shown=None, sheet=None, leading='r', table=True, steps=None):
        """Lay the keys on a clip by the row's curve, say what it is in numbers, and give the clip as the game reads it.

        contact_point: the place the blow lands with, in the rig's rest space (blocks), carried by contact_bone."""
        rig, pt = self.rig, self.pt
        ks = _Stepped(Keys(keys), {s: stepping(v) for s, v in (steps or {}).items()})
        count = frames or 3 * row.total + 1
        times = [row.place(f / (count - 1)) for f in range(count)]
        times[0], times[-1] = 0.0, float(row.total)
        posed = [(self.pose(ks.at(t)), ks.at(t)) for t in times]
        adv = np.maximum.accumulate([float(c['adv']) for _, c in posed])
        # ---- what it is, in numbers ----
        t_hit = row.place(row.contact)
        print('%s: %d+%d+%d ticks, its mark met at tick %.2f (the clip at %.3f); the body goes %.1f ahead, by tick %.1f' % (
            name, row.startup, row.live, row.recovery, t_hit, row.contact, adv[-1], next((times[i] for i in range(count) if adv[i] >= adv[-1] - 1e-6), 0)))
        print('  wrists brought in or pushed out by at the most %.2f (left, at tick %.1f) %.2f (right, at tick %.1f)' % tuple(
            x for s_ in 'lr' for x in max((p[3]['arm_pull_' + s_], times[i]) for i, (p, _) in enumerate(posed))))
        print('  out of reach at the most: legs %.2f %.2f, arms %.2f %.2f; knees %.0f..%.0f / %.0f..%.0f; elbows %.0f..%.0f / %.0f..%.0f' % (
            max(p[3]['leg_err_l'] for p, _ in posed), max(p[3]['leg_err_r'] for p, _ in posed), max(p[3]['arm_err_l'] for p, _ in posed), max(p[3]['arm_err_r'] for p, _ in posed),
            min(p[3]['knee_l'] for p, _ in posed), max(p[3]['knee_l'] for p, _ in posed), min(p[3]['knee_r'] for p, _ in posed), max(p[3]['knee_r'] for p, _ in posed),
            min(p[3]['elbow_l'] for p, _ in posed), max(p[3]['elbow_l'] for p, _ in posed), min(p[3]['elbow_r'] for p, _ in posed), max(p[3]['elbow_r'] for p, _ in posed)))
        mark = np.array([self.mark(p[2], contact_bone, contact_point) + Z * adv[i] for i, (p, _) in enumerate(posed)])
        hit = int(np.argmin([abs(t - t_hit) for t in times]))
        print('  the mark (%s) at the hit: %.1f ahead of where the Unit stood, %.1f high, %.1f to its left; going %.1f a tick' % (
            contact_bone, mark[hit, 2], mark[hit, 1], mark[hit, 0], np.linalg.norm(mark[min(count - 1, hit + 1)] - mark[max(0, hit - 1)]) / max(1e-6, times[min(count - 1, hit + 1)] - times[max(0, hit - 1)])))
        # the feet over the ground while they are stood on
        for s in 'lr':
            on = [i for i in range(count) if posed[i][1][s + 'on'] > .5]
            world_place = np.array([pt(posed[i][0][2], 'ankle_' + s) + Z * adv[i] for i in range(count)])
            runs, start = [], None
            for i in range(count + 1):
                if i < count and i in on and start is None:
                    start = i
                if (i == count or i not in on) and start is not None:
                    runs.append((start, i - 1))
                    start = None
            print('  %s foot stood on: %s' % ('left' if s == 'l' else 'right', '; '.join('ticks %.1f to %.1f (moves %.2f, lowest %.2f over where it stands)' % (
                times[a], times[b], np.linalg.norm((world_place[a:b + 1] - world_place[a])[:, [0, 2]], axis=1).max(), world_place[a:b + 1, 1].min() - self.ankle_s[s][1]) for a, b in runs) or 'never'))
        # speeds by the tick, from a fine sampling of the motion itself
        fine = [self.pose(ks.at(t)) for t in np.arange(0, row.total + 1e-9, .25)]
        worst, jerk = (0, '', 0), {}
        for i in range(1, len(fine)):
            for n in ('leg_l', 'shin_l', 'leg_r', 'shin_r', 'arm_l', 'forearm_l', 'arm_r', 'forearm_r', 'torso_lower', 'torso_upper', 'head'):
                a = math.degrees(R.qangle(R.qmul(R.qnorm(fine[i][0][n]), R.qconj(R.qnorm(fine[i - 1][0][n]))))) * 4
                if a > worst[0]:
                    worst = (a, n, i * .25)
                if i > 1:
                    b = math.degrees(R.qangle(R.qmul(R.qnorm(fine[i - 1][0][n]), R.qconj(R.qnorm(fine[i - 2][0][n]))))) * 4
                    jerk[n] = max(jerk.get(n, 0), abs(a - b))
        print('  fastest joint %.0f degrees a tick (%s at tick %.2f); most a joint\'s speed changes in a quarter tick: %s' % (
            worst[0], worst[1], worst[2], ', '.join('%s %.0f' % (n, v) for n, v in sorted(jerk.items(), key=lambda kv: -kv[1])[:4])))
        if table:
            print('   tick  phase |  adv | hips left up ahead | head ahead high | l ankle ahead high | r ankle ahead high | l wrist ahead high left | r wrist ahead high left | knees | shoulders ahead high')
            for t in [float(x) for x in range(row.total + 1)]:
                (rot, pos, m, info), c = self.pose(ks.at(t)), ks.at(t)
                a = float(np.interp(t, times, adv))
                hips = .5 * (pt(m, 'leg_l') + pt(m, 'leg_r'))
                print('   %4.1f  %.3f | %4.1f | %5.1f %5.1f %5.1f | %5.1f %5.1f | %5.1f %5.1f | %5.1f %5.1f | %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f | %3.0f %3.0f | %5.1f %5.1f' % (
                    t, row.phase(t), a, hips[0], hips[1] - STAND['hip_high'], hips[2] + a, pt(m, 'head')[2] + a, pt(m, 'head')[1],
                    pt(m, 'ankle_l')[2] + a, pt(m, 'ankle_l')[1], pt(m, 'ankle_r')[2] + a, pt(m, 'ankle_r')[1],
                    pt(m, 'wrist_l')[2] + a, pt(m, 'wrist_l')[1], pt(m, 'wrist_l')[0], pt(m, 'wrist_r')[2] + a, pt(m, 'wrist_r')[1], pt(m, 'wrist_r')[0],
                    info['knee_l'], info['knee_r'], .5 * (pt(m, 'arm_l')[2] + pt(m, 'arm_r')[2]) + a, .5 * (pt(m, 'arm_l')[1] + pt(m, 'arm_r')[1])))
        # ---- written as what each frame differs by from the base frame ----
        rot0, pos0 = self.rot0, self.pos0
        moved = [n for n in self.bones if n in rot0 and any(R.qangle(R.qmul(R.qnorm(p[0][n]), R.qconj(R.qnorm(rot0[n])))) > 1e-5 for p, _ in posed)]
        shifted = [n for n in pos0 if any(np.linalg.norm(p[1][n] - pos0[n]) > 1e-7 for p, _ in posed)]
        shifted += [n for n in posed[0][0][1] if n not in pos0]
        out = []
        for (rot, pos, m, info), c in posed:
            fr = {'rotation_delta_wxyz': [], 'position_delta_xyz': {}, 'foot_contact': [bool(c['lon'] > .5), bool(c['ron'] > .5)]}
            for n in moved:
                delta = R.qnorm(R.qmul(R.baked_to_clip(R.qnorm(rot[n])), R.qconj(R.baked_to_clip(R.qnorm(rot0[n])))))
                fr['rotation_delta_wxyz'].append([round(float(x), 6) for x in delta])
            for n in shifted:
                t = pos[n] - pos0.get(n, np.zeros(3))
                if n == 'root':
                    fr['root_delta_m'] = [round(float(x), 6) for x in np.array([-t[0], t[1], t[2]]) * 16 / 112]
                else:
                    fr['position_delta_xyz'][n] = [round(float(x), 4) for x in (-t[0] * 16, t[1] * 16, t[2] * 16)]
            out.append(fr)
        clip = {'duration_seconds': row.total / 20.0, 'loop': False, 'leading_side': leading, 'contact_phase': row.contact,
                'trajectory_m': [[0.0, 0.0, round(-float(a) / BLOCKS_A_METRE, 6)] for a in adv], 'step_contacts': [f['foot_contact'] for f in out],
                'contact_bone': contact_bone, 'bones': moved, 'frames': out,
                'row': {'startup': row.startup, 'live': row.live, 'recovery': row.recovery, 'lead': row.lead, 'tail': row.tail}}
        # A blow with both feet off the ground at once is a leap: the game is told, and does not stand those frames
        # on whichever foot is lower (EvaBodyPose.groundGameplay; it lowered the knee's spring until one foot touched,
        # and the knee went in under its mark).
        flown = sum(1 for f in out if not f['foot_contact'][0] and not f['foot_contact'][1])
        if flown:
            clip['leaps'] = True
            print('  %s: off both feet for %d of its %d frames (a leap)' % (name, flown, len(out)))
        if contact_point is not None:
            # The authoring rig mirrors model X on import. The game expects original model coordinates
            # here and mirrors them when it constructs the bone-local contact point.
            clip['contact_point_model'] = [round(float(x), 4) for x in (-contact_point[0] * 16, contact_point[1] * 16, contact_point[2] * 16)]
        print('  %d frames; %d bones turned from the base frame; offsets changed: %s' % (count, len(moved), ' '.join(shifted)))
        if sheet:
            at = sorted(set(round(t, 2) for t in (shown or [k[0] for k in keys])))
            images = []
            for t in at:
                c = ks.at(t)
                rot, pos, m, info = self.pose(c)
                images.append(P.views(self.actors, rig.fk(rot, pos, R.entity_matrix([0, 0, float(np.interp(t, times, adv))], 0, S.SCALE)), '%s %.1f' % (name, t), size=(400, 400), knife=False))
            R.sheet([r[v] for v in range(len(images[0])) for r in images], len(at)).save(sheet)
            print('  wrote', sheet)
        return clip

    def mark(self, m, bone, point=None):
        """Where the blow's mark is, in the body's own frame (blocks)."""
        return self.pt(m, bone, None if point is None else np.asarray(point, float))


def write(out, clips, source):
    """The clips into the file beside what it holds already."""
    doc = {'source': source, 'sample_rate': 60, 'form': 'each frame as its difference from the first frame of r32_knife_forward', 'clips': {}}
    if os.path.exists(out):
        doc = json.load(open(out, encoding='utf8'))
    doc['clips'].update(clips)
    json.dump(doc, open(out, 'w', encoding='utf8'), separators=(',', ':'))
    print('wrote', out, os.path.getsize(out), 'bytes:', ' '.join(sorted(doc['clips'])))
