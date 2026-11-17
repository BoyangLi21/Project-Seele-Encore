"""The positron cannon's sight (R64): five short sounds heard in the pilot's own ears.

  cannon_visor       the sight swinging down over the pilot's face: a small servo and its latch
  cannon_sight_tick  one tick of the marks closing (the game repeats it faster and higher as they close)
  cannon_sight_lock  the marks have met: a steady two-note tone
  cannon_vent        after a shot: the barrel's coolant let off as steam
  cannon_fuse        the spent fuse thrown out, or (played higher) the new one driven home

Everything is synthesised here from fixed seeds: sines, filtered noise and their envelopes. No recording, no
sample and nothing taken from the series' sound; the tones are plain intervals chosen here.

  python tools/build_cannon_sight_audio_r64.py            writes the five .ogg files into the mod's sounds
  python tools/build_cannon_sight_audio_r64.py --out DIR  writes them (and measurements.json) somewhere else
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ramiel_audio_r61 as r61  # noqa: E402
from build_ramiel_audio_r61 import RATE, times, osc, smooth, release  # noqa: E402

CEILING = 10 ** (-3 / 20)


def band(x, lo, hi, order=2):
    if lo <= 0:
        return sosfilt(butter(order, hi, fs=RATE, btype='low', output='sos'), x)
    if hi >= RATE / 2:
        return sosfilt(butter(order, lo, fs=RATE, btype='high', output='sos'), x)
    return sosfilt(butter(order, [lo, hi], fs=RATE, btype='band', output='sos'), x)


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def struck(t, freq, tau, at=0.0):
    """A damped sine that begins at `at` seconds."""
    late = np.maximum(t - at, 0)
    return np.where(t >= at, np.sin(2 * np.pi * freq * late) * np.exp(-late / tau), 0.0)


def visor(seed):
    t = times(.78)
    n = len(t)
    # The servo: a small motor that runs up, holds and runs down over .6 s, with the whine of its gears.
    run = smooth(0, .09, t) * (1 - smooth(.50, .62, t))
    speed = 150 + 190 * smooth(0, .16, t) - 120 * smooth(.46, .62, t)
    wobble = 1 + .012 * np.sin(2 * np.pi * 23 * t)
    motor = .50 * osc(speed * wobble) + .22 * osc(2 * speed * wobble) + .12 * osc(3.02 * speed * wobble)
    gears = band(noise(n, seed), 1400, 5200) * (.6 + .4 * np.sin(2 * np.pi * speed * 6 * t / 150))
    whirr = (.55 * motor + .30 * gears) * run
    # The latch at .63 s: a short low knock and the click of the catch.
    knock = .6 * struck(t, 128, .030, .63) + .35 * struck(t, 310, .012, .63)
    click = band(noise(n, seed + 1), 2200, 9000) * np.where(t >= .63, np.exp(-np.maximum(t - .63, 0) / .006), 0) * .5
    return (whirr + knock + click) * release(n, .05)


def sight_tick(seed):
    t = times(.060)
    n = len(t)
    body = (np.sin(2 * np.pi * 1320 * t) + .35 * np.sin(2 * np.pi * 2640 * t)) * np.exp(-t / .011)
    edge = band(noise(n, seed), 3000, 9000) * np.exp(-t / .0015) * .25
    return (body * smooth(0, .0012, t) + edge) * release(n, .012)


def sight_lock(seed):
    t = times(.56)
    n = len(t)
    # A fourth, a little reedy, held steady with a slow shimmer: the two notes that had been one tick apart.
    shimmer = 1 + .10 * np.sin(2 * np.pi * 17 * t)
    tone = np.sin(2 * np.pi * 1568 * t) + .8 * np.sin(2 * np.pi * 2093 * t) + .18 * np.sin(2 * np.pi * 3136 * t) + .12 * np.sin(2 * np.pi * 4186 * t)
    env = smooth(0, .006, t) * (1 - smooth(.44, .56, t))
    air = band(noise(n, seed), 5000, 11000) * .03
    return (tone * shimmer + air) * env


def vent(seed):
    t = times(2.3)
    n = len(t)
    # The valve opens with a low cough, then the steam: bright noise that falls in pitch and loudness as the pressure goes.
    cough = band(noise(n, seed), 140, 520) * np.exp(-t / .055) * .7
    pressure = smooth(0, .035, t) * (.8 * np.exp(-t / 1.0) + .2 * np.exp(-t / .25))
    flutter = 1 + .16 * np.sin(2 * np.pi * (31 - 9 * t) * t) * np.exp(-t / .9)
    bright = band(noise(n, seed + 1), 2600, 10500)
    low = band(noise(n, seed + 2), 900, 3200)
    steam = (bright * (.9 * np.exp(-t / .5) + .25) + low * .55 * smooth(.1, .9, t)) * pressure * flutter
    drip = sum(struck(t, f, .012, at) * g for f, at, g in ((2380, 1.18, .05), (1990, 1.52, .04), (2710, 1.83, .03)))
    out = cough + steam + drip
    # The first instant is far louder than the hiss that follows; pressed together so the hiss is heard under it.
    out = np.tanh(3.2 * out / np.max(np.abs(out)))
    return out * release(n, .5)


def fuse(seed):
    t = times(.46)
    n = len(t)
    # Two blows .09 s apart: the breech block, then the fuse itself against its stop, each with a short metal ring.
    out = np.zeros(n)
    for at, gain, sharp in ((0.0, 1.0, 0), (.09, .62, 1)):
        late = np.maximum(t - at, 0)
        gate = (t >= at).astype(float)
        thud = (struck(t, 92, .050, at) + .6 * struck(t, 204, .028, at)) * gain
        ring = sum(struck(t, f * (1 + .04 * sharp), tau, at) * g for f, tau, g in ((1340, .045, .46), (2210, .032, .34), (3470, .020, .22), (5120, .012, .12))) * gain
        hit = band(noise(n, seed + sharp), 700, 6500) * gate * np.exp(-late / .008) * .85 * gain
        out += thud + ring + hit
    return out * release(n, .08)


SOUNDS = {
    'cannon_visor': (visor, 6401),
    'cannon_sight_tick': (sight_tick, 6402),
    'cannon_sight_lock': (sight_lock, 6403),
    'cannon_vent': (vent, 6404),
    'cannon_fuse': (fuse, 6405),
}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--out', type=Path, default=r61.ASSET)
    args = a.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, (make, seed) in SOUNDS.items():
        x = make(seed)
        x = x / np.max(np.abs(x)) * CEILING
        x = r61.limit_peaks(x, CEILING)
        r61.encode(x.astype(np.float32), args.out / f'{name}.ogg')
        back = r61.decode(args.out / f'{name}.ogg')
        report[name] = dict(seconds=round(len(x) / RATE, 3), peak_db=round(float(20 * np.log10(np.max(np.abs(back)) + 1e-12)), 2),
                            rms_db=round(float(20 * np.log10(np.sqrt(np.mean(back ** 2)) + 1e-12)), 2), seed=seed)
        print(name, report[name])
    if args.out != r61.ASSET:
        (args.out / 'measurements.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
