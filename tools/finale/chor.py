"""The first-battle execution, authored as key poses.

Stage frame: x side (Unit-01's left is +x), y up, z forward.  Unit-01 starts at
the origin facing +z; Sachiel faces it (heading 180).  Unit-01's feet are
placed by the ball of the foot (anchor 1), Sachiel's by the sole under the ankle.
The AT field panel the client draws stands at z=21, centre height 40.
"""
import math

import numpy as np

import anim
import body as B

FIELD_Z = 21.0
FIELD_Y = 40.0


def rot_y(v, h):
    a = math.radians(h)
    x, y, z = v
    return (x * math.cos(a) + z * math.sin(a), y, -x * math.sin(a) + z * math.cos(a))


class Actor:
    def __init__(self, defaults):
        self.rig = anim.Rig()
        for k, v in defaults.items():
            self.rig.ch(k, v)

    def key(self, t, ease='auto', **controls):
        for name, value in controls.items():
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], str):
                value, mode = value
                self.rig.ch(name).key(t, value, ease=mode)
            else:
                self.rig.ch(name).key(t, value, ease=ease)
        return self

    def sample(self, t):
        return self.rig.sample(t)


EVA_DEFAULTS = {
    'hip': (0, 35.0, 0), 'pelvis_rot': (0, 0, 0), 'chest': (0, 0, 0), 'head': (0, 0, 0),
    'shoulder_l': (0, 0), 'shoulder_r': (0, 0), 'jaw': 0.0,
    'foot_l': (4.8, 0, 2.7), 'foot_r': (-4.8, 0, 2.7), 'foot_l_rot': (0, 0, 0), 'foot_r_rot': (0, 0, 0),
    'foot_l_anchor': 1.0, 'foot_r_anchor': 1.0, 'knee_l': 8.0, 'knee_r': -8.0,
    'knee_l_down': 0.0, 'knee_r_down': 0.0,
    'hand_l': (8, 27, 3), 'hand_r': (-8, 27, 3),
    'elbow_l': (0.5, -0.3, -1.0), 'elbow_r': (-0.5, -0.3, -1.0),
    'wrist_l': (0, 0, 0), 'wrist_r': (0, 0, 0),
    'pound_l': (2.3, 2.6, -0.4), 'pound_r': (-2.3, 2.6, -0.4), 'pound_w': 0.0,
}

ANGEL_DEFAULTS = {
    'hip': (0, 34.0, 42.0), 'pelvis_rot': (180, 0, 0), 'chest': (0, 0, 0), 'head': (0, 0, 0),
    'foot_l': (-7.6, 0, 43.5), 'foot_r': (7.6, 0, 43.5), 'foot_l_rot': (180, 0, 0), 'foot_r_rot': (180, 0, 0),
    'knee_l': 190.0, 'knee_r': 170.0, 'knee_l_down': 0.0, 'knee_r_down': 0.0,
    'hand_l': (-17, 22, 40), 'hand_r': (17, 22, 40),
    'elbow_l': (-0.5, -0.2, 1.0), 'elbow_r': (0.5, -0.2, 1.0),
    'wrist_l': (0, 0, 0), 'wrist_r': (0, 0, 0),
    'break_r': 0.0, 'hug_w': 0.0,
}


SACH_Z = 52.0


def build():
    eva = Actor(EVA_DEFAULTS)
    ang = Actor(ANGEL_DEFAULTS)
    awakening(eva, ang)
    field(eva, ang)
    charge(eva, ang)
    wrench(eva, ang)
    flight(eva, ang)
    leap(eva, ang)
    pound(eva, ang)
    embrace(eva, ang)
    aftermath(eva, ang)
    return eva, ang


def step(actor, foot, t0, t1, p0, p1, h0, h1, lift=2.5, pitch0=0.0, roll=0.0):
    """One step: planted at p0 until t0, peels off upward, travels, drops vertically onto p1 at t1."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = t1 - t0
    up = np.array([0, 1.0, 0])
    ch = actor.rig.ch(foot)
    ch.key(t0, p0, ease='flat')
    ch.key(t0 + 0.14 * d, p0 + 0.03 * (p1 - p0) + up * lift * 0.4)
    ch.key(t0 + 0.42 * d, p0 + 0.42 * (p1 - p0) + up * lift)
    ch.key(t0 + 0.74 * d, p0 + 0.93 * (p1 - p0) + up * lift * 0.62)
    ch.key(t0 + 0.9 * d, p0 + 0.995 * (p1 - p0) + up * lift * 0.16)
    ch.key(t1, p1, ease='flat')
    r = actor.rig.ch(foot + '_rot')
    r.key(t0, (h0, pitch0, roll), ease='flat')
    r.key(t0 + 0.14 * d, (h0, min(pitch0, -14), roll))
    r.key(t0 + 0.42 * d, (h0 + (h1 - h0) * 0.4, -8, roll))
    r.key(t0 + 0.74 * d, (h0 + (h1 - h0) * 0.9, 4, roll))
    r.key(t1, (h1, 0, roll), ease='flat')


# --------------------------------------------------------------- 0.0 - 1.6
def awakening(eva, ang):
    stance = dict(foot_l=(5.4, 0, 4.0), foot_r=(-5.4, 0, 1.2), foot_l_rot=(8, 0, 0), foot_r_rot=(-8, 0, 0),
                  knee_l=12.0, knee_r=-12.0)
    eva.key(0.0, ease='flat', hip=(0, 35.0, 0.2), pelvis_rot=(0, 8, 0), chest=(0, 22, 0), head=(0, 30, 0),
            hand_l=(7.0, 27.0, 6.0), hand_r=(-7.0, 27.0, 6.0), elbow_l=(0.5, -0.2, -1.0), elbow_r=(-0.5, -0.2, -1.0),
            shoulder_l=(-3, 10), shoulder_r=(-3, 10), jaw=0.0, **stance)
    # a convulsion runs up the body before the scream
    eva.key(0.42, hip=(0, 33.9, 0.0), pelvis_rot=(0, 14, 0), chest=(0, 30, 0), head=(0, 18, 0),
            hand_l=(6.6, 25.6, 6.8), hand_r=(-6.6, 25.6, 6.8), shoulder_l=(6, 12), shoulder_r=(6, 12), jaw=6.0)
    # roar at the sky: chest thrown open, head back, arms hanging back with fists
    eva.key(0.88, hip=(0, 33.2, -1.0), pelvis_rot=(0, -2, 0), chest=(0, -24, 0), head=(0, -44, 0), jaw=46.0,
            hand_l=(18.5, 32.5, -3.0), hand_r=(-18.5, 32.5, -3.0), elbow_l=(0.5, -1.0, -0.6), elbow_r=(-0.5, -1.0, -0.6),
            shoulder_l=(10, -14), shoulder_r=(10, -14), wrist_l=(-34, 0, 0), wrist_r=(-34, 0, 0))
    eva.key(1.30, hip=(0, 33.0, -0.9), pelvis_rot=(0, -1, 0), chest=(0, -21, 0), head=(0, -40, 3), jaw=42.0,
            hand_l=(18.8, 32.0, -2.6), hand_r=(-18.6, 32.3, -2.8), shoulder_l=(9, -12), shoulder_r=(9, -12))
    # it finds the angel: head snaps level, hands come up, weight drops
    eva.key(1.62, hip=(0, 33.2, 0.4), pelvis_rot=(0, 14, 0), chest=(0, 8, 0), head=(0, -6, 0), jaw=12.0,
            hand_l=(8.0, 34.5, 9.0), hand_r=(-8.0, 34.5, 9.0), elbow_l=(0.8, -0.6, -0.3), elbow_r=(-0.8, -0.6, -0.3),
            shoulder_l=(2, 6), shoulder_r=(2, 6), wrist_l=(-12, 0, 0), wrist_r=(-12, 0, 0))
    sach = dict(foot_l=(-7.6, 0, SACH_Z + 1.5), foot_r=(7.6, 0, SACH_Z + 1.5))
    ang.key(0.0, hip=(0, 34.2, SACH_Z), pelvis_rot=(180, 4, 0), chest=(0, 6, 0), head=(0, 2, 0),
            hand_l=(-16, 21, SACH_Z - 2), hand_r=(16, 21, SACH_Z - 2), **sach)
    ang.key(0.9, hip=(0, 34.0, SACH_Z + 0.3), pelvis_rot=(180, 2, 0), chest=(0, 3, 0), head=(0, -4, 0),
            hand_l=(-17, 22, SACH_Z - 2.5), hand_r=(17, 22, SACH_Z - 2.5))


# --------------------------------------------------------------- 1.6 - 5.0
def field_x(t):
    """Half width of the tear the client draws at the field's centre height."""
    return 13.0 * anim.smooth((t - 3.0) / 2.0)


def field(eva, ang):
    zf = FIELD_Z - 0.6
    # lunge: the left foot drives forward as the hands hit the field
    step(eva, 'foot_l', 1.62, 1.98, (5.4, 0, 4.0), (5.8, 0, 8.0), 8, 6, lift=2.0)
    eva.key(1.62, foot_r=(-5.4, 0, 1.2), foot_r_rot=(-8, 0, 0))
    # the rear foot pushes back into a long brace
    step(eva, 'foot_r', 1.70, 2.06, (-5.4, 0, 1.2), (-6.0, 0, -11.5), -8, -10, lift=1.4)
    eva.key(2.3, foot_r_rot=(-10, -20, 0))
    contact_l, contact_r = (6.5, 43.0, zf), (-6.5, 43.0, zf)
    eva.key(1.98, hip=(0, 31.2, -1.6), pelvis_rot=(0, 22, 0), chest=(0, 12, 0), head=(0, -12, 0), jaw=22.0,
            hand_l=(contact_l, 'fast'), hand_r=(contact_r, 'fast'),
            elbow_l=(0.8, -0.7, -0.2), elbow_r=(-0.8, -0.7, -0.2), wrist_l=(-30, 0, 0), wrist_r=(-30, 0, 0))
    eva.key(2.2, hip=(0, 30.8, -2.4), pelvis_rot=(0, 23, 0), chest=(0, 13, 0), head=(0, -14, 0), jaw=16.0,
            hand_l=contact_l, hand_r=contact_r)
    # second pulse: sink back, then drive the shoulders in
    eva.key(2.5, hip=(0, 31.4, -3.4), pelvis_rot=(0, 19, 0), chest=(0, 9, 0), head=(0, -18, 0), jaw=10.0,
            hand_l=contact_l, hand_r=contact_r)
    eva.key(2.66, hip=(0, 30.4, -1.6), pelvis_rot=(0, 25, 0), chest=(0, 17, 0), head=(0, -6, 0), jaw=30.0,
            shoulder_l=(0, 12), shoulder_r=(0, 12))
    eva.key(2.95, hip=(0, 30.6, -2.0), pelvis_rot=(0, 24, 0), chest=(0, 15, 0), head=(0, -10, 0), jaw=18.0,
            hand_l=contact_l, hand_r=contact_r)
    # claws work to the seam at the centre
    seam_l, seam_r = (2.4, 41.5, zf), (-2.4, 41.5, zf)
    eva.key(3.45, hand_l=seam_l, hand_r=seam_r, elbow_l=(1.0, -0.4, 0.1), elbow_r=(-1.0, -0.4, 0.1),
            hip=(0, 30.6, -1.2), pelvis_rot=(0, 24, 0), chest=(0, 16, 0), head=(0, -8, 0),
            wrist_l=(-28, 12, 0), wrist_r=(-28, 12, 0), shoulder_l=(2, 16), shoulder_r=(2, 16))
    # the rear foot steps up square for the pull
    step(eva, 'foot_r', 3.48, 3.92, (-6.0, 0, -11.5), (-7.2, 0, 5.5), -10, -12, lift=2.4, pitch0=-20)
    eva.key(3.48, foot_l=(5.8, 0, 8.0))
    for t in (3.75, 4.0, 4.25, 4.5, 4.75):
        x = max(2.4, field_x(t) + 1.2)
        eva.key(t, hand_l=(x, 41.5, zf), hand_r=(-x, 41.5, zf))
    eva.key(3.75, hip=(0, 30.2, 0.4), pelvis_rot=(0, 20, 0), chest=(0, 10, 0), head=(0, -6, 0), jaw=22.0,
            shoulder_l=(4, 2), shoulder_r=(4, 2))
    eva.key(4.4, hip=(0, 29.8, 1.6), pelvis_rot=(0, 15, 0), chest=(0, 4, 0), head=(0, -12, 0), jaw=36.0,
            elbow_l=(0.6, -0.8, -0.6), elbow_r=(-0.6, -0.8, -0.6), shoulder_l=(6, -10), shoulder_r=(6, -10))
    eva.key(4.95, hip=(0, 31.0, 2.4), pelvis_rot=(0, 6, 0), chest=(0, -12, 0), head=(0, -24, 0), jaw=42.0,
            hand_l=(17.5, 42.0, 15.5), hand_r=(-17.5, 42.0, 15.5), shoulder_l=(9, -16), shoulder_r=(9, -16),
            wrist_l=(-30, 0, 0), wrist_r=(-30, 0, 0))
    # Sachiel flinches at the shove and steps back as its field fails
    ang.key(2.6, hip=(0, 34.0, SACH_Z + 0.3), pelvis_rot=(180, 2, 0), chest=(0, 3, 0), head=(0, -4, 0))
    ang.key(2.82, hip=(0, 34.1, SACH_Z + 1.0), pelvis_rot=(180, -4, 0), chest=(0, -6, 0), head=(0, -10, 0))
    ang.key(3.7, hip=(0, 33.9, SACH_Z + 0.8), pelvis_rot=(180, 0, 0), chest=(0, 0, 0), head=(0, -4, 0),
            hand_l=(-18, 24, SACH_Z - 3), hand_r=(18, 24, SACH_Z - 3))
    step(ang, 'foot_r', 4.05, 4.45, (7.6, 0, SACH_Z + 1.5), (8.4, 0, SACH_Z + 5.0), 180, 176, lift=1.8)
    ang.key(4.9, hip=(0, 33.2, SACH_Z + 2.6), pelvis_rot=(180, 8, 0), chest=(0, 10, 0), head=(0, 6, 0),
            hand_l=(-15, 34, SACH_Z - 5), hand_r=(15, 34, SACH_Z - 5), elbow_l=(-0.8, -0.5, 0.5), elbow_r=(0.8, -0.5, 0.5))


# --------------------------------------------------------------- 5.0 - 8.0
def charge(eva, ang):
    # coil low behind the torn field
    eva.key(5.3, hip=(0, 29.2, 1.8), pelvis_rot=(0, 30, 0), chest=(0, 16, 0), head=(0, -24, 0), jaw=20.0,
            hand_l=(9.5, 25.0, -4.0), hand_r=(-9.5, 25.0, -4.0), elbow_l=(0.5, 0.2, -1.0), elbow_r=(-0.5, 0.2, -1.0),
            shoulder_l=(2, -8), shoulder_r=(2, -8), wrist_l=(-10, 0, 0), wrist_r=(-10, 0, 0))
    eva.key(5.3, foot_l=(5.8, 0, 8.0), foot_r=(-7.2, 0, 5.5))
    step(eva, 'foot_r', 5.32, 5.76, (-7.2, 0, 5.5), (-5.4, 0, 17.0), -12, -4, lift=4.0)
    step(eva, 'foot_l', 5.68, 6.12, (5.8, 0, 8.0), (5.6, 0, 26.0), 6, 6, lift=4.0)
    step(eva, 'foot_r', 6.08, 6.46, (-5.4, 0, 17.0), (-7.0, 0, 23.5), -4, -12, lift=2.2)
    eva.key(5.55, hip=(0, 31.8, 8.5), pelvis_rot=(0, 28, 0), chest=(0, 10, 0), head=(0, -20, 0),
            hand_l=(8.0, 32.0, 18.0), hand_r=(-9.5, 28.0, 2.5))
    eva.key(5.92, hip=(0, 32.6, 16.5), pelvis_rot=(0, 24, 0), chest=(0, 8, 0), head=(0, -18, 0),
            hand_l=(9.5, 28.0, 11.0), hand_r=(-8.0, 32.5, 27.5))
    eva.key(6.3, hip=(0, 31.6, 21.0), pelvis_rot=(0, 12, 0), chest=(0, 2, 0), head=(0, -18, 0), jaw=24.0,
            hand_l=(11.0, 34.0, 30.0), hand_r=(-11.0, 34.0, 29.0), elbow_l=(0.9, -0.6, -0.3), elbow_r=(-0.9, -0.6, -0.3))
    # it squares up under the angel, roaring, arms open to grab
    eva.key(6.8, hip=(0, 32.2, 21.4), pelvis_rot=(0, 6, 0), chest=(0, -6, 0), head=(0, -24, 0), jaw=40.0,
            hand_l=(13.5, 41.0, 33.0), hand_r=(-13.5, 40.0, 33.0), shoulder_l=(6, 4), shoulder_r=(6, 4),
            elbow_l=(1.0, -0.5, -0.2), elbow_r=(-1.0, -0.5, -0.2), wrist_l=(-30, 0, 0), wrist_r=(-30, 0, 0))
    eva.key(7.6, hip=(0, 31.8, 21.6), pelvis_rot=(0, 8, 0), chest=(0, -8, 0), head=(0, -28, 0), jaw=30.0,
            hand_l=(11.0, 47.0, 35.0), hand_r=(-9.0, 46.0, 35.0))
    # Sachiel rears up and cocks its right claw high, then hacks down at the head
    ang.key(5.6, hip=(0, 34.4, SACH_Z + 2.4), pelvis_rot=(180, -2, 0), chest=(0, -6, 0), head=(0, -6, 0),
            hand_l=(-17, 30, SACH_Z - 6), hand_r=(17, 40, SACH_Z - 2))
    ang.key(6.9, hip=(0, 35.0, SACH_Z + 2.8), pelvis_rot=(180, -8, 5), chest=(-12, -14, 0), head=(-6, -10, 0),
            hand_l=(-16, 32, SACH_Z - 9), hand_r=(15, 86, SACH_Z + 4), elbow_r=(0.9, 0.2, 0.4),
            elbow_l=(-0.8, -0.5, 0.5))
    ang.key(7.55, hip=(0, 34.6, SACH_Z + 3.2), pelvis_rot=(180, -10, 6), chest=(-16, -16, 0), head=(-8, -12, 0),
            hand_r=(14, 88, SACH_Z + 7), ease='flat')
    ang.key(8.0, hip=(0, 33.6, SACH_Z + 1.0), pelvis_rot=(180, 14, -4), chest=(8, 16, 0), head=(4, 8, 0),
            hand_r=((6.0, 47.0, 39.0), 'fast'), elbow_r=(0.8, -0.2, 0.6), hand_l=(-15, 30, SACH_Z - 10))


# --------------------------------------------------------------- 8.0 - 9.7
def wrench(eva, ang):
    # the catch at arm's length: Unit-01's hands are slaved to Sachiel's right forearm (see contacts)
    eva.key(8.05, hip=(0, 31.4, 20.6), pelvis_rot=(0, 8, 0), chest=(0, -2, 0), head=(0, -16, 0), jaw=26.0)
    # haul the arm down to its right hip, leaning back: the angel is dragged a step in
    eva.key(8.5, hip=(-1.0, 31.2, 19.6), pelvis_rot=(-14, -8, -3), chest=(-20, -6, -4), head=(-10, -6, 0), jaw=36.0)
    # chamber the left knee high while still hauling
    eva.key(8.6, foot_l=(5.6, 0, 26.0), foot_l_rot=(6, 0, 0))
    eva.key(8.7, knee_l_down=0.0)
    eva.key(8.95, foot_l=(4.4, 15.0, 26.0), foot_l_rot=(4, 10, 0), knee_l=0.0, knee_l_down=3.0)
    eva.key(8.95, hip=(-0.6, 32.6, 19.4), pelvis_rot=(-8, -14, 0), chest=(-10, 4, 0), head=(-4, -4, 0), jaw=30.0)
    # the push kick lands flat-footed in the belly at 9.2, the leg driving straight
    eva.key(9.2, foot_l=((2.0, 36.5, 45.6), 'fast'), foot_l_rot=(0, 72, 0), knee_l_down=3.0)
    eva.key(9.34, foot_l=(2.0, 37.5, 48.4), foot_l_rot=(0, 70, 0))
    eva.key(9.58, foot_l=(4.0, 14.0, 31.0), foot_l_rot=(2, 0, 0), knee_l_down=1.0)
    eva.key(9.8, knee_l_down=0.0)
    eva.key(9.8, foot_l=(5.6, 0, 28.0), foot_l_rot=(6, 0, 0), ease='flat')
    eva.key(9.2, hip=(0.2, 33.4, 20.2), pelvis_rot=(-4, -26, 0), chest=(0, 12, 0), head=(0, 10, 0), jaw=40.0,
            hand_l=(13.0, 38.0, 19.0), hand_r=(-13.0, 36.0, 17.0), elbow_l=(0.8, -0.6, -0.3), elbow_r=(-0.8, -0.6, -0.3))
    eva.key(9.4, hip=(0.0, 33.0, 21.0), pelvis_rot=(0, -20, 0), chest=(0, 8, 0), head=(0, 2, 0))
    eva.key(9.85, hip=(0, 31.6, 24.0), pelvis_rot=(0, 12, 0), chest=(0, 6, 0), head=(0, -12, 0), jaw=12.0,
            hand_l=(9.5, 31.0, 28.0), hand_r=(-9.5, 31.0, 26.0))
    # Sachiel stumbles in on its stretched arm, upright enough to take the foot in the belly
    step(ang, 'foot_l', 8.2, 8.62, (-7.6, 0, SACH_Z + 1.5), (-6.8, 0, SACH_Z - 4.5), 180, 186, lift=2.2)
    ang.key(8.5, hip=(0, 32.4, SACH_Z - 2.0), pelvis_rot=(180, 18, -8), chest=(8, 12, 0), head=(6, 8, 0),
            hand_r=(-3.0, 33.0, 26.0), elbow_r=(0.4, 0.8, 0.5), hand_l=(-17, 28, SACH_Z - 12))
    ang.key(9.0, hip=(0, 32.4, SACH_Z - 2.2), pelvis_rot=(180, 14, -6), chest=(4, 10, 0), head=(4, 8, 0),
            hand_r=(-2.0, 33.0, 26.0), hand_l=(-17, 30, SACH_Z - 13))
    ang.key(9.2, hip=(0, 32.6, SACH_Z - 2.0), pelvis_rot=(180, 10, -4), chest=(0, 8, 0), head=(0, 10, 0),
            break_r=0.0)
    ang.key(9.3, break_r=55.0)


# --------------------------------------------------------------- 9.2 - 10.9 Sachiel thrown down
LIE_Z = 66.0


def flight(eva, ang):
    ang.key(9.45, hip=(0, 37.0, 54.0), pelvis_rot=(180, -18, 4), chest=(0, -16, 0), head=(0, -26, 0),
            hand_l=(-26, 42, 48), hand_r=(22, 30, 44), elbow_l=(-0.6, 0.2, 0.8), elbow_r=(0.6, 0.2, 0.8))
    ang.key(9.75, hip=(0, 34.0, 57.5), pelvis_rot=(180, -42, 2), chest=(0, -14, 0), head=(0, -22, 0),
            hand_l=(-28, 44, 60), hand_r=(25, 36, 55))
    ang.key(10.1, hip=(0, 18.0, 63.0), pelvis_rot=(180, -74, -6), chest=(0, -10, 0), head=(0, -18, 0),
            hand_l=(-28, 30, 72), hand_r=(27, 26, 70))
    ang.key(10.4, hip=((0, 4.6, LIE_Z), 'fast'), pelvis_rot=((180, -90, 0), 'fast'), chest=(0, -6, 0), head=(0, -10, 0),
            hand_l=(-27, 4, 78), hand_r=(25, 4, 75))
    ang.key(10.6, hip=(0, 6.0, LIE_Z + 0.6), pelvis_rot=(180, -85, 0), chest=(0, 3, 0), head=(0, 5, 0))
    ang.key(10.9, hip=(0, 4.6, LIE_Z + 0.8), pelvis_rot=(180, -90, 0), chest=(0, 0, 0), head=(0, -6, 0),
            hand_l=(-24, 3.5, 76), hand_r=(24, 3.5, 74), elbow_l=(-0.8, 1.0, 0.2), elbow_r=(0.8, 1.0, 0.2))
    # legs: the planted feet leave the ground, swing up, then slap down straight out along the ground
    ang.key(9.25, foot_l=(-6.8, 0, SACH_Z - 4.5), foot_r=(7.6, 0, SACH_Z + 1.5), foot_l_rot=(188, 0, 0), foot_r_rot=(180, 0, 0))
    ang.key(9.55, foot_l=(-7.0, 8.0, 44.0), foot_r=(8.0, 10.0, 47.0), foot_l_rot=(186, -40, 0), foot_r_rot=(176, -40, 0))
    ang.key(10.1, foot_l=(-8.0, 26.0, 46.0), foot_r=(8.5, 30.0, 48.0), foot_l_rot=(186, -80, 0), foot_r_rot=(176, -80, 0),
            knee_l_down=-1.0, knee_r_down=-1.0)
    ang.key(10.42, foot_l=(-7.0, 8.0, 39.0), foot_r=(7.5, 10.0, 40.0), foot_l_rot=(186, -70, 0), foot_r_rot=(176, -70, 0),
            knee_l_down=-2.5, knee_r_down=-2.5)
    ang.key(10.7, foot_l=(-6.5, 3.4, 37.5), foot_r=(6.5, 3.4, 38.0), foot_l_rot=(186, -86, 0), foot_r_rot=(176, -86, 0),
            knee_l_down=-3.0, knee_r_down=-3.0, ease='flat')


# --------------------------------------------------------------- 9.8 - 12.4 leap and mount
KNEEL_Z = 68.0


def leap(eva, ang):
    step(eva, 'foot_r', 9.8, 10.22, (-7.0, 0, 23.5), (-6.4, 0, 31.0), -12, -8, lift=2.0)
    eva.key(10.22, foot_l=(5.6, 0, 28.0), foot_l_rot=(6, 0, 0))
    eva.key(10.22, hip=(0, 31.4, 26.4), pelvis_rot=(0, 14, 0), chest=(0, 6, 0), head=(0, -16, 0),
            hand_l=(9.0, 30.0, 29.0), hand_r=(-9.0, 30.0, 29.0))
    # load: deep crouch, arms swung back
    eva.key(10.62, hip=(0, 24.0, 25.6), pelvis_rot=(0, 34, 0), chest=(0, 14, 0), head=(0, -30, 0), jaw=20.0,
            hand_l=(11.0, 22.0, 19.0), hand_r=(-11.0, 22.0, 19.0), elbow_l=(1.0, 0.3, -0.3), elbow_r=(-1.0, 0.3, -0.3),
            foot_l=(5.6, 0, 28.0), foot_r=(-6.4, 0, 31.0), foot_l_rot=(6, 0, 0), foot_r_rot=(-8, 0, 0))
    # drive: legs extend, arms whip up, feet leave the ground at 10.82
    eva.key(10.82, hip=(0, 36.5, 31.5), pelvis_rot=(0, 18, 0), chest=(0, 0, 0), head=(0, -20, 0), jaw=34.0,
            hand_l=(9.0, 64.0, 44.0), hand_r=(-9.0, 64.0, 44.0), elbow_l=(1.0, -0.2, -0.2), elbow_r=(-1.0, -0.2, -0.2))
    eva.key(10.8, foot_l=(5.6, 0, 28.0), foot_r=(-6.4, 0, 31.0), foot_l_rot=(6, -26, 0), foot_r_rot=(-8, -26, 0))
    eva.key(10.67, hand_l=(11.0, 22.5, 36.0), hand_r=(-11.0, 22.5, 36.0))
    eva.key(10.72, hand_l=(9.5, 43.0, 51.0), hand_r=(-9.5, 43.0, 51.0))
    # flight: knees tucked, fists high
    eva.key(11.25, hip=(0, 50.0, 51.0), pelvis_rot=(0, 6, 0), chest=(0, -6, 0), head=(0, -10, 0),
            hand_l=(7.0, 72.0, 52.0), hand_r=(-7.0, 72.0, 52.0),
            foot_l=(6.5, 30.0, 52.0), foot_r=(-6.5, 30.0, 50.0), foot_l_rot=(8, -20, 0), foot_r_rot=(-8, -20, 0))
    eva.key(11.55, hip=(0, 40.0, 63.0), pelvis_rot=(0, 10, 0), chest=(0, -2, 0), head=(0, -6, 0),
            hand_l=(7.0, 64.0, 63.0), hand_r=(-7.0, 64.0, 63.0),
            foot_l=(12.0, 9.0, 66.0), foot_r=(-12.0, 9.0, 65.0), foot_l_rot=(14, -6, 0), foot_r_rot=(-14, -6, 0))
    # land astride the angel's waist (EVA_LAND at 11.7), absorb, then drop the knees
    eva.key(11.7, foot_l=(13.0, 0, 66.5), foot_r=(-13.0, 0, 66.0), foot_l_rot=(16, 0, 0), foot_r_rot=(-16, 0, 0), ease='flat')
    eva.key(11.7, hip=((0, 30.0, 66.0), 'fast'), pelvis_rot=(0, 22, 0), chest=(0, 12, 0), head=(0, 0, 0), jaw=28.0,
            hand_l=(9.0, 50.0, 70.0), hand_r=(-9.0, 50.0, 70.0), knee_l=24.0, knee_r=-24.0)
    eva.key(11.88, hip=(0, 24.0, 66.4), pelvis_rot=(0, 30, 0), chest=(0, 18, 0), head=(0, 6, 0),
            hand_l=(10.0, 38.0, 72.0), hand_r=(-10.0, 38.0, 72.0))
    kneel(eva, 11.95, 12.4)


def kneel_controls(z=KNEEL_Z, spread=12.5):
    """Knees on the ground either side of the angel's waist, shins flat behind, toes tucked."""
    return dict(foot_l=(spread + 0.6, 0, z - 16.2), foot_r=(-spread - 0.6, 0, z - 16.4),
                foot_l_rot=(10, -62, 0), foot_r_rot=(-10, -62, 0), knee_l=10.0, knee_r=-10.0,
                knee_l_down=-1.2, knee_r_down=-1.2)


def kneel(eva, t0, t1):
    k = kneel_controls()
    eva.key(t0, foot_l=(13.0, 0, 66.5), foot_r=(-13.0, 0, 66.0), foot_l_rot=(16, 0, 0), foot_r_rot=(-16, 0, 0), ease='flat')
    eva.key(t0 + 0.07, foot_l=(13.0, 2.4, 65.6), foot_r=(-13.0, 2.4, 65.1), foot_l_rot=(15, -16, 0), foot_r_rot=(-15, -16, 0))
    eva.key((t0 + t1) / 2, foot_l=(13.0, 4.0, 60.0), foot_r=(-13.0, 4.0, 59.5), foot_l_rot=(12, -40, 0), foot_r_rot=(-12, -40, 0))
    eva.key(t1, ease='flat', **k)
    eva.key(t1, hip=(0, 17.0, KNEEL_Z), pelvis_rot=(0, 6, 0), chest=(0, 8, 0), head=(0, 10, 0), jaw=20.0,
            hand_l=(9.0, 30.0, 76.0), hand_r=(-9.0, 30.0, 76.0), elbow_l=(0.8, -0.4, -0.5), elbow_r=(-0.8, -0.4, -0.5))


# --------------------------------------------------------------- 12.4 - 16.35 ground and pound
BLOWS = (12.75, 13.35, 14.15, 14.75, 15.35, 16.05)


def pound(eva, ang):
    """Hands are keyed relative to Sachiel's core (channels pound_l/pound_r, see contacts)."""
    both_up = ((2.2, 37.0, -11.0), (-2.2, 37.0, -11.0))
    both_hit = ((2.3, 2.6, -0.4), (-2.3, 2.6, -0.4))
    plans = [  # (raise time, impact, kind)
        (12.58, 12.75, 'both'), (13.18, 13.35, 'both'), (13.95, 14.15, 'right'),
        (14.56, 14.75, 'left'), (15.17, 15.35, 'both'), (15.84, 16.05, 'final')]
    eva.key(12.4, pound_l=(5.0, 20.0, -3.0), pound_r=(-5.0, 20.0, -3.0), pound_w=0.0)
    eva.key(12.5, pound_w=1.0)
    for raise_t, hit, kind in plans:
        if kind in ('both', 'final'):
            up = both_up if kind == 'both' else ((2.0, 40.0, -13.0), (-2.0, 40.0, -13.0))
            eva.key(raise_t, ease='flat', pound_l=up[0], pound_r=up[1])
            eva.key(raise_t, elbow_l=(1.0, 0.1, -0.3), elbow_r=(-1.0, 0.1, -0.3))
            if kind == 'final':
                eva.key(raise_t + 0.06, ease='flat', pound_l=up[0], pound_r=up[1])
            eva.key(hit - 0.06, pound_l=(2.3, 21.0, 6.5), pound_r=(-2.3, 21.0, 6.5))
            eva.key(hit, pound_l=(both_hit[0], 'fast'), pound_r=(both_hit[1], 'fast'))
            body_up = dict(hip=(0, 18.6 if kind == 'both' else 20.0, KNEEL_Z - 0.6), pelvis_rot=(0, -6 if kind == 'both' else -10, 0),
                           chest=(0, -22 if kind == 'both' else -30, 0), head=(0, 4, 0), jaw=30.0,
                           elbow_l=(0.7, 0.3, -0.6), elbow_r=(-0.7, 0.3, -0.6))
            body_hit = dict(hip=(0, 16.0, KNEEL_Z + 0.8), pelvis_rot=(0, 20, 0), chest=(0, 32, 0), head=(0, 26, 0), jaw=40.0,
                            elbow_l=(0.9, -0.3, -0.4), elbow_r=(-0.9, -0.3, -0.4))
        else:
            s = 1 if kind == 'left' else -1
            strike = 'pound_l' if kind == 'left' else 'pound_r'
            brace = 'pound_r' if kind == 'left' else 'pound_l'
            eva.key(raise_t, ease='flat', **{strike: (s * 6.0, 36.0, -10.0), brace: (-s * 6.5, 2.4, -3.5)})
            eva.key(raise_t, elbow_l=(1.0, 0.1, -0.3), elbow_r=(-1.0, 0.1, -0.3))
            eva.key(hit - 0.06, **{strike: (s * 2.0, 21.0, 6.0)})
            eva.key(hit, **{strike: ((s * 1.2, 2.6, -0.2), 'fast'), brace: (-s * 6.5, 2.4, -3.5)})
            body_up = dict(hip=(0, 18.2, KNEEL_Z - 0.4), pelvis_rot=(0, -2, -4 * s), chest=(s * 18, -14, 0), head=(s * 6, 6, 0),
                           jaw=32.0)
            body_hit = dict(hip=(0, 16.2, KNEEL_Z + 0.6), pelvis_rot=(0, 18, 4 * s), chest=(-s * 14, 28, 0), head=(-s * 4, 24, 0),
                            jaw=40.0)
        eva.key(raise_t, ease='flat', **body_up)
        eva.key(hit, **{k: (v, 'fast') if k in ('hip', 'chest', 'pelvis_rot') else v for k, v in body_hit.items()})
        # recoil off the core, then the fists come back up in front of the chest
        rec = hit + 0.08
        eva.key(rec, pound_l=(2.7, 5.4, -1.0), pound_r=(-2.7, 5.4, -1.0))
        nxt = plans[plans.index((raise_t, hit, kind)) + 1][2] if hit != BLOWS[-1] else None
        if nxt in ('both', 'final', 'left'):
            eva.key(rec + 0.2, pound_l=(3.2, 21.0, 3.0))
        if nxt in ('both', 'final', 'right'):
            eva.key(rec + 0.2, pound_r=(-3.2, 21.0, 3.0))
        eva.key(rec, hip=(0, 16.4, KNEEL_Z + 0.4), pelvis_rot=(0, 16, 0), chest=(0, 24, 0), head=(0, 20, 0))
    # after the last blow: fists stay ground into the cracked core
    eva.key(16.3, pound_l=(2.6, 3.4, -0.8), pound_r=(-2.6, 3.4, -0.8), hip=(0, 16.0, KNEEL_Z + 0.6),
            pelvis_rot=(0, 18, 0), chest=(0, 28, 0), head=(0, 24, 0), jaw=24.0)
    # Sachiel convulses under each blow
    for hit in BLOWS:
        big = 1.6 if hit == BLOWS[-1] else 1.0
        ang.key(hit - 0.04, hip=(0, 4.6, LIE_Z + 0.8), pelvis_rot=(180, -90, 0), chest=(0, 0, 0), head=(0, -6, 0))
        ang.key(hit + 0.05, hip=(0, 3.9, LIE_Z + 0.8), pelvis_rot=(180, -94 * 1.0, 0), chest=(0, 12 * big, 0),
                head=(0, 22 * big, 0))
        ang.key(hit + 0.22, hip=(0, 4.6, LIE_Z + 0.8), pelvis_rot=(180, -90, 0), chest=(0, 3, 0), head=(0, 4, 0))
    # its free left claw grabs at Unit-01's right forearm, then flails
    ang.key(12.9, hand_l=(-24, 3.5, 76))
    ang.key(13.6, hand_l=(-14, 20, 70), elbow_l=(-1.0, 0.2, 0.3))
    ang.key(14.4, hand_l=(-12, 22, 68))
    ang.key(15.2, hand_l=(-22, 6, 74), elbow_l=(-0.8, 1.0, 0.2))


# --------------------------------------------------------------- 16.3 - 18.6 the self-destruct embrace
def embrace(eva, ang):
    """Sachiel curls up off the ground and locks its arms round Unit-01's back; Unit-01, still
    bent over it, braces both hands on the ground and heaves to break free, and is dragged back."""
    eva.key(16.42, pound_w=1.0)
    eva.key(16.62, pound_w=0.0)
    ground_l, ground_r = (12.5, 2.4, 80.5), (-12.5, 2.4, 80.0)
    eva.key(16.62, hand_l=ground_l, hand_r=ground_r, elbow_l=(1.0, 0.4, -0.2), elbow_r=(-1.0, 0.4, -0.2))
    # pulled down onto the angel's chest
    eva.key(16.75, hip=(0, 16.4, KNEEL_Z + 1.2), pelvis_rot=(0, 24, 0), chest=(0, 26, 0), head=(0, 6, 0), jaw=30.0)
    # heave up, dragged back, heave again
    eva.key(17.15, hip=(0, 18.6, KNEEL_Z - 0.4), pelvis_rot=(0, 16, 0), chest=(0, 4, 0), head=(0, -18, 0), jaw=42.0,
            shoulder_l=(6, -6), shoulder_r=(6, -6))
    eva.key(17.45, hip=(0, 16.8, KNEEL_Z + 0.8), pelvis_rot=(0, 24, 0), chest=(0, 22, 0), head=(0, 4, 0), jaw=26.0,
            shoulder_l=(0, 8), shoulder_r=(0, 8))
    eva.key(17.95, hip=(0, 19.4, KNEEL_Z - 0.8), pelvis_rot=(0, 14, -3), chest=(4, 0, 0), head=(-6, -24, 0), jaw=44.0,
            shoulder_l=(8, -8), shoulder_r=(8, -8))
    eva.key(18.25, hip=(0, 17.4, KNEEL_Z + 0.6), pelvis_rot=(0, 22, 2), chest=(-4, 18, 0), head=(4, -2, 0), jaw=30.0)
    eva.key(18.55, hip=(0, 19.0, KNEEL_Z - 0.4), pelvis_rot=(0, 16, 0), chest=(0, 6, 0), head=(0, -20, 0), jaw=44.0)
    # Sachiel: the trunk stays on the ground, the chest curls up into Unit-01 and holds
    ang.key(16.35, hip=(0, 4.6, LIE_Z + 0.8), pelvis_rot=(180, -90, 0), chest=(0, 2, 0), head=(0, 0, 0))
    ang.key(16.75, chest=((0, 42, 0), 'fast'), head=(0, 26, 0))
    for t, c in ((17.15, 30), (17.45, 44), (17.95, 28), (18.25, 42), (18.55, 32)):
        ang.key(t, hip=(0, 4.6, LIE_Z + 0.8), pelvis_rot=(180, -90, 0), chest=(0, c, 0), head=(0, 20, 0))
    ang.key(16.4, hug_w=0.0)
    ang.key(16.8, hug_w=1.0)


# --------------------------------------------------------------- 18.6 - 23.0 aftermath
def aftermath(eva, ang):
    k = kneel_controls()
    # the blast throws the trunk back, then it slumps
    eva.key(18.6, hand_l=(10.0, 30.0, 74.0), hand_r=(-10.0, 30.0, 74.0))
    eva.key(18.82, hip=(0, 18.6, KNEEL_Z - 2.6), pelvis_rot=(0, -20, 0), chest=(0, -26, 0), head=(0, -30, 0), jaw=20.0,
            hand_l=(15.0, 42.0, 66.0), hand_r=(-15.0, 42.0, 66.0), elbow_l=(0.7, -0.7, -0.2), elbow_r=(-0.7, -0.7, -0.2))
    eva.key(19.5, hip=(0, 16.0, KNEEL_Z - 0.6), pelvis_rot=(0, 26, 0), chest=(0, 30, 0), head=(0, 36, 0), jaw=4.0,
            hand_l=(9.0, 3.0, 76.5), hand_r=(-9.0, 3.0, 76.0), elbow_l=(0.9, 0.2, -0.4), elbow_r=(-0.9, 0.2, -0.4))
    eva.key(19.9, hip=(0, 16.6, KNEEL_Z - 0.4), pelvis_rot=(0, 22, 0), chest=(0, 22, 0), head=(0, 14, 0))
    # left foot comes through to one knee (foot sound at 20.5)
    eva.key(19.95, foot_l=k['foot_l'], foot_l_rot=k['foot_l_rot'], ease='flat')
    eva.key(20.05, foot_l=(13.2, 2.6, 52.6), foot_l_rot=(10, -50, 0))
    eva.key(20.25, foot_l=(11.0, 8.0, 66.0), foot_l_rot=(9, -14, 0), knee_l_down=0.0)
    eva.key(20.42, foot_l=(7.6, 1.2, 75.2), foot_l_rot=(8, 2, 0))
    eva.key(20.5, foot_l=(7.5, 0, 75.5), foot_l_rot=(8, 0, 0), knee_l=10.0, ease='flat')
    eva.key(20.5, hip=(0, 19.0, KNEEL_Z + 1.0), pelvis_rot=(0, 14, 0), chest=(0, 12, 0), head=(0, 2, 0),
            hand_l=(10.0, 20.0, 76.0), hand_r=(-9.0, 18.0, 73.0))
    # stand on it, the right foot steps up (foot sound at 21.4)
    eva.key(20.95, hip=(0, 29.0, 71.6), pelvis_rot=(0, 18, 0), chest=(0, 8, 0), head=(0, -2, 0),
            hand_l=(8.5, 26.0, 74.0), hand_r=(-8.5, 25.0, 72.0))
    eva.key(20.95, foot_r=k['foot_r'], foot_r_rot=k['foot_r_rot'], ease='flat')
    eva.key(21.03, foot_r=(-13.2, 2.6, 52.4), foot_r_rot=(-10, -50, 0))
    eva.key(21.2, foot_r=(-9.0, 7.0, 65.0), foot_r_rot=(-9, -16, 0), knee_r_down=0.0)
    eva.key(21.33, foot_r=(-5.5, 1.2, 73.6), foot_r_rot=(-8, 2, 0))
    eva.key(21.4, foot_r=(-5.4, 0, 74.0), foot_r_rot=(-8, 0, 0), knee_r=-10.0, ease='flat')
    eva.key(21.6, foot_l=(7.5, 0, 75.5))
    step(eva, 'foot_l', 21.6, 21.95, (7.5, 0, 75.5), (5.4, 0, 74.6), 8, 6, lift=1.2)
    eva.key(21.9, hip=(0, 35.0, 72.0), pelvis_rot=(0, 4, 0), chest=(0, 2, 0), head=(0, 0, 0), jaw=0.0,
            hand_l=(8.4, 28.8, 74.2), hand_r=(-8.4, 28.8, 74.2), elbow_l=(0.5, -0.3, -1.0), elbow_r=(-0.5, -0.3, -1.0))
    eva.key(23.0, hip=(0, 35.6, 72.0), pelvis_rot=(0, 2, 0), chest=(0, 2, 0), head=(0, 2, 0),
            hand_l=(8.3, 29.2, 74.0), hand_r=(-8.3, 29.2, 74.0), knee_l=8.0, knee_r=-8.0)


# ------------------------------------------------------------------ layers
def tremor(t, t0, t1, amp, freq=8.0, seed=0.0):
    if t <= t0 or t >= t1:
        return 0.0
    env = math.sin(math.pi * (t - t0) / (t1 - t0)) ** 0.5
    return amp * env * (math.sin(2 * math.pi * freq * t + seed) * 0.6 + math.sin(2 * math.pi * freq * 1.73 * t + 2 * seed) * 0.4)


def eva_layers(t, c):
    c['chest'] = c['chest'] + np.array([tremor(t, 2.0, 4.9, 0.9, 9.0, 1.0), tremor(t, 2.0, 4.9, 0.7, 7.0, 2.0),
                                        tremor(t, 2.0, 4.9, 0.9, 8.0, 3.0)])
    c['head'] = c['head'] + np.array([tremor(t, 0.7, 1.4, 2.5, 11.0), tremor(t, 0.7, 1.4, 1.5, 9.0, 1.3), 0])
    return c


def window(t, a, b, c, d):
    """0 before a, eased up to 1 by b, 1 until c, eased down to 0 by d."""
    if t <= a or t >= d:
        return 0.0
    if t < b:
        return anim.smooth((t - a) / (b - a))
    if t <= c:
        return 1.0
    return 1.0 - anim.smooth((t - c) / (d - c))


SACH_R_ELBOW = np.array([54.410686, 108.749362, 6.75443]) / 16
SACH_R_HAND = np.array([54.410686, 108.749362, -34.572077]) / 16


# Unit-01's shoulder tops (baked model px): Sachiel's claws clamp them from below and drag down
EVA_SHOULDER = {'l': np.array([-21.0, 153.0, -1.0]) / 16, 'r': np.array([21.0, 153.0, -1.0]) / 16}
SACH_PUSH = {'l': np.array([-13.0, 170.0, -10.0]) / 16, 'r': np.array([13.0, 170.0, -10.0]) / 16}


def _toward(grip, origin, back):
    d = grip - origin
    return grip - back * d / np.linalg.norm(d)


def eva_contacts(t, ce, am, core):
    hip = np.asarray(ce['hip'], float)
    # catch to kick: both hands clamp Sachiel's right forearm like a bat; the right lets go first
    fa = am['forearm_r']
    for side, frac, w in (('l', 0.86, window(t, 7.9, 8.0, 9.16, 9.26)), ('r', 0.52, window(t, 7.9, 8.0, 8.92, 9.04))):
        if w <= 0:
            continue
        grip = B.point(fa, SACH_R_ELBOW + frac * (SACH_R_HAND - SACH_R_ELBOW))
        shoulder = hip + np.array([6.0 if side == 'l' else -6.0, 12.6, 3.0])
        ce['hand_' + side] = ce['hand_' + side] * (1 - w) + _toward(grip, shoulder, 2.6) * w
    # ground and pound: fists are keyed relative to the core
    w = float(np.ravel(ce['pound_w'])[0])
    if w > 0:
        for side in 'lr':
            ce['hand_' + side] = ce['hand_' + side] * (1 - w) + (core + ce['pound_' + side]) * w
    return ce


def angel_contacts(t, ca, em):
    w = float(np.ravel(ca['hug_w'])[0])
    if w > 0:
        tu = em['torso_upper']
        for side, s2 in (('l', 'r'), ('r', 'l')):
            ca['hand_' + side] = ca['hand_' + side] * (1 - w) + B.point(tu, EVA_SHOULDER[s2]) * w
            ca['elbow_' + side] = np.array([-1.0 if side == 'l' else 1.0, -0.6, 0.1])
    return ca


class Scene:
    def __init__(self, actors):
        self.actors = actors
        self.eva_body = B.EvaBody(actors.eva_rig)
        self.eva_body.foot_points = {side: np.concatenate([tris.reshape(-1, 3) for bone, tris, _ in actors.eva_mesh.parts
                                                           if bone == 'foot_' + side])[::3] for side in 'lr'}
        self.ang_body = B.AngelBody(actors.angel_rig)
        self.eva, self.ang = build()

    def solve(self, t):
        ca = self.ang.sample(t)
        ar, ap, am, ai = self.ang_body.solve(ca)
        core = self.ang_body.core_world(am)
        ce = eva_contacts(t, eva_layers(t, self.eva.sample(t)), am, core)
        er, ep, em, ei = self.eva_body.solve(ce)
        if float(np.ravel(ca['hug_w'])[0]) > 0:
            ca = angel_contacts(t, ca, em)
            ar, ap, am, ai = self.ang_body.solve(ca)
            # Unit-01 wrenches at the wrists clamped on its shoulders (its trunk does not depend on its hands)
            w = window(t, 16.8, 17.0, 18.62, 18.8)
            if w > 0:
                hip = np.asarray(ce['hip'], float)
                for side, s2 in (('l', 'r'), ('r', 'l')):
                    fa = am['forearm_' + s2]
                    el = np.array([54.410686 if s2 == 'r' else -54.410686, 108.749362, 6.75443]) / 16
                    hd = np.array([el[0], 108.749362 / 16, -34.572077 / 16])
                    grip = B.point(fa, el + 0.7 * (hd - el))
                    shoulder = hip + np.array([6.0 if side == 'l' else -6.0, 12.6, 0.0])
                    ce['hand_' + side] = ce['hand_' + side] * (1 - w) + _toward(grip, shoulder, 2.4) * w
                er, ep, em, ei = self.eva_body.solve(ce)
        return {'eva': (er, ep, em, ei, ce), 'angel': (ar, ap, am, ai, ca), 'core': core}
