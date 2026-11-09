"""R61 original Ramiel attack sounds.

Every waveform below is seeded mathematical synthesis: band-limited additive
tones and FFT-shaped noise. No recording, sample, film, TV or game audio is
read, so nothing here derives from official Evangelion audio.

Usage:
  python tools/build_ramiel_audio_r61.py --out <candidates dir>
  python tools/build_ramiel_audio_r61.py --out <dir> --install
  python tools/build_ramiel_audio_r61.py --out <dir> --install beam_charge=b_energy_riser,drill=c_deep_churn

--install copies the measured default of each event (or the variant named on
the command line) over the shipped asset. Which variant sounds right is the
owner's call by ear; the measurements only reject the broken ones.
"""
from pathlib import Path
import argparse, json, shutil, subprocess
import numpy as np
from scipy.ndimage import minimum_filter1d
from scipy.signal import butter, sosfilt, lfilter, medfilt, resample_poly, hilbert

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'src/main/resources/assets/projectseele/sounds'
RATE = 48000


# --------------------------------------------------------------- primitives
def times(seconds):
    return np.arange(int(round(seconds * RATE))) / RATE


def osc(freq):
    """Sine driven by an instantaneous frequency array (Hz); never aliases."""
    if np.ndim(freq) == 0:
        raise ValueError('osc needs a frequency array; multiply a constant by np.ones_like(t)')
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE)


def smooth(a, b, x):
    u = np.clip((x - a) / max(b - a, 1e-9), 0, 1)
    return u * u * (3 - 2 * u)


def attack(t, tau):
    return 1 - np.exp(-t / tau)


def release(n, seconds):
    k = int(seconds * RATE)
    tail = np.ones(n)
    tail[-k:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k)
    return tail


def shaped_noise(seconds, gain, seed, nfft=4096):
    """Noise whose spectrum follows gain(freqs, u) with u running 0..1 over the clip."""
    n = int(round(seconds * RATE))
    hop = nfft // 4
    total = n + 2 * nfft
    x = np.random.default_rng(seed).standard_normal(total)
    window = np.sqrt(np.hanning(nfft + 1)[:-1])
    freqs = np.fft.rfftfreq(nfft, 1 / RATE)
    out = np.zeros(total)
    for start in range(0, total - nfft, hop):
        u = float(np.clip((start - nfft / 2) / n, 0, 1))
        out[start:start + nfft] += np.fft.irfft(np.fft.rfft(x[start:start + nfft] * window) * gain(freqs, u)) * window
    out = out[nfft:nfft + n]
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-12)


def log_band(freqs, centre, octaves):
    with np.errstate(divide='ignore'):
        return np.exp(-0.5 * (np.log2(np.maximum(freqs, 1) / centre) / octaves) ** 2)


def lowpass_gain(freqs, cut, order=4):
    return 1 / np.sqrt(1 + (freqs / cut) ** (2 * order))


def band_noise(seconds, lo, hi, seed):
    n = int(round(seconds * RATE))
    x = np.random.default_rng(seed).standard_normal(n)
    y = sosfilt(butter(4, [lo, hi], fs=RATE, btype='bandpass', output='sos'), x)
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-12)


def loop_fades(n, seconds, equal_power):
    """Fades for a clip re-triggered every (length - seconds): their overlap keeps level flat."""
    k = int(seconds * RATE)
    g = np.ones(n)
    ramp = (np.arange(k) + .5) / k
    if equal_power:
        g[:k] = np.sin(ramp * np.pi / 2)
        g[-k:] = np.cos(ramp * np.pi / 2)
    else:
        g[:k] = ramp
        g[-k:] = 1 - ramp
    return g


# ----------------------------------------------------------- beam_charge (2.6 s)
CHARGE = 2.6


def charge_crystal(seed):
    t = times(CHARGE)
    p = t / CHARGE
    f0 = 110 * 2 ** (0.92 * p ** 1.6)
    out = np.zeros_like(t)
    rows = [(1, 1, 0, .35), (2, .55, 0, .5), (2.76, .34, .1, .6), (3.52, .22, .25, .75), (5.40, .09, .45, .9), (6.87, .05, .6, 1)]
    for ratio, amp, a, b in rows:
        wander = .9 * np.sin(2 * np.pi * np.cumsum(.8 + ratio * .13) / RATE * np.ones_like(t)) if ratio > 3 else 0
        for detune in (-.35 * (1 + ratio / 4), .35 * (1 + ratio / 4)):
            out += .5 * amp * smooth(a, b, p) * osc(f0 * ratio + detune + wander)
    tremolo = 1 - .10 * (.5 + .5 * np.sin(2 * np.pi * np.cumsum(3 + 5 * p) / RATE))
    air = shaped_noise(CHARGE, lambda f, u: log_band(f, 2600 + 1400 * u, .55), seed) * .012 * p ** 2
    return (out * tremolo + air) * smooth(0, .5 / CHARGE, p) * (.30 + .70 * p ** 1.8) * release(len(t), .07)


def charge_riser(seed):
    t = times(CHARGE)
    p = t / CHARGE
    low = shaped_noise(CHARGE, lambda f, u: log_band(f, 180 * (700 / 180) ** (u ** 1.2), .45), seed)
    high = shaped_noise(CHARGE, lambda f, u: log_band(f, 900 * (2300 / 900) ** (u ** 1.4), .32), seed + 1)
    tones = .55 * osc(55 + 0 * t) + .32 * osc(165 + 0 * t) + .14 * osc(275 + 0 * t)
    out = low * (.20 + .80 * p ** 1.7) + .16 * high * p ** 2.4 + tones * (.42 + .58 * p ** 1.2)
    return out * smooth(0, .45 / CHARGE, p) * release(len(t), .08)


def charge_pulses(seed):
    t = times(CHARGE)
    p = t / CHARGE
    n = len(t)
    rate = 3.2 + 19 * p ** 2.2
    phase = np.cumsum(rate) / RATE
    starts = np.searchsorted(phase, np.arange(1, int(phase[-1]) + 1))
    pulses = np.zeros(n)
    click = np.random.default_rng(seed).standard_normal(n)
    click = sosfilt(butter(2, 900, fs=RATE, btype='low', output='sos'), click)
    for s in starts:
        pk = p[s]
        tau = .085 - .04 * pk
        length = min(n - s, int(.5 * RATE))
        u = t[:length]
        env = attack(u, .003) * np.exp(-u / tau)
        f = 98 * (1 + .7 * pk)
        pulses[s:s + length] += (np.sin(2 * np.pi * f * u) + .25 * np.sin(2 * np.pi * 2 * f * u) + .55 * click[s:s + length]) * env
    f0 = 82.41 * 2 ** (1.0 * p ** 1.5)
    bed = (.5 * osc(f0) + .28 * osc(f0 * 3) + .12 * osc(f0 * 5)) * (.25 + .75 * p ** 1.5)
    return (pulses * .42 + bed * .6) * smooth(0, .3 / CHARGE, p) * release(len(t), .08)


def charge_formant(seed):
    t = times(CHARGE)
    p = t / CHARGE
    rng = np.random.default_rng(seed)
    f0 = 130.81
    out = np.zeros_like(t)
    centre = 260 * (1500 / 260) ** (p ** 1.4)
    for k in range(1, 17):
        freq = k * f0
        detune = rng.uniform(-.25, .25)
        gain = np.exp(-.5 * (np.log2(freq / centre) / .62) ** 2) / np.sqrt(k)
        out += gain * osc((freq + detune) * np.ones_like(t))
    return out * smooth(0, .45 / CHARGE, p) * (.32 + .68 * p ** 1.5) * release(len(t), .08)


# ------------------------------------------------------------- beam_fire (1.5 s)
FIRE = 1.5


def fire_discharge(seed):
    t = times(FIRE)
    a = attack(t, .0035)
    thump = osc(34 + 84 * np.exp(-t / .065)) * np.exp(-t / .30) * a
    glide = 1 - .24 * (1 - np.exp(-t / .55))
    body = np.zeros_like(t)
    for ratio, amp, tau in [(1, .62, .48), (1.6, .40, .36), (2.4, .28, .30), (3.4, .18, .22), (4.9, .10, .15)]:
        body += amp * osc(165 * ratio * glide) * np.exp(-t / tau)
    burst = band_noise(FIRE, 120, 3200, seed) * np.exp(-t / .012) * a
    tail = shaped_noise(FIRE, lambda f, u: lowpass_gain(f, 180 + 1220 * np.exp(-u * FIRE / .25)), seed + 1) * np.exp(-t / .42) * attack(t, .02)
    mid = shaped_noise(FIRE, lambda f, u: log_band(f, 900 - 500 * u, .85), seed + 2) * np.exp(-t / .28) * attack(t, .006)
    return (.58 * thump + .78 * a * body + .13 * burst + .26 * tail + .09 * mid) * release(len(t), .12)


def fire_lance(seed):
    t = times(FIRE)
    a = attack(t, .002)
    strike = np.zeros_like(t)
    for freq, amp, tau in [(1180, .30, .16), (1730, .22, .12), (2290, .14, .09), (3120, .08, .06)]:
        strike += amp * np.sin(2 * np.pi * freq * t) * np.exp(-t / tau)
    tone = np.zeros_like(t)
    for ratio, amp, tau in [(1, .75, .62), (2, .38, .44), (3, .22, .30), (5, .09, .18)]:
        tone += amp * osc(220 * ratio * (1 - .08 * (1 - np.exp(-t / .7)))) * np.exp(-t / tau)
    sub = osc(55 + 0 * t) * np.exp(-t / .5)
    return (a * strike * .55 + a * tone * .8 + a * sub * .7) * release(len(t), .12)


def fire_whoomp(seed):
    t = times(FIRE)
    a = attack(t, .006)
    air = shaped_noise(FIRE, lambda f, u: lowpass_gain(f, 170 + 1250 * np.exp(-u * FIRE / .2), 3), seed)
    sub = osc(44 + 22 * np.exp(-t / .1)) * np.exp(-t / .7)
    return (air * np.exp(-t / .5) * a * .72 + sub * a * .5) * release(len(t), .15)


def fire_column(seed):
    t = times(FIRE)
    env = attack(t, .012) * (.25 + .75 * np.exp(-t / .55)) * smooth(0, .9, 1.5 - t)
    tone = np.zeros_like(t)
    for freq, amp in [(130.81, .9), (131.91, .7), (261.63, .5), (263.2, .35), (392.0, .24), (523.25, .1)]:
        tone += amp * osc(freq * (1 - .05 * t / FIRE))
    thump = osc(40 + 60 * np.exp(-t / .05)) * np.exp(-t / .22) * attack(t, .004)
    air = shaped_noise(FIRE, lambda f, u: log_band(f, 700 - 350 * u, .8), seed) * env
    return (tone * env * .45 + thump * .95 + air * .12) * release(len(t), .1)


# ----------------------------------------------------- drill (re-triggered every second)
DRILL = 1.25
DRILL_OVERLAP = .25


def drill_mix(tone, grind):
    n = len(tone)
    return tone * loop_fades(n, DRILL_OVERLAP, False) + grind * loop_fades(n, DRILL_OVERLAP, True)


def drill_rotor(seed):
    t = times(DRILL)
    tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(55, .68), (165, .42), (275, .22), (385, .12), (605, .05)])
    rotor = 1 - .22 * (.5 + .5 * np.cos(2 * np.pi * 7 * t))
    grind = shaped_noise(DRILL, lambda f, u: log_band(f, 430, .95), seed) * (1 - .30 * (.5 + .5 * np.cos(2 * np.pi * 7 * t + 1.1)))
    return drill_mix(tone * rotor * .75, grind * .24)


def drill_bore(seed):
    t = times(DRILL)
    tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(78, .62), (196, .40), (311, .30), (523, .16), (871, .05)])
    rotor = 1 - .25 * (.5 + .5 * np.cos(2 * np.pi * 5 * t))
    grind = shaped_noise(DRILL, lambda f, u: log_band(f, 720, .7), seed) * (1 - .35 * (.5 + .5 * np.cos(2 * np.pi * 5 * t + .8)))
    return drill_mix(tone * rotor * .72, grind * .2)


def drill_churn(seed):
    t = times(DRILL)
    tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(70, .55), (183, .25)])
    sway = 1 - .35 * (.5 + .5 * np.cos(2 * np.pi * 3 * t))
    low = shaped_noise(DRILL, lambda f, u: lowpass_gain(f, 420, 3) * (1 - np.exp(-(f / 60) ** 2)), seed) * sway
    return drill_mix(tone * .55, low * .42)


# ----------------------------------------------------------- beam impact / explosion
BLAST = 2.6


def blast_body(t, seed, cut_tau, cut_top):
    air = shaped_noise(BLAST, lambda f, u: lowpass_gain(f, 130 + cut_top * np.exp(-u * BLAST / cut_tau), 3), seed)
    return air * np.exp(-t / .62) * attack(t, .009)


def blast_mass(t, seed, tau):
    mass = shaped_noise(BLAST, lambda f, u: log_band(f, 300 - 130 * u, 1.05), seed)
    return mass * np.exp(-t / tau) * attack(t, .014)


def blast_dark(seed):
    t = times(BLAST)
    boom = osc(30 + 26 * np.exp(-t / .12)) * np.exp(-t / .7) * attack(t, .006)
    rumble = shaped_noise(BLAST, lambda f, u: lowpass_gain(f, 170, 3), seed + 1) * np.exp(-t / .9) * attack(t, .02)
    return (blast_body(t, seed, .10, 1900) * .55 + blast_mass(t, seed + 5, .75) * .85 + boom * .42 + rumble * .5) * release(len(t), .2)


def blast_glass(seed):
    t = times(BLAST)
    boom = osc(32 + 28 * np.exp(-t / .1)) * np.exp(-t / .6) * attack(t, .005)
    shards = np.zeros_like(t)
    rng = np.random.default_rng(seed + 2)
    for f, amp, tau in [(1350, .34, .42), (1980, .26, .32), (2640, .18, .26), (3510, .10, .18)]:
        delay = rng.uniform(.01, .06)
        u = np.maximum(0, t - delay)
        shards += amp * (np.sin(2 * np.pi * f * u) + .7 * np.sin(2 * np.pi * (f + 2.3) * u)) * np.exp(-u / tau) * (t > delay)
    return (blast_body(t, seed, .09, 1500) * .5 + blast_mass(t, seed + 6, .62) * .9 + boom * .42 + shards * .09) * release(len(t), .2)


def blast_rumble(seed):
    t = times(BLAST)
    boom = osc(27 + 20 * np.exp(-t / .18)) * np.exp(-t / .95) * attack(t, .008)
    roll = shaped_noise(BLAST, lambda f, u: lowpass_gain(f, 90 + 900 * np.exp(-u * BLAST / .5), 3), seed + 3)
    swell = np.exp(-t / 1.0) * attack(t, .05)
    return (blast_body(t, seed, .08, 1300) * .62 + boom * .5 + roll * swell * .7) * release(len(t), .25)


EVENTS = {
    'beam_charge': dict(target_momentary=-16.0, targets='eva_land_r47 的 Mmax -15.9', seed=6100, variants={
        'a_crystal_swell': (charge_crystal, '玻璃非谐波分音的上行膨胀，主音 110 到 207 Hz，音高只升约一个八度'),
        'b_energy_riser': (charge_riser, '两段随时间升高的噪声带，加 55/165/275 Hz 低音，没有单一音高的长滑音'),
        'c_capacitor_pulses': (charge_pulses, '从约 3 Hz 加速到约 22 Hz 的低频脉冲，叠一层上行低音（设计意图：电容充能）'),
        'd_formant_choir': (charge_formant, '固定 C3 泛音列，共振峰从 260 Hz 扫到 1.5 kHz，音高不动、音色变亮'),
    }),
    'beam_fire': dict(target_momentary=-15.5, targets='旧 beam_fire 和 eva_land_r47 都是 -15.9', seed=6200, variants={
        'a_discharge': (fire_discharge, '下滑低频冲击加下行分音束，开头只有一小段低通噪声'),
        'b_crystal_lance': (fire_lance, '短促的玻璃击打分音叠 220 Hz 持续音和 55 Hz 底音，偏清脆'),
        'c_pressure_whoomp': (fire_whoomp, '几乎全是低通噪声和次低频，频谱最暗'),
        'd_beam_column': (fire_column, 'C3/C4/G4 的慢拍频持续音柱，开头垫一记低频冲击'),
    }),
    'drill': dict(target_momentary=-20.5, targets='shamshel_whip_charge 的 -19.9，持续循环压在撞击音以下', seed=6300, variants={
        'a_rotor_grind': (drill_rotor, '55 Hz 奇次谐波加 7 Hz 转子起伏和中频研磨噪声'),
        'b_crystal_bore': (drill_bore, '78/196/311/523 Hz 非谐波音，加 5 Hz 起伏，音色偏晶体'),
        'c_deep_churn': (drill_churn, '以低频噪声为主、音高感最弱，加 3 Hz 缓慢摆动'),
    }),
    'cross_explosion': dict(target_momentary=-14.5, targets='旧 cross_explosion 的 -14.5', seed=6400, variants={
        'a_blast_dark': (blast_dark, '低通噪声、低中频主体和次低频冲击，没有旧版 890 Hz 的固定音调'),
        'b_blast_glass': (blast_glass, '同样的爆炸底层，上面加低电平的玻璃碎裂分音'),
        'c_blast_rumble': (blast_rumble, '起音更软、低频滚动尾巴更长'),
    }),
}


# ---------------------------------------------------------------- measurement
def find_ffmpeg():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(x, path):
    subprocess.run([find_ffmpeg(), '-v', 'error', '-y', '-f', 'f32le', '-ar', str(RATE), '-ac', '1', '-i', '-',
                    '-c:a', 'libvorbis', '-q:a', '6', str(path)], input=x.astype('<f4').tobytes(), check=True)


def decode(path):
    raw = subprocess.check_output([find_ffmpeg(), '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(RATE), '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').astype(np.float64)


def k_weight(x):
    # ITU-R BS.1770 pre-filter and RLB, 48 kHz coefficients.
    y = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585], x)
    return lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], y)


def blocks(x):
    y = k_weight(x)
    n = int(.4 * RATE)
    if len(y) < n:
        return np.array([np.mean(y ** 2)])
    return np.array([np.mean(y[i:i + n] ** 2) for i in range(0, len(y) - n + 1, n // 4)])


def momentary(x):
    return float(-.691 + 10 * np.log10(np.max(blocks(x)) + 1e-20))


def lufs(x):
    p = blocks(x)
    p = p[p > 10 ** ((-70 + .691) / 10)]
    if p.size == 0:
        return -70.0
    gated = p[p > np.mean(p) * .1]
    return float(-.691 + 10 * np.log10(np.mean(gated)))


def measure(x):
    peak = float(np.max(np.abs(x)))
    tp = float(np.max(np.abs(resample_poly(x, 4, 1))))
    active = np.where(np.abs(x) > .05 * max(peak, 1e-9))[0]
    body = x[active[0]:active[-1] + 1] if active.size else x
    rms = float(np.sqrt(np.mean(body ** 2)))
    nfft = 4096
    window = np.hanning(nfft)
    frames = [np.abs(np.fft.rfft(x[i:i + nfft] * window)) ** 2 for i in range(0, max(1, len(x) - nfft), nfft // 8)
              if np.sqrt(np.mean(x[i:i + nfft] ** 2)) > 1e-4] or [np.ones(nfft // 2 + 1) * 1e-12]
    psd = np.mean(frames, axis=0)
    freqs = np.fft.rfftfreq(nfft, 1 / RATE)
    total = np.sum(psd) + 1e-20
    log_psd = 10 * np.log10(psd + 1e-20)
    kernel = int(round(240 / (RATE / nfft)))
    kernel += 1 - kernel % 2
    excess = log_psd - medfilt(log_psd, kernel_size=kernel)
    harsh = (freqs >= 500) & (freqs <= 5000)
    top = np.max(log_psd[(freqs >= 100) & (freqs <= 10000)])
    # A tonal line counts only when it is loud enough to be heard over the rest,
    # and only beyond the +/-6 dB that averaged noise shows by itself.
    audible = harsh & (log_psd > top - 24)
    tonal = float(max(0.0, np.max(excess[audible]) - 6)) if np.any(audible) else 0.0
    # Rasp is partials beating above the sub range; a sub thump under noise is not rasp.
    env = np.abs(hilbert(sosfilt(butter(4, 150, fs=RATE, btype='high', output='sos'), x)))
    if len(env) > 256:
        e = env - np.mean(env)
        spec = np.abs(np.fft.rfft(e * np.hanning(len(e)))) ** 2
        f = np.fft.rfftfreq(len(e), 1 / RATE)
        rough = float(np.sum(spec[(f >= 20) & (f < 90)]) / (np.sum(spec[f >= 1]) + 1e-20))
    else:
        rough = 0.0
    return dict(seconds=round(len(x) / RATE, 3), peak=round(peak, 3), true_peak_db=round(float(20 * np.log10(max(tp, 1e-9))), 2),
                clipped=int(np.sum(np.abs(x) >= .9995)), dc=round(float(np.mean(x)), 5), lufs=round(lufs(x), 2),
                momentary_max=round(momentary(x), 2), crest_db=round(float(20 * np.log10(max(peak, 1e-9) / max(rms, 1e-9))), 2),
                first_sample=round(float(abs(x[0])), 4), last_sample=round(float(abs(x[-1])), 4),
                centroid_hz=round(float(np.sum(freqs * psd) / total)),
                presence_2_5k_db=round(float(10 * np.log10(np.sum(psd[(freqs >= 2000) & (freqs < 5000)]) / total + 1e-12)), 1),
                mid_300_3k_db=round(float(10 * np.log10(np.sum(psd[(freqs >= 300) & (freqs < 3000)]) / total + 1e-12)), 1),
                tonal_excess_500_5k_db=round(tonal, 1), roughness_20_90=round(rough, 3))


def retrigger_dip(x, period):
    """Level dip (dB) at the joins when the clip re-triggers every `period` seconds."""
    n = int(period * RATE)
    mix = np.zeros(4 * n + len(x))
    for i in range(4):
        mix[i * n:i * n + len(x)] += x
    w = int(.03 * RATE)
    env = np.sqrt(np.convolve(mix ** 2, np.ones(w) / w, mode='same'))
    typical = np.median(env[n:3 * n])
    joins = [np.min(env[j - w:j + w]) for j in (n, 2 * n, 3 * n)]
    return round(float(20 * np.log10(max(min(joins), 1e-9) / max(typical, 1e-9))), 1)


def limit_peaks(x, ceiling):
    """Look-ahead gain dip, 1.3 ms each side: only a transient above the ceiling is turned down."""
    side = 64
    for _ in range(3):
        over = np.abs(resample_poly(x, 4, 1))[::4][:len(x)]
        need = np.minimum(1.0, ceiling / np.maximum(over, 1e-9))
        if np.min(need) >= 1:
            break
        held = minimum_filter1d(need, size=2 * side + 1)
        kernel = np.hanning(2 * side + 3)[1:-1]
        x = x * np.convolve(held, kernel / np.sum(kernel), mode='same')
    return x


def score(m, target, dip):
    """Lower is better. Weights are a stated heuristic; they rank, they do not judge by ear."""
    return round(abs(m['momentary_max'] - target) * 1.0
                 + max(0.0, m['presence_2_5k_db'] + 16) * .35
                 + m['tonal_excess_500_5k_db'] * .25
                 + max(0.0, -15 - m['mid_300_3k_db']) * .2
                 + m['roughness_20_90'] * 12
                 + max(0.0, m['centroid_hz'] - 1400) / 300
                 + (abs(dip) * .5 if dip is not None else 0), 2)


def gates(m, dip):
    fails = []
    if m['true_peak_db'] > -1.0:
        fails.append('true peak above -1 dBFS')
    if m['clipped'] > 0:
        fails.append('clipped samples')
    if abs(m['dc']) > .002:
        fails.append('DC offset')
    if m['first_sample'] > .03 or m['last_sample'] > .02:
        fails.append('hard edge')
    if dip is not None and dip < -3.0:
        fails.append('re-trigger dip')
    return fails


EVENT_NAMES = {'beam_charge': '光束蓄力', 'beam_fire': '光束发射', 'drill': '钻击（每秒重触发一次）', 'cross_explosion': '光束落点爆炸（也是使徒死亡的十字爆炸）'}


def write_readme(out, report):
    lines = ['# 拉米尔攻击音效候选', '',
             '由 `tools/build_ramiel_audio_r61.py` 用固定种子纯数学合成，没有录音采样，也没有使用任何官方音频。',
             '`00_original` 是更换前的旧文件，留作对比。', '',
             '**这些声音好不好听只有你能判断。下面的数字只说明电平、频谱和有没有硬切，不代表好听。**', '',
             '换一个候选：在仓库根目录运行',
             '`python tools/build_ramiel_audio_r61.py --out <本目录> --install beam_charge=b_energy_riser`，',
             '或者直接把选中的 ogg 覆盖到 `src/main/resources/assets/projectseele/sounds/<事件名>.ogg`。', '',
             '指标说明：Mmax = 400 ms 窗最大响度；LUFS = 整段响度；2-5k = 刺耳频段占比；tonal = 500 Hz-5 kHz 窄带尖峰高出噪声的量；'
             'rough = 150 Hz 以上包络在 20-90 Hz 的抖动占比（越大越有毛刺感）；dip = 按每秒一次重触发时接缝处的音量跌落。', '']
    for event, r in report.items():
        lines += [f"## {event} — {EVENT_NAMES[event]}", '', f"目标 Mmax {r['target_momentary']}（对齐：{r['target_basis']}）。默认装入：`{r.get('installed', r['default'])}`（测量得分最低且通过全部门限）。", '',
                  '| 文件 | 说明 | LUFS | Mmax | 真峰值 dB | 2-5k dB | tonal | rough | dip | 末样本 | 得分 |', '|---|---|---|---|---|---|---|---|---|---|---|']
        rows = dict([('00_original', dict(r['before'], note='更换前的旧文件', score='-'))] + list(r['variants'].items()))
        for name, m in rows.items():
            dip = m.get('retrigger_dip_db')
            lines.append(f"| `{event}__{name}.ogg` | {m['note']} | {m['lufs']} | {m['momentary_max']} | {m['true_peak_db']} | {m['presence_2_5k_db']} | {m['tonal_excess_500_5k_db']} | {m['roughness_20_90']} | {'-' if dip is None else dip} | {m['last_sample']} | {m['score']} |")
        lines.append('')
    lines += ['混音参照（现有战斗音的中位数）：普通命中 Mmax -19.6，重击 -18.8，落地 -15.9，脚步 -16.3，刀切 -16.9，挥击 -27.3。', '',
              '原声的问题（测量）：蓄力比这些音响 11 dB 以上，主音一路滑到约 1.3 kHz，结尾在 0.41 的幅度上硬切；钻击的两组锯齿拍出 22 Hz 抖动，每秒重触发时有接近静音的接缝；爆炸里有一条 890 Hz 的固定音调（落点爆炸降调后约 641 Hz）。', '']
    (out / 'README.md').write_text('\n'.join(lines), encoding='utf8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'artifacts/ramiel_audio_r61'))
    ap.add_argument('--install', nargs='?', const='', default=None, help='install defaults, optionally event=variant,...')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    picked = dict(item.split('=', 1) for item in args.install.split(',') if item) if args.install else {}
    report = {}
    for event, spec in EVENTS.items():
        rows = {}
        original = out / f'{event}__00_original.ogg'
        if not original.exists():
            shutil.copyfile(ASSET / f'{event}.ogg', original)
        y = decode(original)
        before = measure(y)
        before['retrigger_dip_db'] = retrigger_dip(y, 1.0) if event == 'drill' else None
        for index, (name, (fn, note)) in enumerate(spec['variants'].items()):
            x = fn(spec['seed'] + index * 10)
            x = x - np.mean(x)
            x = x * 10 ** ((spec['target_momentary'] - momentary(x)) / 20)
            x = limit_peaks(x, 10 ** (-1.4 / 20))
            path = out / f'{event}__{name}.ogg'
            encode(x, path)
            y = decode(path)
            m = measure(y)
            m['retrigger_dip_db'] = retrigger_dip(y, 1.0) if event == 'drill' else None
            m['failed_gates'] = gates(m, m['retrigger_dip_db'])
            m['score'] = score(m, spec['target_momentary'], m['retrigger_dip_db'])
            m['note'] = note
            rows[name] = m
        passing = {k: v for k, v in rows.items() if not v['failed_gates']}
        default = min(passing or rows, key=lambda k: (passing or rows)[k]['score'])
        report[event] = dict(target_momentary=spec['target_momentary'], target_basis=spec['targets'], before=before, variants=rows, default=default)
        chosen = picked.get(event, default)
        if args.install is not None:
            shutil.copyfile(out / f'{event}__{chosen}.ogg', ASSET / f'{event}.ogg')
            report[event]['installed'] = chosen
    (out / 'measurements.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    write_readme(out, report)
    for event, r in report.items():
        print(f"\n== {event} target M-max {r['target_momentary']} ({r['target_basis']}) default={r['default']}")
        print('   name                  LUFS  Mmax   TP    crest cent  2-5k  mid  tonal rough  dip   last  score gates')
        rows = dict(original=r['before'], **r['variants'])
        for name, m in rows.items():
            print(f"   {name:20s} {m['lufs']:6.1f} {m['momentary_max']:6.1f} {m['true_peak_db']:6.2f} {m['crest_db']:5.1f} {m['centroid_hz']:5d} {m['presence_2_5k_db']:6.1f} {m['mid_300_3k_db']:5.1f} {m['tonal_excess_500_5k_db']:5.1f} {m['roughness_20_90']:6.3f} {str(m.get('retrigger_dip_db')):>6s} {m['last_sample']:6.3f} {m.get('score', '-')} {m.get('failed_gates', '')}")


if __name__ == '__main__':
    main()
