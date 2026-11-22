"""R65 owner fixes (2026-11-22 playtest): heavy mechanical footfalls and a zoned air-raid alarm.

Seeded mathematical synthesis only, like tools/build_audio_r65.py (whose building blocks it reuses): no recording,
sample, film, TV or game audio is read.

  eva_foot_concrete / eva_foot_soil   The R65 takes read as water: their mid layer was a band-passed noise burst
                                      (280-2600 Hz, ~70 ms) with a spray band and hundreds of tiny tonal grains on
                                      top, which is how a splash is synthesised. Now a giant armoured foot: heel and
                                      forefoot strike 55-85 ms apart, a falling sub thump, low noise weight, a short
                                      steel-structure ring, a latch knock and a ground rumble. Nothing band-passed in
                                      the mids, no grains; concrete only adds a dry crack and a few broadband ticks.
  alarm (dry, looping)                The siren through a facility horn with almost no room: the listener's venue
                                      (hangar, cavern, shaft, room) is added at run time by VenueReverbR61.
  alarm_city (looping)                The same loop, phase-aligned, as heard in the open city: the nearest horn is
                                      already far (darkened) and the other horns all over Tokyo-3 arrive 0.4-5.3 s
                                      later and darker, over a long dark tail. AlarmSoundInstance crossfades the two
                                      by whether the listener sees the sky.

Usage:
  python tools/build_audio_r65b.py --out <review dir>             candidates + measurements, nothing installed
  python tools/build_audio_r65b.py --out <review dir> --install   also writes the shipped .ogg files and sounds.json
"""
from pathlib import Path
import argparse, json, shutil, sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ramiel_audio_r61 as r61  # noqa: E402
from build_ramiel_audio_r61 import RATE, times, osc, lowpass_gain, shaped_noise  # noqa: E402
from build_audio_r65 import hp, lp, env_exp, fade_tail, modal, room_ir, place, to_lufs, wail_pitch, siren_voice, LOOP  # noqa: E402

ASSET = r61.ASSET


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


# --------------------------------------------------------------- footsteps
def footstep_heavy(seed, soil):
    rng = np.random.default_rng(seed)
    dur = 1.2 if soil else 1.4
    t = times(dur)
    n = len(t)
    heel = 0.004
    fore = heel + rng.uniform(0.055, 0.085)
    x = np.zeros(n)
    for at, share in ((heel, 1.0), (fore, rng.uniform(0.55, 0.7))):
        u = np.maximum(t - at, 0)
        on = t >= at
        # The strike itself: a broadband click of a few milliseconds, darker on earth.
        click = lp(noise(n, seed + int(at * 1e4)), 2500 if soil else 6000, 2) * on * np.exp(-u / 0.003)
        # Weight: a sub thump that falls as the ground takes the load, saturated so its harmonics carry on small speakers.
        f_end = rng.uniform(46, 54) * (0.92 if soil else 1)
        f = f_end + rng.uniform(45, 60) * np.exp(-u / 0.035)
        thump = np.tanh(2.5 * np.sin(2 * np.pi * np.cumsum(f * on) / RATE)) / np.tanh(2.5) * on * np.exp(-u / (0.17 if soil else 0.14))
        # Low body of the blow: noise below 150-180 Hz, instant attack, short.
        body = lp(noise(n, seed + 7 + int(at * 1e4)), 220 if soil else 280, 2) * on * np.exp(-u / 0.07)
        x += share * (1.3 * click + 0.7 * thump + 2.6 * body)
    # The armoured leg and foot frame ring once, low and short (plate modes, 80-450 Hz).
    f0 = rng.uniform(78, 96)
    ratios = [1, 1.59, 2.14, 2.65, 3.16, 3.91, 4.6]
    ring = modal(t, heel + 0.001, [f0 * k for k in ratios], [0.2, 0.17, 0.14, 0.11, 0.09, 0.07, 0.05],
                 [1, 0.8, 0.6, 0.45, 0.32, 0.22, 0.15], seed + 61, detune=0.01)
    ring += 0.5 * modal(t, fore + 0.001, [f0 * k * 1.012 for k in ratios], [0.18, 0.15, 0.12, 0.1, 0.08, 0.06, 0.045],
                        [1, 0.8, 0.6, 0.45, 0.32, 0.22, 0.15], seed + 62, detune=0.01)
    # Ankle latch and actuators taking the load: a short knock, not a ring.
    k0 = rng.uniform(230, 270)
    latch = modal(t, fore + rng.uniform(0.025, 0.04), [k0, k0 * 1.71, k0 * 2.73, k0 * 4.1], [0.05, 0.035, 0.025, 0.018],
                  [1, 0.6, 0.35, 0.2], seed + 71, detune=0.02)
    # The ground carries it away: a slow low rumble.
    rumble = lp(noise(n, seed + 81), 90, 3) * env_exp(t, heel + 0.03, 0.38 if soil else 0.32, 0.08)
    x += (0.28 if soil else 0.4) * ring / (np.abs(ring).max() + 1e-9) + 0.22 * latch / (np.abs(latch).max() + 1e-9) \
        + 0.45 * rumble
    if soil:
        # Earth gives under it: a dull compression thud just after the heel.
        x += 1.2 * lp(noise(n, seed + 91), 520, 2) * env_exp(t, heel + 0.006, 0.05, 0.003)
    else:
        # Concrete: a dry crack (broadband, no ring) and a few broadband ticks of chips, sparse so they never trickle.
        x += 0.4 * hp(noise(n, seed + 91), 1200, 2) * (t >= heel) * np.exp(-np.maximum(t - heel, 0) / 0.006)
        for i in range(rng.integers(3, 6)):
            at = heel + 0.03 + rng.exponential(0.09)
            if at > dur - 0.1:
                continue
            j = int(at * RATE)
            tick = hp(noise(int(0.004 * RATE), seed + 101 + i), 900, 2) * np.exp(-np.arange(int(0.004 * RATE)) / (0.0012 * RATE))
            x[j:j + len(tick)] += 0.09 * np.exp(-(at - heel) / 0.2) * tick
    x = hp(x, 24, 2)
    # Open street: two facade slaps and a short tail, not a hall.
    ir = room_ir(0.8, seed + 121, 0.22, [(0.045, 0.3), (0.11, 0.18), (0.21, 0.1)], bright=4000, dark=600)
    x = place(x, ir, 0.12)
    return fade_tail(x, 0.25)


# --------------------------------------------------------------- alarm
def alarm_voice_loops(n):
    """Three periods of the R65 siren voice, its fundamental rounded to a whole number of cycles per loop (a multiple
    of 5, so the 6:5 rotor is whole too). Callers filter all three and keep the middle one: steady state at both ends."""
    t = np.arange(3 * n) / RATE
    f = wail_pitch(t)
    cycles = np.sum(f[:n]) / RATE
    f = f * (np.round(cycles / 5) * 5 / cycles)
    return siren_voice(f)


def circular(x, ir):
    n = len(x)
    return np.real(np.fft.ifft(np.fft.fft(x) * np.fft.fft(ir[:n], n)))


def alarm_dry(seed):
    n = int(LOOP * RATE)
    x = alarm_voice_loops(n)[n:2 * n]
    # Almost dry: a horn mounted on a wall, so a hint of its own surroundings. The venue comes from VenueReverbR61.
    ir = room_ir(LOOP, seed + 1, 0.12, [(0.018, 0.25), (0.041, 0.15)], bright=5000, dark=900)
    wet = circular(x, ir)
    wet *= np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(wet ** 2)) + 1e-12)
    return 0.9 * x + 0.1 * wet


# Horns across the city: (delay s, gain, lowpass Hz). Farther horns are later, quieter and darker (air absorbs highs).
CITY_HORNS = [(0.0, 0.55, 2800), (0.38, 0.52, 2400), (0.81, 0.46, 2100), (1.33, 0.40, 1800), (1.92, 0.33, 1500),
              (2.61, 0.26, 1300), (3.40, 0.20, 1100), (4.30, 0.14, 950), (5.30, 0.10, 800)]


def alarm_city(seed):
    n = int(LOOP * RATE)
    voice = alarm_voice_loops(n)
    horns = np.zeros(n)
    for delay, gain, cut in CITY_HORNS:
        # The voice is periodic in n, so rolling the filtered three-loop signal and keeping the middle is a
        # circular delay: the far horns' wails wrap into the start of the loop as they would in steady state.
        horns += gain * np.roll(lp(voice, cut, 2), int(delay * RATE))[n:2 * n]
    # The whole basin answers: a long dark diffuse tail over everything.
    t = np.arange(n) / RATE
    tail_ir = lp(noise(n, seed + 3), 1400, 2) * np.exp(-t / 2.4) * (t > 0.08)
    tail = circular(horns, tail_ir)
    tail *= np.sqrt(np.mean(horns ** 2)) / (np.sqrt(np.mean(tail ** 2)) + 1e-12)
    return 0.7 * horns + 0.42 * tail


# --------------------------------------------------------------- catalogue
# event -> (new file stem, count, maker, loudness target LUFS, files it replaces)
FAMILIES = {
    'eva_foot_concrete': ('eva_foot_concrete_r65m', 6, lambda i: footstep_heavy(8500 + 17 * i, False), -19.5,
                          ['eva_foot_concrete_r65_%d' % i for i in range(6)]),
    'eva_foot_soil': ('eva_foot_soil_r65m', 6, lambda i: footstep_heavy(8600 + 17 * i, True), -20.5,
                      ['eva_foot_soil_r65_%d' % i for i in range(6)]),
    # One dB under the R65 loop (-17.0); AlarmSoundInstance also goes from 0.45 to 0.30.
    'alarm': ('facility_alarm_dry_r65b', 1, lambda i: alarm_dry(9000), -18.0, ['facility_alarm_loop_r65']),
    'alarm_city': ('facility_alarm_city_r65b', 1, lambda i: alarm_city(9000), -18.0, []),
}
LOOPED = {'alarm', 'alarm_city'}


def build(out, install):
    out.mkdir(parents=True, exist_ok=True)
    sounds = json.loads((ASSET.parent / 'sounds.json').read_text('utf8'))
    report = {}
    for event, (stem, count, make, target, old) in FAMILIES.items():
        rows, names = [], []
        for i in range(count):
            name = stem if count == 1 else '%s_%d' % (stem, i)
            x = to_lufs(make(i), target)
            if event in LOOPED:
                step = abs(x[0] - x[-1]); typical = float(np.median(np.abs(np.diff(x))))
                assert step < 6 * typical + 1e-4, ('loop seam', event, step, typical)
            path = out / (name + '.ogg')
            r61.encode(x.astype(np.float32), path)
            m = r61.measure(r61.decode(path))
            rows.append(dict(file=name, **m))
            names.append(name)
            if install:
                shutil.copyfile(path, ASSET / (name + '.ogg'))
        report[event] = dict(new=rows, replaces=old)
        if install:
            # The two alarm takes share one entry shape (looping, not streamed); footsteps keep their range.
            entry = sounds.setdefault(event, {'subtitle': sounds['alarm']['subtitle'], 'sounds': [{'name': '', 'stream': False}]})
            first = entry['sounds'][0]
            template = {k: v for k, v in first.items() if k != 'name'} if isinstance(first, dict) else {}
            entry['sounds'] = [dict({'name': 'projectseele:' + nm}, **template) for nm in names]
        print(event, [(r['file'], r['lufs'], r['peak'], r['seconds']) for r in rows], flush=True)
    if install:
        (ASSET.parent / 'sounds.json').write_text(json.dumps(sounds, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (out / 'r65b_measure.json').write_text(json.dumps(report, indent=1), encoding='utf8')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--install', action='store_true')
    a = p.parse_args()
    build(a.out, a.install)


if __name__ == '__main__':
    main()
