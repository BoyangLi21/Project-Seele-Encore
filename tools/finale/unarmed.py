"""Unit-01's bare hands as the attack plan has them: python unarmed.py out.json [sheet folder|-] [move ...]

The frames core's bare hands were a boxer's: jab, cross, jab. In the original Unit-01 does not box. It goes at an
Angel with its whole body: throws itself on it, drives a knee into it, takes hold of it and beats on its core,
runs into it. These are those, each written from the way the Unit stands and back to it (tools/finale/moves.py),
nothing of them captured and nothing taken from the original's pictures:

  pounce   (the light press) a stride in on the left foot, the trunk thrown down over it, the right hand brought
           over from beside the head and down onto the mark like a claw, the left reaching for it underneath;
  knee     (the light press after it) both hands on the mark, a short spring off the left foot, and the right knee
           driven up into it as the hands pull it down and the trunk goes back against the leg.

The third light press is the two-fisted slam the Unit had (its own clip). The charge and the beating of a held
Angel are written here as they are made.

A clip's root path is the stride its row may take; the game takes as much of it as brings the mark to the blow's
reach (EvaCombatMachineR64), and holds a foot that is stood on where it is in the world.
"""
import os
import sys

import numpy as np

import moves as M
from moves import key

# The rows as EvaMoveTableR64 has them: start-up, live, recovery, how far the live part reaches before and after the
# clip's contact, and where on the clip the contact is.
POUNCE = M.Row(6, 3, 12, .030, .100, .340)
KNEE = M.Row(6, 3, 13, .030, .090, .330)
CHARGE = M.Row(4, 6, 12, .030, .230, .210)
POUNCE_STRIDE, KNEE_SPRING, CHARGE_LEAP = 8.0, 17.0, 16.0


def pounce(stage):
    hit = POUNCE.place(POUNCE.contact)
    s = POUNCE_STRIDE
    keys = [
        (0.0, key()),
        # gathered: the weight back over the right foot, the hips down and folding, the right hand up beside the head
        (1.7, key(hip=(-1.0, -1.0), high=-2.2, tuck=-8, yaw=-10, chest=-12, lean=-4, ltoe=-6,
                  rreach=1, rhand=(-6.0, -7.0, -9.0), relbow=(-1.5, .3, -.4),
                  larm=(0, 2.0, 3.0))),
        # thrown forward: the left foot off the ground and going out, the trunk coming down, the right hand over the top
        (3.6, key(adv=.42 * s, hip=(-.3, .4), high=-3.4, tuck=-18, yaw=-5, chest=-6, lean=-10, rtoe=-8,
                  rreach=1, rhand=(-4.0, 15.0, -6.0), relbow=(-1.5, .3, -.4),
                  lreach=1, lhand=(1.0, -7.0, 9.0), lelbow=(2.0, -.6, .5))),
        # the left foot down a stride on, the body over it
        (5.3, key(adv=.9 * s, hip=(.3, 1.6), high=-5.0, tuck=-26, yaw=6, chest=10, lean=-15, nod=4, rtoe=-16,
                  rreach=1, rhand=(1.5, 13.0, 8.5), relbow=(-1.4, .4, -.2),
                  lreach=1, lhand=(0, -5.0, 12.0), lelbow=(2.0, -.6, .5))),
        # the hand on its mark
        (hit, key(adv=s, hip=(.5, 2.2), high=-5.6, tuck=-30, yaw=10, chest=16, lean=-18, nod=8, rtoe=-20,
                  rreach=1, rhand=(4.0, 3.5, 15.0), relbow=(-1.0, .6, 0),
                  lreach=1, lhand=(-.5, -4.5, 13.5), lelbow=(2.0, -.6, .5))),
        # dragged down through it
        (hit + 2.3, key(adv=s, hip=(.5, 2.4), high=-6.6, tuck=-33, yaw=12, chest=18, lean=-21, nod=10, rtoe=-22,
                        rreach=1, rhand=(5.0, -5.5, 12.5), relbow=(-1.0, .6, 0),
                        lreach=1, lhand=(-.5, -7.0, 11.5), lelbow=(2.0, -.6, .5))),
        # coming up: the right foot leaves the ground behind and comes on under the body
        (12.2, key(adv=s, hip=(.6, 1.0), high=-3.6, tuck=-16, yaw=4, chest=6, lean=-10, nod=3,
                   rreach=.45, rhand=(2.0, -9.0, 8.0), rarm=(0, 2.0, 4.0), relbow=(-.5, .3, 0),
                   lreach=.5, lhand=(.5, -9.0, 7.0), larm=(0, 1.0, 2.0), lelbow=(1.0, -.3, .25))),
        (15.6, key(adv=s, hip=(.2, .3), high=-1.2, tuck=-5, lean=-3, rtoe=-4,
                   rarm=(0, 1.0, 2.0), larm=(0, 1.0, 1.6))),
        (float(POUNCE.total), key(adv=s)),
    ]
    steps = {'l': [(2.6, 4.6, (0, s), 1.7)], 'r': [(10.4, 14.2, (0, s), 1.6)]}
    return keys, [0, 1.7, 3.6, 5.3, hit, hit + 2.3, 12.2, 15.6, POUNCE.total], steps


def knee(stage):
    hit = KNEE.place(KNEE.contact)
    s = KNEE_SPRING
    out_l, out_r = (2.0, -.6, .5), (-2.0, -.6, .5)
    keys = [
        (0.0, key()),
        # both hands on the mark, the weight going over the left foot
        (1.8, key(hip=(1.5, 1.0), high=-1.5, tuck=-4, lean=-4, rtoe=-10,
                  lreach=.75, lhand=(-.5, -7.0, 12.0), lelbow=out_l, rreach=.75, rhand=(.5, -7.0, 12.0), relbow=out_r)),
        # the spring: the left foot pushes off, the right leg coming through
        (3.8, key(adv=.25 * s, hip=(2.0, 2.2), high=1.5, tuck=4, lean=1, ltoe=-24,
                  rfree=.7, rflex=22, rknee=78,
                  lreach=1, lhand=(-1.0, -5.5, 13.5), lelbow=out_l, rreach=1, rhand=(1.0, -5.5, 13.5), relbow=out_r)),
        # in the air, the knee going up and in
        (5.2, key(adv=.75 * s, hip=(2.3, 3.6), high=5.4, tuck=10, lean=7, ltoe=-14,
                  rfree=1, rflex=52, rknee=108,
                  lreach=1, lhand=(-1.2, -9.0, 12.0), lelbow=out_l, rreach=1, rhand=(1.2, -9.0, 12.0), relbow=out_r)),
        # the knee meets its mark still going in, at the top of the leap
        (hit, key(adv=s, hip=(2.4, 4.0), high=6.5, tuck=12, lean=9, ltoe=-12,
                  rfree=1, rflex=86, rknee=124,
                  lreach=1, lhand=(-1.4, -11.5, 11.0), lelbow=out_l, rreach=1, rhand=(1.4, -11.5, 11.0), relbow=out_r)),
        # driven home
        (hit + 1.4, key(adv=s, hip=(2.5, 5.4), high=5.6, tuck=16, lean=13, ltoe=-7,
                        rfree=1, rflex=96, rknee=128,
                        lreach=1, lhand=(-1.5, -14.0, 10.0), lelbow=out_l, rreach=1, rhand=(1.5, -14.0, 10.0), relbow=out_r)),
        # the leg coming down, the hands letting go
        (11.6, key(adv=s, hip=(1.8, 2.4), high=-.4, tuck=6, lean=3,
                   rfree=.75, rflex=46, rknee=86,
                   lreach=.5, lhand=(-.5, -13.0, 7.0), larm=(0, 1.0, 2.0), lelbow=(1.0, -.3, .25),
                   rreach=.5, rhand=(.5, -13.0, 7.0), rarm=(0, 1.0, 2.0), relbow=(-1.0, -.3, .25))),
        (15.4, key(adv=s, hip=(.5, .5), high=-.6, lean=-2, rtoe=-8,
                   larm=(0, 1.0, 1.5), rarm=(0, 1.0, 1.5))),
        (float(KNEE.total), key(adv=s)),
    ]
    # (the right leg is carried by its thigh and knee from the spring until it is set down)
    # (a leap: the knee goes in at the height of the chest with both feet off the ground, where the mark is nearest;
    # at the height of the hip it met nothing, a Sachiel's belly being five blocks behind its chest)
    steps = {'l': [(3.6, 9.6, (0, s), 9.5)], 'r': [(2.6, 14.0, (0, s), 0.0)]}
    return keys, [0, 1.8, 3.8, 5.2, hit, hit + 1.4, 11.6, 15.4, KNEE.total], steps


def charge(stage):
    """Out of a run: the Unit throws itself at its mark behind its left shoulder. The left foot drives it off the
    ground, the body goes in low and level with the left forearm drawn across the chest and the right arm back, the
    right foot comes down under it past the mark's place and the left after it, braking. The trunk is turned more
    than it is thrown down: the shoulder is what is ahead, and two bodies are kept apart by their trunks'
    fronts (thrown down as in the pounce, the head was ahead of the shoulder and the body was stopped thirty
    blocks from its mark). The ground it covers is
    its own (a blow ends the run: laid over the gait, as a punch is, the body had stopped within three blocks)."""
    hit = CHARGE.place(CHARGE.contact)
    a = CHARGE_LEAP
    tuck_l, tuck_r = (-3.5, 12.0, 6.0), (0, 5.0, -5.0)       # the left forearm across the chest, the right arm back
    keys = [
        (0.0, key()),
        # the drive off the left foot, the body going down and forward
        (1.4, key(adv=.14 * a, hip=(0, 1.6), high=-2.6, tuck=-6, lean=-8, yaw=-8, chest=-12, side=-3, ltoe=-22,
                  rfree=.8, rflex=38, rknee=82,
                  larm=(-1.5, 7.0, 4.0), lelbow=(.5, .6, 0), rarm=(0, 3.0, -3.0))),
        # in the air: the right knee leading, the left leg trailing, the shoulder going in
        (3.2, key(adv=.44 * a, hip=(.4, 2.6), high=-3.4, tuck=-8, lean=-12, yaw=-16, chest=-24, side=-6, nod=3,
                  rfree=1, rflex=62, rknee=108, lfree=1, lflex=-24, lknee=44,
                  larm=tuck_l, lelbow=(1.0, 1.0, 0), rarm=tuck_r)),
        # the shoulder into its mark
        (hit, key(adv=.70 * a, hip=(.6, 3.0), high=-4.0, tuck=-8, lean=-14, yaw=-22, chest=-32, side=-8, nod=4,
                  rfree=.7, rflex=52, rknee=98, lfree=1, lflex=-30, lknee=58,
                  larm=tuck_l, lelbow=(1.0, 1.0, 0), rarm=tuck_r)),
        # the right foot down under the body, the left coming through
        (6.4, key(adv=.86 * a, hip=(.5, 2.4), high=-4.4, tuck=-8, lean=-12, yaw=-16, chest=-22, side=-6, nod=3,
                  lfree=1, lflex=4, lknee=74,
                  larm=tuck_l, lelbow=(1.0, 1.0, 0), rarm=tuck_r)),
        # the left foot down ahead, braking
        (9.6, key(adv=a, hip=(.2, .4), high=-3.6, tuck=-12, lean=-14, yaw=-6, chest=-10, side=-4, nod=3, rtoe=-18,
                  larm=(-2.0, 7.0, 4.0), lelbow=(.5, .6, 0), rarm=(0, 3.0, -2.0))),
        (15.5, key(adv=a, hip=(.1, .2), high=-1.2, tuck=-4, lean=-4, yaw=-2, chest=-3,
                   larm=(-.5, 2.0, 1.5), rarm=(0, 1.0, -.5))),
        (float(CHARGE.total), key(adv=a)),
    ]
    steps = {'l': [(1.3, 9.2, (0, a), 0.0)], 'r': [(.3, 5.6, (0, .86 * a), 0.0), (11.0, 14.4, (0, a), 1.6)]}
    return keys, [0, 1.4, 3.2, hit, 6.4, 9.6, 15.5, CHARGE.total], steps


MOVES = {
    # name: (the clip, its row, its keys, the bone its mark is on, the mark in the rig's rest space or None)
    'pounce': ('r32_pounce_r64', POUNCE, pounce, 'hand_r', None, 'r'),
    # (the knee's mark is carried by the thigh, two blocks beyond the joint along it: the kneecap, which is what goes
    # in; the charge's is the outside of the left shoulder)
    'knee': ('r32_knee_r64', KNEE, knee, 'leg_r', 'knee_r', 'r'),
    'charge': ('r32_charge_r64', CHARGE, charge, 'arm_l', 'shoulder_l', 'l'),
}


def main():
    out = sys.argv[1]
    sheets = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != '-' else None
    which = sys.argv[3:] or list(MOVES)
    stage = M.Stage()
    m = stage.m_s
    print('the stand: shoulders %s %s; wrists %s %s; knees %s %s; arm %.1f long, leg %.1f' % (
        np.round(stage.pt(m, 'arm_l'), 1), np.round(stage.pt(m, 'arm_r'), 1), np.round(stage.pt(m, 'wrist_l'), 1), np.round(stage.pt(m, 'wrist_r'), 1),
        np.round(stage.pt(m, 'shin_l', stage.body.knee['l']), 1), np.round(stage.pt(m, 'shin_r', stage.body.knee['r']), 1),
        stage.body.limbs['arm_l'].reach(stage.body.limbs['arm_l'].lo)[0], stage.legs['l'].reach(stage.legs['l'].lo)[0]))
    clips = {}
    for name in which:
        clip, row, make, bone, point, leading = MOVES[name]
        keys, shown, steps = make(stage)
        at = (stage.body.knee['r'] + np.array([0, -.4, 0]) if point == 'knee_r'
              else stage.rig.pivot['arm_l'] + np.array([.4, 0, 0]) if point == 'shoulder_l' else point)
        clips[clip] = stage.clip(name, row, keys, bone, at, shown=shown, leading=leading, steps=steps,
                                 sheet=os.path.join(sheets, 'unarmed_%s.png' % name) if sheets else None)
    if out != '-':
        M.write(out, clips, 'Project SEELE original bare-handed blows (tools/finale/unarmed.py), MIT')


if __name__ == '__main__':
    main()
