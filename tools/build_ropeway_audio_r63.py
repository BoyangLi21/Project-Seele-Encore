"""Cabin sound for the Hakone ropeway cable cars (MTR plays nothing while you ride one).

A seamless 16 s loop: motor hum, cable rumble, wind past the windows, and once a loop the
clatter of the cabin passing a tower's roller battery. Synthesised from fixed seeds with the
round-one Ramiel primitives; no recordings.

  python tools/build_ropeway_audio_r63.py            # writes src/main/resources/.../sounds/ropeway_ride.ogg
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ramiel_audio_r61 as r61  # noqa: E402
from build_ramiel_audio_r61 import RATE, times, osc, shaped_noise, log_band, lowpass_gain  # noqa: E402

LOOP = 16.0
FADE = 2.0
TARGET = -21.0


def body(seconds, seed):
    t = times(seconds)
    wow = 1 + .004 * np.sin(2 * np.pi * .3 * t)
    hum = sum(a * osc(f * wow) for f, a in [(98, .55), (196, .3), (294, .14), (392, .07), (1180, .02)])
    rumble = shaped_noise(seconds, lambda f, u: lowpass_gain(f, 260, 3) * (1 - np.exp(-(f / 35) ** 2)), seed)
    swell = 1 + .25 * np.sin(2 * np.pi * .11 * t + 1.3)
    wind = shaped_noise(seconds, lambda f, u: log_band(f, 1100, .9), seed + 1) * (.6 + .4 * np.sin(2 * np.pi * .07 * t + .4) ** 2)
    return .55 * hum + .5 * rumble * swell + .16 * wind


def roller_clatter(seconds, start, seed):
    """Three wheel thumps and a short rattle as the cabin runs over a tower's rollers."""
    t = times(seconds)
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    for k, offset in enumerate([0, .16, .31, .47]):
        at = start + offset + rng.uniform(-.01, .01)
        local = np.maximum(t - at, 0)
        gate = t >= at
        thump = osc(70 + 50 * np.exp(-local / .02)) * np.exp(-local / .07) * gate
        click = shaped_noise(seconds, lambda f, u: log_band(f, 2400, .5), seed + 10 + k) * np.exp(-local / .015) * gate
        out += (.9 - .12 * k) * thump + .25 * click
    rattle = shaped_noise(seconds, lambda f, u: log_band(f, 650, .6), seed + 20) * np.exp(-np.maximum(t - start - .55, 0) / .4) * (t >= start + .5)
    return out + .2 * rattle


def build():
    total = LOOP + FADE
    x = body(total, 9100) + .8 * roller_clatter(total, 8.0, 9150)
    n, k = int(LOOP * RATE), int(FADE * RATE)
    ramp = np.sin((np.arange(k) + .5) / k * np.pi / 2)
    loop = x[:n].copy()
    loop[:k] = loop[:k] * ramp + x[n:n + k] * np.cos((np.arange(k) + .5) / k * np.pi / 2)
    m = r61.measure(loop)
    loop *= 10 ** ((TARGET - m['momentary_max']) / 20)
    loop = r61.limit_peaks(loop, 10 ** (-3 / 20))
    out = r61.ASSET / 'ropeway_ride.ogg'
    r61.encode(loop.astype(np.float32), out)
    m = r61.measure(loop)
    print(out.name, f'{len(loop) / RATE:.1f}s', 'Mmax', m['momentary_max'], 'TP', m['true_peak_db'])


if __name__ == '__main__':
    build()
