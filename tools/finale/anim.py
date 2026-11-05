"""Keyframed channels for hand-authored cinematics.

A Channel holds keys (time, value) of any dimension and interpolates with
monotone cubic Hermite segments (no overshoot unless asked).  Per-key tangent
modes shape timing the way an animator would:
  'auto'  - monotone Catmull-Rom (default)
  'flat'  - zero slope (ease in / ease out, holds)
  'fast'  - arrive/leave at 1.6x the segment's average speed (whip into a hit)
  'linear'- slope of the adjoining segment
A key may also be 'step' (value jumps at the next key).
"""
import math

import numpy as np


class Channel:
    def __init__(self, name, default):
        self.name = name
        self.default = np.atleast_1d(np.asarray(default, float))
        self.keys = []  # (t, value, tin, tout, step)

    def key(self, t, value, tin='auto', tout='auto', step=False, ease=None):
        if ease is not None:
            tin = tout = ease
        v = np.atleast_1d(np.asarray(value, float))
        self.keys = [k for k in self.keys if abs(k[0] - t) > 1e-9]
        self.keys.append((float(t), v, tin, tout, step))
        self.keys.sort(key=lambda k: k[0])
        self._tangents = None
        return self

    def hold(self, t0, t1, value, ease='flat'):
        self.key(t0, value, ease=ease)
        self.key(t1, value, ease=ease)
        return self

    def value_at_key(self, t):
        return self(t)

    def _slopes(self):
        if self._tangents is not None:
            return self._tangents
        ks = self.keys
        n = len(ks)
        ins, outs = [], []
        for i in range(n):
            t, v = ks[i][0], ks[i][1]
            prev_s = (v - ks[i - 1][1]) / (t - ks[i - 1][0]) if i > 0 else None
            next_s = (ks[i + 1][1] - v) / (ks[i + 1][0] - t) if i < n - 1 else None
            if prev_s is None and next_s is None:
                auto = np.zeros_like(v)
            elif prev_s is None:
                auto = np.zeros_like(v)
            elif next_s is None:
                auto = np.zeros_like(v)
            else:
                auto = (prev_s + next_s) / 2
                # monotone: extrema get zero slope, and limit to 3x either side
                same = np.sign(prev_s) == np.sign(next_s)
                auto = np.where(same, auto, 0.0)
                lim = 3 * np.minimum(np.abs(prev_s), np.abs(next_s))
                auto = np.clip(auto, -lim, lim)

            def mode(m, side_slope):
                if m == 'flat':
                    return np.zeros_like(v)
                if m == 'linear':
                    return side_slope if side_slope is not None else np.zeros_like(v)
                if m == 'fast':
                    return 1.6 * side_slope if side_slope is not None else np.zeros_like(v)
                return auto
            ins.append(mode(ks[i][2], prev_s))
            outs.append(mode(ks[i][3], next_s))
        self._tangents = (ins, outs)
        return self._tangents

    def __call__(self, t):
        ks = self.keys
        if not ks:
            return self.default.copy()
        if t <= ks[0][0]:
            return ks[0][1].copy()
        if t >= ks[-1][0]:
            return ks[-1][1].copy()
        i = 0
        lo, hi = 0, len(ks) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ks[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        i = lo
        t0, v0 = ks[i][0], ks[i][1]
        t1, v1 = ks[i + 1][0], ks[i + 1][1]
        if ks[i][4]:
            return v0.copy()
        ins, outs = self._slopes()
        h = t1 - t0
        s = (t - t0) / h
        s2, s3 = s * s, s * s * s
        h00 = 2 * s3 - 3 * s2 + 1
        h10 = s3 - 2 * s2 + s
        h01 = -2 * s3 + 3 * s2
        h11 = s3 - s2
        return h00 * v0 + h10 * h * outs[i] + h01 * v1 + h11 * h * ins[i + 1]


class Rig:
    """A named bag of channels."""

    def __init__(self):
        self.channels = {}

    def ch(self, name, default=0.0):
        if name not in self.channels:
            self.channels[name] = Channel(name, default)
        return self.channels[name]

    def sample(self, t):
        return {k: c(t) for k, c in self.channels.items()}


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def step_arc(t, t0, t1, a, b, lift, heel=0.0):
    """Foot path for one step: eased travel with a sine lift.  Returns (pos, u)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if t <= t0:
        return a.copy(), 0.0
    if t >= t1:
        return b.copy(), 1.0
    u = (t - t0) / (t1 - t0)
    e = smooth(u)
    p = a + (b - a) * e
    p[1] += lift * math.sin(math.pi * min(1.0, u * 1.08))
    return p, u
