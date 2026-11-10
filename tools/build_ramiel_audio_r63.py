"""Second round of Ramiel attack sounds, after the owner's audition on 2026-11-10.

Owner's notes: the charge must be terrifying and sit in a huge, empty, far-reaching space; the
fire is a sudden choir burst layered on the beam column (round-one D), long and big; the impact
explosion louder and wider; the drill one continuous sound for the whole attack. Everything is
synthesised from fixed seeds: no recordings, no official audio, no melody taken from anywhere.

  python tools/build_ramiel_audio_r63.py --out <candidates dir>
  python tools/build_ramiel_audio_r63.py --out <dir> --install beam_charge=v2_riser_hall,drill=v2_rotor_continuous
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ramiel_audio_r61 as r61  # noqa: E402
from build_ramiel_audio_r61 import RATE, times, osc, smooth, attack, release, shaped_noise, log_band, lowpass_gain  # noqa: E402

CEILING = 10 ** (-1 / 20)


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-12)


def lowpass(x, cut, order=2):
    return sosfilt(butter(order, cut, fs=RATE, btype='low', output='sos'), x)


# ------------------------------------------------------------------ space
def hall_ir(decay, seed, predelay):
    """Noise tail with -60 dB at `decay` s for the lows, shorter for mids and highs."""
    n = int((decay * 1.1 + predelay) * RATE)
    t = np.arange(n) / RATE
    noise = np.random.default_rng(seed).standard_normal(n)
    lo = sosfilt(butter(2, 280, fs=RATE, btype='low', output='sos'), noise)
    mid = sosfilt(butter(2, [280, 2200], fs=RATE, btype='band', output='sos'), noise)
    hi = sosfilt(butter(2, 2200, fs=RATE, btype='high', output='sos'), noise)
    late = np.maximum(t - predelay, 0)
    env = lambda seconds: np.exp(-6.91 * late / seconds)
    ir = (lo * env(decay) + .8 * mid * env(decay * .65) + .3 * hi * env(decay * .3)) * smooth(predelay, predelay + .15, t)
    return ir / np.sqrt(np.sum(ir ** 2))


def huge_space(x, decay, seed, wet=.6, predelay=.09, echoes=((.45, .3), (.9, .18), (1.35, .1))):
    """Dry signal in a very large empty space: long tail plus a few distant slap-backs."""
    ir = hall_ir(decay, seed, predelay)
    n = len(x) + len(ir)
    size = 1 << int(np.ceil(np.log2(n)))
    tail = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:n]
    tail *= rms(x) / rms(tail[:len(x)])
    dry = np.pad(x, (0, n - len(x)))
    far = lowpass(dry, 1500)
    echo = np.zeros(n)
    for delay, gain in echoes:
        k = int(delay * RATE)
        echo[k:] += gain * far[:n - k]
    out = (1 - wet) * dry + wet * tail + echo
    # Drop the part of the tail more than 60 dB under the peak, then fade.
    level = np.abs(out)
    above = np.nonzero(level > level.max() * 1e-3)[0]
    out = out[:above[-1] + 1] if len(above) else out
    return out * release(len(out), .6)


# ------------------------------------------------------------------ choir
VOWELS = {
    'a': [(800, 80, 1.0), (1150, 90, .5), (2900, 120, .25), (3900, 130, .12)],
    'o': [(450, 70, 1.0), (800, 80, .45), (2830, 100, .12), (3800, 120, .06)],
    'u': [(325, 50, 1.0), (700, 60, .25), (2530, 170, .06)],
}


def formant(freq, vowel):
    return sum(a / (1 + ((freq - fc) / bw) ** 2) for fc, bw, a in VOWELS[vowel]) + .02


def choir(t, notes, vowel, seed, voices=3, spread=.004):
    """Additive voices shaped by vowel formants; each note sung by a few slightly detuned voices."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    for f0 in notes:
        for _ in range(voices):
            detune = 1 + rng.uniform(-spread, spread)
            vibrato = 1 + .0055 * np.sin(2 * np.pi * rng.uniform(4.6, 5.8) * t + rng.uniform(0, 2 * np.pi)) * smooth(.15, .7, t)
            drift = 1 + .0015 * np.sin(2 * np.pi * rng.uniform(.2, .5) * t + rng.uniform(0, 2 * np.pi))
            inst = f0 * detune * vibrato * drift
            k = 1
            while f0 * k < 6500:
                out += formant(f0 * k, vowel) * osc(inst * k) / k ** .35
                k += 1
    return out / rms(out)


# ------------------------------------------------------------------ beam charge
CHARGE = r61.CHARGE


def dread_drone(t, p):
    beat = .5 * osc(36.7 + 0 * t) + .5 * osc(38.9 + 0 * t)
    tritone = .35 * osc(51.9 * (1 + .02 * p)) + .25 * osc(73.4 * (1 + .02 * p))
    return (beat + tritone) * (.25 + .75 * p ** 1.3)


def charge_riser_hall(seed):
    t = times(CHARGE)
    p = t / CHARGE
    dry = r61.charge_riser(seed) + .9 * dread_drone(t, p) * smooth(0, .3 / CHARGE, p) * release(len(t), .08)
    return huge_space(dry, 9.0, seed + 50, wet=.62, predelay=.1, echoes=((.55, .34), (1.1, .2), (1.65, .12)))


def charge_dread_cluster(seed):
    t = times(CHARGE)
    p = t / CHARGE
    glide = 2 ** (3 * p ** 1.6 / 12)
    cluster = sum(a * osc(f * glide) for f, a in [(110.0, .5), (116.5, .42), (123.5, .36), (130.8, .3)])
    whine = sum(a * osc(f * (1 + .04 * p)) for f, a in [(1730, .05), (2210, .035), (2980, .02)]) * smooth(.45, 1, p)
    swirl = shaped_noise(CHARGE, lambda f, u: log_band(f, 220 * (900 / 220) ** u, .6), seed)
    dry = (cluster * (.2 + .8 * p ** 1.5) + whine + .45 * swirl * p ** 1.8 + .8 * dread_drone(t, p)) * smooth(0, .35 / CHARGE, p) * release(len(t), .08)
    return huge_space(dry, 9.0, seed + 51, wet=.62, predelay=.1, echoes=((.55, .34), (1.1, .2), (1.65, .12)))


def charge_abyss(seed):
    t = times(CHARGE)
    p = t / CHARGE
    sub = osc(30 + 15 * p ** 1.4) * (.3 + .7 * p ** 1.2)
    hum = choir(t, [73.42, 110.0], 'u', seed, voices=2) * (.1 + .9 * p ** 2)
    shimmer = sum(a * osc(f * (1 + .01 * np.sin(2 * np.pi * .7 * t))) for f, a in [(1567, .04), (2349, .03), (3136, .02)]) * smooth(.3, 1, p)
    dry = (sub * .9 + hum * .45 + shimmer) * smooth(0, .4 / CHARGE, p) * release(len(t), .08)
    return huge_space(dry, 10.0, seed + 52, wet=.7, predelay=.18, echoes=((.7, .36), (1.4, .22), (2.1, .12)))


# ------------------------------------------------------------------ beam fire
HOLD = 2.8


def choir_envelope(t, accent, swell):
    rise = attack(t, swell)
    body = .68 + accent * np.exp(-t / .18)
    return rise * body * smooth(0, 1.0, HOLD - t)


def fire_choir(seed, notes, vowel, accent, swell, impact):
    t = times(HOLD)
    sung = choir(t, notes, vowel, seed) * choir_envelope(t, accent, swell)
    column = np.pad(r61.fire_column(seed + 7), (0, len(t)))[:len(t)]
    thump = osc(32 + 70 * np.exp(-t / .06)) * np.exp(-t / .35) * attack(t, .004)
    air = shaped_noise(HOLD, lambda f, u: log_band(f, 1100 - 600 * u, .9), seed + 8) * np.exp(-t / .4)
    dry = .55 * sung + .5 * column + impact * thump + .1 * air
    return huge_space(dry, 6.5, seed + 60, wet=.55, predelay=.07)


def fire_choir_hit(seed):
    return fire_choir(seed, [146.83, 220.0, 293.66, 349.23, 440.0, 659.25], 'a', .55, .025, .9)


def fire_choir_swell(seed):
    return fire_choir(seed, [146.83, 220.0, 293.66, 440.0, 587.33, 880.0], 'a', .25, .16, .7)


def fire_dark_choir(seed):
    return fire_choir(seed, [73.42, 110.0, 146.83, 174.61, 220.0], 'o', .45, .03, 1.0)


# ------------------------------------------------------------------ impact
def rumble(seconds, seed):
    t = times(seconds)
    low = shaped_noise(seconds, lambda f, u: lowpass_gain(f, 160 - 90 * u, 3) * (1 - np.exp(-(f / 25) ** 2)), seed)
    return low * attack(t, .08) * np.exp(-t / 1.6)


def blast_vast(base, seed):
    body = base(seed)
    roll = rumble(5.0, seed + 70)
    mix = np.pad(body, (0, len(roll) - len(body))) + .55 * roll
    return huge_space(mix, 7.0, seed + 71, wet=.55, predelay=.06, echoes=((.6, .3), (1.2, .18)))


def blast_dark_vast(seed):
    return blast_vast(r61.blast_dark, seed)


def blast_glass_vast(seed):
    return blast_vast(r61.blast_glass, seed)


# ------------------------------------------------------------------ drill, played once for the whole attack
DRILL = 4.0


def continuous(tone, grind):
    n = len(tone)
    t = np.arange(n) / RATE
    return (tone + grind) * smooth(0, .15, t) * smooth(0, .35, DRILL - t)


def drill_rotor_continuous(seed):
    t = times(DRILL)
    rise = 1 + .08 * t / DRILL
    tone = sum(a * osc(f * rise) for f, a in [(55, .68), (165, .42), (275, .22), (385, .12), (605, .05)])
    rotor = 1 - .12 * (.5 + .5 * np.cos(2 * np.pi * 7 * t))
    grind = shaped_noise(DRILL, lambda f, u: log_band(f, 430 + 120 * u, .95), seed) * (1 - .15 * (.5 + .5 * np.cos(2 * np.pi * 7 * t + 1.1)))
    return continuous(tone * rotor * .75, grind * .26)


def drill_churn_continuous(seed):
    t = times(DRILL)
    tone = sum(a * osc(f * (1 + .05 * t / DRILL)) for f, a in [(70, .55), (183, .25)])
    sway = 1 - .2 * (.5 + .5 * np.cos(2 * np.pi * 3 * t))
    low = shaped_noise(DRILL, lambda f, u: lowpass_gain(f, 420 + 160 * u, 3) * (1 - np.exp(-(f / 60) ** 2)), seed) * sway
    return continuous(tone * .55, low * .45)


def drill_bore_continuous(seed):
    t = times(DRILL)
    tone = sum(a * osc(f * (1 + .06 * t / DRILL)) for f, a in [(78, .62), (196, .40), (311, .30), (523, .16), (871, .05)])
    rotor = 1 - .14 * (.5 + .5 * np.cos(2 * np.pi * 5 * t))
    grind = shaped_noise(DRILL, lambda f, u: log_band(f, 720, .7), seed) * (1 - .18 * (.5 + .5 * np.cos(2 * np.pi * 5 * t + .8)))
    return continuous(tone * rotor * .72, grind * .22)


EVENTS = {
    'beam_charge': dict(target=-13.0, seed=7100, variants={
        'v2_riser_hall': (charge_riser_hall, '以 B 为底，加不协和的超低频拍音和三全音，放进衰减 9 秒、带远处回声的巨大空间。'),
        'v2_dread_cluster': (charge_dread_cluster, '低音区四个半音挤在一起慢慢往上滑，后段加入金属尖啸，同样的巨大空间。'),
        'v2_abyss_swell': (charge_abyss, '从深渊升起的超低频，叠低沉的哼唱和远处的高频微光，空间最空、回声最远。'),
    }),
    'beam_fire': dict(target=-11.0, seed=7200, variants={
        'v2_choir_hit': (fire_choir_hit, '合唱和弦瞬间爆发再持续，叠第一轮 D 的音柱和低频冲击，尾巴很长。'),
        'v2_choir_swell': (fire_choir_swell, '同样的合唱，起音稍缓、更明亮，叠 D 的音柱。'),
        'v2_dark_choir': (fire_dark_choir, '低一个八度的男声合唱，更阴沉，叠 D 的音柱和更重的冲击。'),
    }),
    'cross_explosion': dict(target=-10.5, seed=7400, variants={
        'v2_dark_vast': (blast_dark_vast, '现在用的暗爆炸，加 5 秒低频滚动和大空间回声，更响、更开阔。'),
        'v2_glass_vast': (blast_glass_vast, '带玻璃碎裂声的爆炸，同样加长滚动和大空间。'),
    }),
    'drill': dict(target=-17.0, seed=7300, variants={
        'v2_rotor_continuous': (drill_rotor_continuous, '一整段 4 秒的转子研磨声，起伏更平滑，音高随钻深微微上升。'),
        'v2_churn_continuous': (drill_churn_continuous, '一整段 4 秒的低沉翻搅声，音高感最弱。'),
        'v2_bore_continuous': (drill_bore_continuous, '一整段 4 秒的晶体钻孔声。'),
    }),
}


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for event, spec in EVENTS.items():
        for name, (make, note) in spec['variants'].items():
            x = make(spec['seed'])
            m = r61.measure(x)
            x = x * 10 ** ((spec['target'] - m['momentary_max']) / 20)
            x = r61.limit_peaks(x, CEILING)
            m = r61.measure(x)
            path = out / f'{event}__{name}.ogg'
            r61.encode(x.astype(np.float32), path)
            report[f'{event}__{name}'] = dict(note=note, seconds=round(len(x) / RATE, 2), lufs=m['lufs'],
                                              momentary_max=m['momentary_max'], true_peak_db=m['true_peak_db'])
            print(f'{event}__{name}: {len(x) / RATE:.1f}s Mmax {m["momentary_max"]} TP {m["true_peak_db"]}')
    (out / 'measurements_v2.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def install(out, choices):
    for pair in choices.split(','):
        event, name = pair.split('=')
        shutil.copyfile(out / f'{event}__{name}.ogg', r61.ASSET / f'{event}.ogg')
        print('installed', event, name)


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--install', default='')
    args = a.parse_args()
    if args.install:
        install(args.out, args.install)
    else:
        build(args.out)


if __name__ == '__main__':
    main()
