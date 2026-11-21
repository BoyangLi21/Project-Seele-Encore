"""R65 original movement, AT Field and alarm sounds.

Every waveform is seeded mathematical synthesis (additive and modal tones, shaped noise, granular clicks and a
synthetic room). No recording, sample, film, TV or game audio is read, so nothing here derives from official
Evangelion audio or from the CC0 recordings behind the R36/R47 files it replaces.

What each family fixes (measured on the shipped R47/R36 files, see docs/ASSETS.md):
  eva_foot_concrete / eva_foot_soil  six files were three distinct takes; a flat 0.5 s body, then a hard cut to
                                     silence at 1.07 s; nearly nothing above 250 Hz, so no ground texture.
  eva_joint_load                     three takes 98 % alike.
  eva_at_pressure                    a punching-bag thud borrowed from body contact: no field character at all.
  eva_at_tear                        one take.
  alarm (looping)                    a 2.6 s horn blast decaying to -55 dB, looped: a hard jump back to full level
                                     every 2.6 s. Now a seamless 8 s wail loop (phase-continuous, circular room).
  facility_siren (one-shot)          the same blast; now one wail of the loop's voice with a natural tail.

Usage:
  python tools/build_audio_r65.py --out <review dir>             candidates + measurements, nothing installed
  python tools/build_audio_r65.py --out <review dir> --install   also writes the shipped .ogg files

Loudness targets keep each family near the file it replaces, so the volumes in code stay right; the AT Field
cues are raised on purpose (the old thud sat at -26 LUFS under every other combat sound).
"""
from pathlib import Path
import argparse, json, shutil, sys
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ramiel_audio_r61 as r61  # noqa: E402
from build_ramiel_audio_r61 import RATE, times, osc, shaped_noise, log_band, lowpass_gain, band_noise  # noqa: E402

ASSET = r61.ASSET


# --------------------------------------------------------------- building blocks
def hp(x, f, order=2):
    return sosfilt(butter(order, f, fs=RATE, btype='high', output='sos'), x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, fs=RATE, btype='low', output='sos'), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], fs=RATE, btype='bandpass', output='sos'), x)


def env_exp(t, start, tau, rise=0.002):
    """Zero before start, a short rise, then exponential decay."""
    u = t - start
    e = np.where(u < 0, 0.0, (1 - np.exp(-np.maximum(u, 0) / rise)) * np.exp(-np.maximum(u, 0) / tau))
    return e


def fade_tail(x, seconds=0.12):
    """Ends every one-shot on true silence without cutting a ringing tail (the R47 steps stopped dead)."""
    k = min(len(x), int(seconds * RATE))
    x = x.copy()
    x[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k)
    k = min(len(x), 48)
    x[:k] *= np.linspace(0, 1, k)
    return x


def modal(t, start, freqs, taus, amps, seed, detune=0.0):
    """A struck plate or shell: decaying partials, each with a little random phase and detune."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    u = np.maximum(t - start, 0)
    on = t >= start
    for f, tau, a in zip(freqs, taus, amps):
        f = f * (1 + detune * rng.uniform(-1, 1))
        out += on * a * np.sin(2 * np.pi * f * u + rng.uniform(0, 2 * np.pi)) * np.exp(-u / tau)
    return out


def grains(t, seed, count, mean_time, lo, hi, length=(0.002, 0.007), start=0.0, decay_amp=0.35, stop=None):
    """Granular crackle: short band-passed bursts whose density and size fall off over time (crushed
    concrete, gravel, falling debris)."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    stop = stop if stop is not None else t[-1] - 0.05
    for _ in range(count):
        at = start + rng.exponential(mean_time)
        if at >= stop:
            continue
        n = int(rng.uniform(*length) * RATE)
        i = int(at * RATE)
        if i + n >= len(t):
            continue
        centre = np.exp(rng.uniform(np.log(lo), np.log(hi)))
        burst = rng.standard_normal(n) * np.exp(-np.arange(n) / (n / 3))
        w = max(0.25, min(0.9, 600 / centre))
        burst = bp(np.pad(burst, (0, n)), centre * (1 - w / 2), min(centre * (1 + w / 2), RATE / 2 - 100))[:2 * n]
        amp = np.exp(-(at - start) / decay_amp) * rng.uniform(0.3, 1.0)
        out[i:i + 2 * n] += amp * burst[:len(out) - i] if i + 2 * n > len(out) else amp * burst
    return out


def room_ir(seconds, seed, decay, early, bright=6000.0, dark=900.0):
    """A synthetic space: discrete early reflections (facades, walls) then a darkening diffuse tail."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    ir = np.zeros(n)
    ir[0] = 1.0
    for delay, gain in early:
        i = int(delay * RATE)
        if i < n:
            ir[i] += gain * rng.choice([-1, 1])
    tail = rng.standard_normal(n) * np.exp(-t / decay) * (t > 0.02)
    # Higher bands die first: split the tail in two and give the top a faster decay.
    tail = lp(tail, bright, 1) - hp(lp(tail, bright, 1), dark, 1) * (1 - np.exp(-t / (decay * 0.35)))
    ir += 0.012 * tail
    return ir


def place(x, ir, wet):
    y = fftconvolve(x, ir)[:len(x)]
    y = y / (np.sqrt(np.mean(y ** 2)) + 1e-12) * np.sqrt(np.mean(x ** 2))
    return x * (1 - wet) + y * wet


def soft_limit(x, ceiling=0.89):
    """Peaks above 70 % of the ceiling bend smoothly into it (tanh), the rest is untouched."""
    knee = 0.7 * ceiling
    a = np.abs(x)
    over = a > knee
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (ceiling - knee) * np.tanh((a[over] - knee) / (ceiling - knee)))
    return y


def to_lufs(x, target, ceiling=0.89):
    """Level to a loudness target, then bend peaks under the ceiling; a second pass keeps the target after it."""
    for _ in range(3):
        x = x * 10 ** ((target - r61.lufs(x)) / 20)
        x = soft_limit(x, ceiling)
    return x


# --------------------------------------------------------------- footsteps
def footstep(seed, soil):
    rng = np.random.default_rng(seed)
    dur = 1.35 if soil else 1.65
    t = times(dur)
    t0 = 0.004
    # Weight: a pitched sub thump that drops as the ground takes the load, saturated a little so its
    # harmonics carry on small speakers that cannot play 30 Hz.
    # The weight sits where speakers can play it (40-160 Hz); the sub only underpins it.
    f_end = rng.uniform(36, 44) * (0.9 if soil else 1)
    f_start = f_end + rng.uniform(40, 55)
    f = f_end + (f_start - f_end) * np.exp(-np.maximum(t - t0, 0) / 0.05)
    sub = np.tanh(2.2 * osc(f)) / np.tanh(2.2) * env_exp(t, t0, rng.uniform(0.2, 0.28) * (0.85 if soil else 1), 0.004)
    body = shaped_noise(dur, lambda fr, u: lowpass_gain(fr, 260 if soil else 320, 3) * (1 - lowpass_gain(fr, 45, 2)), seed + 11)         * env_exp(t, t0, 0.13, 0.002)
    # The mass of the foot and the slab under it: a damped low resonance.
    fm = rng.uniform(70, 96) * (0.88 if soil else 1)
    mass = modal(t, t0, [fm, fm * 1.87, fm * 2.9], [0.17, 0.09, 0.05], [1, 0.45, 0.2], seed + 13, detune=0.02)
    if soil:
        # Earth gives: a duller mid thump, gravel grains, and a little sand sliding back into the print.
        mid = bp(band_noise(dur, 120, 2400, seed + 21), 150, 1300) * env_exp(t, t0 + 0.003, rng.uniform(0.11, 0.16), 0.004)
        crunch = grains(t, seed + 31, rng.integers(220, 320), 0.12, 500, 3200, start=t0, decay_amp=0.25)
        debris = grains(t, seed + 41, rng.integers(60, 110), 0.30, 900, 5000, length=(0.001, 0.003), start=t0 + 0.08, decay_amp=0.5)
        slide = bp(band_noise(dur, 1500, 9000, seed + 51), 2000, 7000) * env_exp(t, t0 + 0.12, 0.28, 0.08)
        clank_level, crunch_level, mid_level = 0.06, 0.30, 0.42
        hiss_level = 0.035
    else:
        # Concrete cracks under it: a bright crush, a granular crackle that thins out, then pebbles settling.
        mid = bp(band_noise(dur, 250, 4000, seed + 21), 280, 2600) * env_exp(t, t0 + 0.002, rng.uniform(0.06, 0.09), 0.002)
        crunch = grains(t, seed + 31, rng.integers(320, 460), 0.09, 900, 6500, start=t0, decay_amp=0.18)
        debris = grains(t, seed + 41, rng.integers(70, 130), 0.45, 1500, 7000, length=(0.001, 0.003), start=t0 + 0.12, decay_amp=0.7)
        slide = bp(band_noise(dur, 1500, 9000, seed + 51), 2500, 8000) * env_exp(t, t0 + 0.05, 0.16, 0.03)
        clank_level, crunch_level, mid_level = 0.11, 0.42, 0.5
        hiss_level = 0.03
    # The armoured sole rings briefly as it strikes: a free bar's partials (1 : 2.76 : 5.40 : 8.93), detuned.
    f0 = rng.uniform(150, 205)
    clank = modal(t, t0 + 0.001, [f0, f0 * 2.76, f0 * 5.40, f0 * 8.93, f0 * 13.3],
                  [0.22, 0.16, 0.10, 0.06, 0.035], [1, 0.7, 0.45, 0.28, 0.15], seed + 61, detune=0.015)
    # Leg actuators settle under the load: a faint falling whine and a pressure hiss.
    whine_f = rng.uniform(190, 240) * (1 - 0.18 * (1 - np.exp(-np.maximum(t - 0.05, 0) / 0.25)))
    whine = (np.sin(2 * np.pi * np.cumsum(whine_f) / RATE) + 0.35 * np.sin(4 * np.pi * np.cumsum(whine_f) / RATE)) \
        * env_exp(t, 0.06, 0.32, 0.07)
    hiss = bp(band_noise(dur, 1800, 9000, seed + 71), 2200, 6500) * env_exp(t, 0.07, 0.22, 0.05)
    x = (0.38 * sub + 1.0 * body + 0.55 * mass + mid_level * mid + crunch_level * crunch / (np.sqrt(np.mean(crunch ** 2)) * 6 + 1e-9)
         + 0.11 * debris / (np.sqrt(np.mean(debris ** 2)) * 6 + 1e-9) + 0.05 * slide + clank_level * clank
         + 0.012 * whine + hiss_level * hiss)
    x = hp(x, 20, 2)
    ir = room_ir(1.2, seed + 81, 0.32, [(0.031, 0.32), (0.067, 0.22), (0.118, 0.17), (0.19, 0.11), (0.27, 0.07)])
    x = place(x, ir, 0.16 if soil else 0.2)
    return fade_tail(x, 0.25)


# --------------------------------------------------------------- joint load
def joint_load(seed):
    rng = np.random.default_rng(seed)
    dur = 0.52
    t = times(dur)
    # A loaded actuator groans: a buzzy harmonic stack bent up as the load comes on and back as it settles.
    f0 = rng.uniform(68, 92)
    bend = f0 * (1 + 0.12 * np.sin(np.pi * np.clip(t / 0.5, 0, 1)) ** 1.5)
    # Few, falling harmonics: it plays on every stance change and reach, so it must not buzz.
    groan = sum(k ** -1.4 * np.sin(2 * np.pi * k * np.cumsum(bend) / RATE + rng.uniform(0, 6.28)) for k in range(1, 8))
    groan = lp(groan, 700, 2) * (np.clip(t / 0.06, 0, 1) * np.exp(-np.maximum(t - 0.14, 0) / 0.13))
    # Metal on metal under pressure: stick-slip pulses, each ringing two resonances (a creak).
    out = np.zeros_like(t)
    rate = rng.uniform(26, 42)
    at = rng.uniform(0.02, 0.05)
    res = [rng.uniform(420, 620), rng.uniform(1100, 1500)]
    while at < 0.34:
        i = int(at * RATE)
        n = int(0.025 * RATE)
        if i + n < len(t):
            u = np.arange(n) / RATE
            amp = np.sin(np.pi * at / 0.36) * rng.uniform(0.5, 1.0)
            out[i:i + n] += amp * (np.sin(2 * np.pi * res[0] * u) * np.exp(-u / 0.006) + 0.5 * np.sin(2 * np.pi * res[1] * u) * np.exp(-u / 0.003))
        at += (1 / rate) * rng.uniform(0.7, 1.3)
    creak = out
    hiss = bp(band_noise(dur, 1800, 9000, seed + 7), 2400, 7000) * env_exp(t, 0.24, 0.11, 0.04)
    thunk = modal(t, 0.0, [rng.uniform(95, 125), 260, 575], [0.08, 0.05, 0.03], [1, 0.4, 0.2], seed + 9) * 0.5
    x = 0.55 * groan / (np.abs(groan).max() + 1e-9) + 0.25 * creak / (np.abs(creak).max() + 1e-9) + 0.06 * hiss + 0.3 * thunk
    x = hp(x, 35, 2)
    ir = room_ir(0.8, seed + 11, 0.22, [(0.023, 0.25), (0.051, 0.15), (0.094, 0.1)])
    return fade_tail(place(x, ir, 0.15), 0.08)


# --------------------------------------------------------------- AT Field
def at_pressure(seed):
    rng = np.random.default_rng(seed)
    dur = 1.1
    t = times(dur)
    # The field takes the blow: a hard strike, a glassy inharmonic ring that bends a little under the load and
    # shimmers as the ripple spreads (detuned pairs beat at a few hertz, the top is tremoloed at 14-22 Hz).
    f0 = rng.uniform(270, 400)
    # Two shell shapes, so the takes differ in colour and not only in pitch.
    ratios = [[1.0, 1.414, 2.236, 2.828, 3.873, 5.0, 6.32, 8.6, 11.3],
              [1.0, 1.593, 2.135, 2.653, 3.155, 4.17, 5.43, 7.9, 10.6]][seed % 2]
    # Short enough that hits a second apart do not pile up into a drone.
    taus = [0.62, 0.47, 0.35, 0.27, 0.19, 0.13, 0.08, 0.06, 0.04]
    amps = [1.0, 0.75, 0.6, 0.45, 0.32, 0.22, 0.14, 0.12, 0.09]
    glide = 1 - 0.012 * (1 - np.exp(-t / 0.4))
    ring = np.zeros_like(t)
    for k, (q, tau, a) in enumerate(zip(ratios, taus, amps)):
        # Unequal pairs: the beat shimmers without dropping the ring out.
        for d, share in ((-1, 0.68), (1, 0.32)):
            beat = rng.uniform(1.5, 4.0) * d
            ring += share * a * np.sin(2 * np.pi * np.cumsum((f0 * q + beat) * glide) / RATE + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    trem_rate = rng.uniform(14, 22)
    shimmer = 1 - 0.35 * np.exp(-t / 0.5) * (0.5 + 0.5 * np.sin(2 * np.pi * trem_rate * t))
    ring = ring * shimmer * np.clip(t / 0.002, 0, 1)
    strike = hp(np.random.default_rng(seed + 1).standard_normal(len(t)), 1500, 2) * np.exp(-t / 0.004)
    thump_f = 46 + 34 * np.exp(-t / 0.05)
    thump = np.tanh(1.4 * osc(thump_f)) * env_exp(t, 0.0, 0.2, 0.003)
    air = bp(band_noise(dur, 600, 6000, seed + 3), 800, 4500) * env_exp(t, 0.0, 0.09, 0.006)
    knock = modal(t, 0.0, [rng.uniform(95, 130), 210], [0.12, 0.06], [1, 0.4], seed + 7)
    x = (0.42 * ring / (np.abs(ring).max() + 1e-9) + 0.30 * strike / (np.abs(strike).max() + 1e-9) + 0.4 * thump
         + 0.3 * knock + 0.08 * air)
    x = hp(x, 25, 2)
    ir = room_ir(1.4, seed + 5, 0.4, [(0.04, 0.3), (0.09, 0.2), (0.16, 0.14), (0.26, 0.09)], bright=9000)
    return fade_tail(place(x, ir, 0.24), 0.3)


def at_tear(seed):
    rng = np.random.default_rng(seed)
    dur = 1.6
    t = times(dur)
    # The field gives way: the ring is wrenched downward and breaks into shards, under a low collapse.
    f0 = rng.uniform(320, 360)
    sweep = f0 * (1 - 0.45 * (1 - np.exp(-t / 0.35)))
    ring = sum(a * np.sin(2 * np.pi * np.cumsum(sweep * q) / RATE + rng.uniform(0, 6.28)) * np.exp(-t / tau)
               for q, tau, a in zip([1, 1.414, 2.236, 2.828, 3.873], [0.55, 0.42, 0.3, 0.22, 0.15], [1, .7, .55, .4, .3]))
    ring = ring * (1 + 0.3 * band_noise(dur, 20, 200, seed + 2) * np.clip(t / 0.3, 0, 1))
    shards = np.zeros_like(t)
    for k in range(int(rng.integers(55, 80))):
        at = rng.uniform(0.01, 0.55) ** 1.4
        fk = np.exp(rng.uniform(np.log(900), np.log(7000)))
        shards += modal(t, at, [fk, fk * 1.53, fk * 2.11], [0.06, 0.035, 0.02], [1, 0.5, 0.25], seed + 100 + k, 0.01) \
            * rng.uniform(0.2, 1.0) * np.exp(-at / 0.35)
    crack = hp(np.random.default_rng(seed + 4).standard_normal(len(t)), 900, 2) * env_exp(t, 0.0, 0.03, 0.001)
    boom = np.tanh(1.5 * osc(30 + 26 * np.exp(-t / 0.08))) * env_exp(t, 0.0, 0.45, 0.004)
    rush = bp(band_noise(dur, 300, 5000, seed + 6), 400, 3500) * env_exp(t, 0.02, 0.35, 0.06)
    x = (0.35 * ring / (np.abs(ring).max() + 1e-9) + 0.3 * shards / (np.abs(shards).max() + 1e-9)
         + 0.25 * crack / (np.abs(crack).max() + 1e-9) + 0.6 * boom + 0.12 * rush)
    x = hp(x, 22, 2)
    ir = room_ir(1.8, seed + 8, 0.5, [(0.05, 0.3), (0.11, 0.22), (0.2, 0.15), (0.33, 0.1)], bright=9000)
    return fade_tail(place(x, ir, 0.26), 0.35)


# --------------------------------------------------------------- siren
LOOP = 8.0          # two wails a loop
WAIL = LOOP / 2


def wail_pitch(t, low=330.0, high=760.0):
    """One air-raid wail every WAIL seconds: 1.9 s climb, 0.9 s hold, 1.2 s fall (periodic, smooth)."""
    u = np.mod(t, WAIL)
    climb, hold = 1.9, 0.9
    up = r61.smooth(0, climb, u)
    down = r61.smooth(climb + hold, WAIL, u)
    return low + (high - low) * (up - down)


def siren_voice(f):
    """A two-rotor siren through a horn loudspeaker, from its pitch curve (Hz per sample). The second rotor
    sits a minor third up (6:5)."""
    phase = 2 * np.pi * np.cumsum(f) / RATE
    tone = np.zeros_like(f)
    for rotor, gain in ((1.0, 1.0), (1.2, 0.55)):
        for k in range(1, 9):
            # Rotor ports make a pulse-like wave; roll its harmonics off at 9 dB an octave.
            tone += gain * k ** -1.5 * np.sin(k * rotor * phase)
    tone = np.tanh(1.8 * tone) / np.tanh(1.8)
    # The horn: strong 500 Hz - 3 kHz, little below or above.
    return lp(hp(tone, 380, 2), 3800, 2)


def city_echo_ir(seconds, seed):
    """Speakers all over the city: the same signal arriving late and darker from far loudspeakers and facades."""
    early = [(0.13, 0.55), (0.29, 0.42), (0.47, 0.33), (0.71, 0.24), (1.02, 0.16), (1.38, 0.1)]
    return room_ir(seconds, seed, 0.9, early, bright=3500, dark=700)


def alarm_loop(seed):
    """Seamless 8 s loop: the fundamental makes a whole number of cycles (a multiple of 5, so the 6:5 rotor
    does too), and the city echo is applied as a circular convolution, so its tail wraps into the start."""
    n = int(LOOP * RATE)
    t = np.arange(3 * n) / RATE
    f = wail_pitch(t)
    cycles = np.sum(f[:n]) / RATE
    f = f * (np.round(cycles / 5) * 5 / cycles)
    # Three loops through the (causal) filters, keep the middle one: its filter state at both ends is the
    # steady state, so the joint carries no start-up transient.
    x = siren_voice(f)[n:2 * n]
    ir = city_echo_ir(LOOP, seed + 1)
    wet = np.real(np.fft.ifft(np.fft.fft(x) * np.fft.fft(ir, n)))
    wet = wet / (np.sqrt(np.mean(wet ** 2)) + 1e-12) * np.sqrt(np.mean(x ** 2))
    return 0.62 * x + 0.38 * wet


def siren_once(seed):
    """One wail of the same voice and city echo, with a natural tail (a one-shot of about 3 s)."""
    dur = 3.0
    t = times(dur)
    # Climb, a short hold, then the rotor spins down: pitch and level fall together.
    f = 330 + 430 * (r61.smooth(0, 1.5, t) - r61.smooth(2.1, 3.0, t) * 0.7)
    x = siren_voice(f) * np.clip(t / 0.12, 0, 1) * (1 - r61.smooth(2.0, 3.0, t) ** 0.8)
    ir = city_echo_ir(2.0, seed + 1)
    y = fftconvolve(x, ir)[:len(x)]
    y = y / (np.sqrt(np.mean(y ** 2)) + 1e-12) * np.sqrt(np.mean(x ** 2))
    return fade_tail(0.62 * x + 0.38 * y, 0.2)


# --------------------------------------------------------------- catalogue
# event -> (new file stem, count, maker, loudness target LUFS, the files it replaces)
FAMILIES = {
    'eva_foot_concrete': ('eva_foot_concrete_r65', 6, lambda i: footstep(6500 + 17 * i, False), -19.5,
                          ['eva_foot_concrete_r47_%d' % i for i in range(6)]),
    'eva_foot_soil': ('eva_foot_soil_r65', 6, lambda i: footstep(6600 + 17 * i, True), -20.5,
                      ['eva_foot_soil_r47_%d' % i for i in range(6)]),
    'eva_joint_load': ('eva_joint_load_r65', 4, lambda i: joint_load(6700 + 13 * i), -17.5,
                       ['eva_joint_load_r47_%d' % i for i in range(3)]),
    'eva_at_pressure': ('eva_at_pressure_r65', 4, lambda i: at_pressure(6800 + 11 * i), -21.0,
                        ['eva_contact_body_r36_%d' % i for i in range(6)]),
    'eva_at_tear': ('eva_at_tear_r65', 2, lambda i: at_tear(6900 + 7 * i), -21.5, ['eva_at_tear']),
    'alarm': ('facility_alarm_loop_r65', 1, lambda i: alarm_loop(7000), -17.0, ['facility_siren']),
    'facility_siren': ('facility_siren_r65', 1, lambda i: siren_once(7000), -16.5, ['facility_siren']),
}
LOOPED = {'alarm'}


def build(out, install):
    out.mkdir(parents=True, exist_ok=True)
    sounds = json.loads((ASSET.parent / 'sounds.json').read_text('utf8'))
    report = {}
    for event, (stem, count, make, target, old) in FAMILIES.items():
        rows = []
        names = []
        for i in range(count):
            name = stem if count == 1 else '%s_%d' % (stem, i)
            x = to_lufs(make(i), target)
            if event in LOOPED:
                # The joint must not click: compare the last and first samples' step with a typical step.
                step = abs(x[0] - x[-1]); typical = float(np.median(np.abs(np.diff(x))))
                assert step < 6 * typical + 1e-4, ('loop seam', step, typical)
            path = out / (name + '.ogg')
            r61.encode(x.astype(np.float32), path)
            back = r61.decode(path)
            m = r61.measure(back)
            rows.append(dict(file=name, **m))
            names.append(name)
            if install:
                shutil.copyfile(path, ASSET / (name + '.ogg'))
        report[event] = dict(new=rows, replaces=old)
        if install:
            # Each new take keeps the old entry's settings (attenuation_distance, stream).
            entry = sounds[event]
            first = entry['sounds'][0]
            template = {k: v for k, v in first.items() if k != 'name'} if isinstance(first, dict) else {}
            if event == 'eva_at_pressure':
                template.pop('pitch', None)  # 1.15 lifted the old body-contact thud; the field ring is tuned as made
            entry['sounds'] = [dict({'name': 'projectseele:' + n}, **template) if template else 'projectseele:' + n for n in names]
        print(event, [(r['file'], r['lufs'], r['peak'], r['seconds']) for r in rows], flush=True)
    if install:
        text = json.dumps(sounds, ensure_ascii=False, indent=2) + '\n'
        (ASSET.parent / 'sounds.json').write_text(text, encoding='utf8')
    (out / 'r65_measure.json').write_text(json.dumps(report, indent=1), encoding='utf8')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--install', action='store_true')
    a = p.parse_args()
    build(a.out, a.install)


if __name__ == '__main__':
    main()
