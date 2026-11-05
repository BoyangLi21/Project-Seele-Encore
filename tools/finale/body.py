"""Pose solvers: high-level controls -> GeckoLib bone rotations/positions.

Stage frame: x side, y up, z forward (the EVA starts at the origin facing +z).
Headings are degrees about +y with 0 = facing +z.  A body facing heading h has
world rotation Ry(h + 180) relative to its model (model forward is -z).

Limbs are solved analytically around their real hinge (the EVA's knee/elbow
hinge centres the game applies, the angel's pivots).  The hinge axis is the
limb's local X, so a knee/elbow can only bend the anatomical way; the limb's
roll is fixed by the pole, so it can never flip back to front.
"""
import math

import numpy as np

import rig as R

D = math.radians
SCALE = 5.0


def heading_q(h):
    return R.qy(D(h) + math.pi)


def body_q(h, pitch=0.0, roll=0.0, yaw=0.0):
    """World rotation: heading, forward lean (+), roll (+ = top to its left)."""
    return R.qmul(R.qmul(heading_q(h + yaw), R.qx(-D(pitch))), R.qz(D(roll)))


def rel_q(yaw=0.0, pitch=0.0, roll=0.0):
    """Relative trunk/head rotation: turn to its left (+yaw), bend forward (+), roll."""
    return R.qmul(R.qmul(R.qy(D(yaw)), R.qx(-D(pitch))), R.qz(D(roll)))


def foot_q(h, pitch=0.0, roll=0.0):
    """Foot world rotation: heading, toes up (+), roll."""
    return R.qmul(R.qmul(heading_q(h), R.qx(D(pitch))), R.qz(D(roll)))


def mat_rot(m):
    r = m[:3, :3]
    s = np.linalg.norm(r[:, 0])
    return R.matq(r / s)


def point(m, p):
    return m[:3, :3] @ p + m[:3, 3]


def frame(a, b):
    a = a / np.linalg.norm(a)
    b = b - a * np.dot(a, b)
    b = b / np.linalg.norm(b)
    return np.stack([a, b, np.cross(a, b)], axis=1)


def perp(v, axis):
    axis = axis / np.linalg.norm(axis)
    r = v - axis * np.dot(v, axis)
    n = np.linalg.norm(r)
    return r / n if n > 1e-9 else None


class Limb:
    """Two-segment limb with a hinge about the upper bone's local X."""

    def __init__(self, upper, lower, end, root_p, hinge_p, end_p, flex_sign, protrude,
                 lo, hi):
        self.upper, self.lower, self.end = upper, lower, end
        self.a = hinge_p - root_p          # model blocks
        self.b = end_p - hinge_p
        self.hinge_p = hinge_p
        self.flex_sign = flex_sign          # hinge rotation = Rx(flex_sign * angle)
        self.protrude = np.asarray(protrude, float)
        self.lo, self.hi = lo, hi           # flexion range, degrees

    def reach(self, angle):
        w = self.a + R.qmat(R.qx(self.flex_sign * D(angle))) @ self.b
        return np.linalg.norm(w) * SCALE, w

    def solve(self, start, target, pole, parent_q):
        """start/target world points, pole world direction.  -> (upper q, lower q, upper world q, flex, error)"""
        d = target - start
        dist = np.linalg.norm(d)
        lo, hi = self.lo, self.hi
        rlo, _ = self.reach(lo)
        rhi, _ = self.reach(hi)
        if dist >= rlo:
            ang = lo
        elif dist <= rhi:
            ang = hi
        else:
            a, b = lo, hi
            for _ in range(48):
                m = (a + b) / 2
                if self.reach(m)[0] > dist:
                    a = m
                else:
                    b = m
            ang = (a + b) / 2
        reach, w = self.reach(ang)
        u = d / max(dist, 1e-9)
        pole = np.asarray(pole, float)
        self.pole_strength = np.linalg.norm(pole - u * np.dot(pole, u)) / max(np.linalg.norm(pole), 1e-9)
        self.reach_frac = dist / rlo
        v = perp(pole, u)
        if v is None:
            v = perp(np.array([0, 0, 1.0]), u)
        p = perp(self.protrude, w)
        world = frame(u, v) @ frame(w, p).T
        qw = R.matq(world)
        q_upper = R.qmul(R.qconj(parent_q), qw)
        q_lower = R.qx(self.flex_sign * D(ang))
        return q_upper, q_lower, qw, ang, abs(reach - dist)


class EvaBody:
    KNEE_LIFT = 11.4 / 16

    def __init__(self, rig):
        self.rig = rig
        pv = rig.pivot
        self.hip_centre = (pv['leg_l'] + pv['leg_r']) / 2
        self.limbs = {}
        for s in 'lr':
            knee = pv['shin_' + s] + np.array([0, self.KNEE_LIFT, 0])
            self.limbs['leg_' + s] = Limb('leg_' + s, 'shin_' + s, 'ankle_' + s, pv['leg_' + s], knee,
                                          pv['ankle_' + s], -1, (0, 0, -1), 0.0, 160.0)
            elbow = np.array([-23.489652 if s == 'l' else 23.489652, 123.435069, 7.737214]) / 16
            self.limbs['arm_' + s] = Limb('arm_' + s, 'forearm_' + s, 'wrist_' + s, pv['arm_' + s], elbow,
                                          pv['wrist_' + s], 1, (0, 0, 1), -22.0, 150.0)
        self.knee = {s: self.limbs['leg_' + s].hinge_p for s in 'lr'}
        self.foot_points = None
        self.elbow = {s: self.limbs['arm_' + s].hinge_p for s in 'lr'}
        # foot sole anchors (model blocks): under the ankle, ball, heel
        self.sole = {}
        for s in 'lr':
            ank = pv['ankle_' + s]
            self.sole[s] = {'mid': np.array([ank[0], 0, ank[2]]),
                            'ball': np.array([ank[0], 0, -8.5 / 16]),
                            'heel': np.array([ank[0], 0, 12.0 / 16])}

    def solve(self, c, entity=(0, 0, 0), yaw=0.0):
        """c: dict of controls (see choreography).  Returns rot, pos, mats, info."""
        rig = self.rig
        E = R.entity_matrix(entity, yaw, SCALE)
        Einv = np.linalg.inv(E)
        qE = R.qy(D(180 - yaw))
        rot, pos, info = {}, {}, {}
        # pelvis
        q_pw = body_q(*c['pelvis_rot'])
        q_tl = R.qmul(R.qconj(qE), q_pw)
        rot['root'] = np.array([1.0, 0, 0, 0])
        rot['torso_lower'] = q_tl
        target = point(Einv, np.asarray(c['hip'], float))
        pv = rig.pivot
        pos['root'] = target - pv['torso_lower'] - R.qmat(q_tl) @ (self.hip_centre - pv['torso_lower'])
        rot['torso_upper'] = rel_q(*c['chest'])
        hy, hp, hr = c['head']
        rot['neck'] = rel_q(0.4 * hy, 0.4 * hp, 0.4 * hr)
        rot['head'] = rel_q(0.6 * hy, 0.6 * hp, 0.6 * hr)
        rot['aim_pitch'] = np.array([1.0, 0, 0, 0])
        for s, sign in (('l', -1), ('r', 1)):
            shrug, fwd = [float(v) for v in c['shoulder_' + s]]
            rot['clavicle_' + s] = R.qmul(R.qz(D(sign * shrug)), R.qy(D(sign * fwd)))
        rot['r37_jaw'] = R.qx(-D(float(np.ravel(c.get('jaw', 0.0))[0])))
        mats = rig.fk(rot, pos, E)
        # legs
        for s in 'lr':
            limb = self.limbs['leg_' + s]
            q_f = foot_q(*c['foot_%s_rot' % s])
            k = float(np.asarray(c.get('foot_%s_anchor' % s, 0.0)).ravel()[0])
            sole = self.sole[s]
            anchor = sole['mid'] + max(k, 0) * (sole['ball'] - sole['mid']) + max(-k, 0) * (sole['heel'] - sole['mid'])
            ank_model = rig.pivot['ankle_' + s]
            foot_at = np.asarray(c['foot_%s' % s], float).copy()
            if self.foot_points is not None:
                low = (foot_at + (self.foot_points[s] - anchor) @ (R.qmat(q_f).T * SCALE))[:, 1].min()
                if low < 0:
                    foot_at[1] -= low
            ankle = foot_at + R.qmat(q_f) @ ((ank_model - anchor) * SCALE)
            hip = point(mats['torso_lower'], rig.pivot['leg_' + s])
            pole = R.qmat(heading_q(float(np.ravel(c['knee_%s' % s])[0]))) @ np.array([0, 0, -1.0])
            pole = pole + np.array([0, float(np.ravel(c.get('knee_%s_down' % s, 0.0))[0]), 0])
            parent_q = mat_rot(mats['torso_lower'])
            qu, ql, qw, ang, err = limb.solve(hip, ankle, pole, parent_q)
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            q_shin_w = R.qmul(qw, ql)
            rot['ankle_' + s] = R.qmul(R.qconj(q_shin_w), q_f)
            rot['foot_' + s] = np.array([1.0, 0, 0, 0])
            info['knee_' + s] = ang
            info['leg_err_' + s] = err
            info['knee_pole_' + s] = limb.pole_strength
            mats = rig.fk(rot, pos, E)
        # arms
        for s in 'lr':
            limb = self.limbs['arm_' + s]
            shoulder = point(mats['clavicle_' + s], rig.pivot['arm_' + s])
            parent_q = mat_rot(mats['clavicle_' + s])
            target = np.asarray(c['hand_%s' % s], float)
            qu, ql, qw, ang, err = limb.solve(shoulder, target, np.asarray(c['elbow_%s' % s], float), parent_q)
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            fl, dv, tw = c['wrist_%s' % s]
            sign = -1 if s == 'l' else 1
            rot['wrist_' + s] = R.qmul(R.qmul(R.qy(D(sign * tw)), R.qx(D(fl))), R.qz(D(sign * dv)))
            rot['hand_' + s] = np.array([1.0, 0, 0, 0])
            info['elbow_' + s] = ang
            info['arm_err_' + s] = err
            info['elbow_pole_' + s] = limb.pole_strength
            info['arm_reach_' + s] = limb.reach_frac
        # game hinge positions for shin and forearm
        for s in 'lr':
            pos['shin_' + s] = R.Rig.hinge_offset(rot['shin_' + s], rig.pivot['shin_' + s], self.knee[s])
            pos['forearm_' + s] = R.Rig.hinge_offset(rot['forearm_' + s], rig.pivot['forearm_' + s], self.elbow[s])
        mats = rig.fk(rot, pos, E)
        return rot, pos, mats, info


class AngelBody:
    """Sachiel: arms rest bent 90 degrees with forearms forward."""

    def __init__(self, rig):
        self.rig = rig
        pv = rig.pivot
        self.hip_centre = (pv['leg_l'] + pv['leg_r']) / 2
        self.limbs = {}
        for s in 'lr':
            self.limbs['leg_' + s] = Limb('leg_' + s, 'shin_' + s, 'foot_' + s, pv['leg_' + s], pv['shin_' + s],
                                          pv['foot_' + s], -1, (0, 0, -1), 0.0, 160.0)
            self.limbs['arm_' + s] = Limb('arm_' + s, 'forearm_' + s, 'hand_' + s, pv['arm_' + s],
                                          pv['forearm_' + s], pv['hand_' + s], 1, (0, 0, 1), -90.0, 75.0)
        self.core = np.array([0.0, 153.42, -16.91]) / 16   # on torso_upper
        self.sole = {s: np.array([pv['foot_' + s][0], 0, pv['foot_' + s][2]]) for s in 'lr'}

    def solve(self, c, entity=(0, 0, 0), yaw=180.0, arm_override=None):
        rig = self.rig
        E = R.entity_matrix(entity, yaw, SCALE)
        Einv = np.linalg.inv(E)
        qE = R.qy(D(180 - yaw))
        rot, pos, info = {}, {}, {}
        q_pw = body_q(*c['pelvis_rot'])
        q_tl = R.qmul(R.qconj(qE), q_pw)
        rot['root'] = np.array([1.0, 0, 0, 0])
        rot['torso_lower'] = q_tl
        target = point(Einv, np.asarray(c['hip'], float))
        pv = rig.pivot
        pos['root'] = target - pv['torso_lower'] - R.qmat(q_tl) @ (self.hip_centre - pv['torso_lower'])
        rot['torso_upper'] = rel_q(*c['chest'])
        hy, hp, hr = c['head']
        rot['neck'] = rel_q(0.4 * hy, 0.4 * hp, 0.4 * hr)
        rot['head'] = rel_q(0.6 * hy, 0.6 * hp, 0.6 * hr)
        mats = rig.fk(rot, pos, E)
        for s in 'lr':
            limb = self.limbs['leg_' + s]
            q_f = foot_q(*c['foot_%s_rot' % s])
            ankle = np.asarray(c['foot_%s' % s], float) + R.qmat(q_f) @ ((pv['foot_' + s] - self.sole[s]) * SCALE)
            hip = point(mats['torso_lower'], pv['leg_' + s])
            pole = R.qmat(heading_q(float(np.ravel(c['knee_%s' % s])[0]))) @ np.array([0, 0, -1.0])
            pole = pole + np.array([0, float(np.ravel(c.get('knee_%s_down' % s, 0.0))[0]), 0])
            qu, ql, qw, ang, err = limb.solve(hip, ankle, pole, mat_rot(mats['torso_lower']))
            rot['leg_' + s], rot['shin_' + s] = qu, ql
            rot['foot_' + s] = R.qmul(R.qconj(R.qmul(qw, ql)), q_f)
            info['knee_' + s] = ang
            info['leg_err_' + s] = err
            mats = rig.fk(rot, pos, E)
        for s in 'lr':
            limb = self.limbs['arm_' + s]
            shoulder = point(mats['torso_upper'], pv['arm_' + s])
            target = np.asarray(c['hand_%s' % s], float)
            qu, ql, qw, ang, err = limb.solve(shoulder, target, np.asarray(c['elbow_%s' % s], float),
                                              mat_rot(mats['torso_upper']))
            rot['arm_' + s], rot['forearm_' + s] = qu, ql
            fl, dv, tw = c['wrist_%s' % s]
            sign = -1 if s == 'l' else 1
            rot['hand_' + s] = R.qmul(R.qmul(R.qy(D(sign * tw)), R.qx(D(fl))), R.qz(D(sign * dv)))
            info['elbow_' + s] = ang
            info['arm_err_' + s] = err
        brk = float(np.ravel(c.get('break_r', 0.0))[0])
        if brk:
            rot['forearm_r'] = R.qmul(R.qmul(rot['forearm_r'], R.qx(-D(brk))), R.qz(D(0.35 * brk)))
        if arm_override:
            rot.update(arm_override)
        mats = rig.fk(rot, pos, E)
        return rot, pos, mats, info

    def core_world(self, mats):
        return point(mats['torso_upper'], self.core)
