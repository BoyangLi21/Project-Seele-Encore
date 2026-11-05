"""Cinematic camera for the first battle: keyed position/target/fov with hard cuts."""
import numpy as np

import anim

# (time, position, target, fov, cut_before)
SHOTS = [
    # awakening: low, in front of Unit-01's left, looking up at the scream
    (0.0, (-52, 20, 50), (0, 36, 4), 56, False),
    (1.55, (-46, 22, 44), (0, 37, 8), 54, False),
    # the field: wide profile with the field and the angel in frame
    (1.6, (-100, 30, 14), (0, 38, 24), 46, True),
    (3.3, (-96, 31, 18), (0, 38, 24), 44, False),
    # behind Unit-01's right shoulder as it rips the field open
    (3.35, (-46, 50, -26), (0, 40, 24), 50, True),
    (5.0, (-50, 50, -28), (0, 40, 26), 50, False),
    # tracking profile on the charge
    (5.05, (-92, 30, 6), (0, 34, 18), 46, True),
    (6.5, (-90, 30, 26), (0, 38, 32), 46, False),
    # the catch, the wrench and the kick: three-quarter from the angel's side
    (7.3, (-88, 30, 74), (0, 38, 36), 50, True),
    (9.3, (-90, 30, 72), (0, 34, 40), 50, False),
    # wide on the flight and the leap
    (9.35, (-118, 34, 30), (0, 26, 46), 46, True),
    (11.7, (-112, 34, 52), (0, 26, 64), 46, False),
    # ground and pound: from beyond the angel's head, looking up at the raised fists
    (11.75, (-58, 22, 104), (0, 30, 70), 54, True),
    (13.9, (-54, 22, 102), (0, 28, 71), 54, False),
    # profile for the alternating fists
    (13.95, (-78, 24, 72), (0, 26, 72), 46, True),
    (15.5, (-76, 25, 72), (0, 27, 72), 46, False),
    # the final blow from in front again
    (15.55, (-48, 16, 106), (0, 30, 71), 54, True),
    (16.4, (-50, 16, 105), (0, 25, 72), 52, False),
    # the embrace, close enough to read the arms locking
    (16.45, (-64, 28, 50), (0, 24, 70), 48, True),
    (18.55, (-60, 30, 52), (0, 25, 70), 46, False),
    # the blast and the rise
    (18.6, (-82, 40, 46), (0, 28, 70), 46, True),
    (21.5, (-74, 38, 50), (0, 32, 72), 46, False),
    (23.0, (-72, 38, 52), (0, 34, 72), 46, False),
]


class Film:
    def __init__(self):
        self.pos = anim.Channel('cam_pos', (0, 0, 0))
        self.target = anim.Channel('cam_target', (0, 0, 0))
        self.fov = anim.Channel('cam_fov', 50)
        self.cuts = []
        last = None
        for t, p, g, f, cut in SHOTS:
            if cut and last is not None:
                # hold the outgoing shot to the frame before the cut
                self.cuts.append(t)
            self.pos.key(t, p, ease='flat' if cut else 'auto')
            self.target.key(t, g, ease='flat' if cut else 'auto')
            self.fov.key(t, f, ease='flat' if cut else 'auto')
            last = t

    def sample(self, t):
        return self.pos(t), self.target(t), float(self.fov(t)[0])

    def cut_frames(self, fps):
        return sorted({int(round(c * fps)) for c in self.cuts})
