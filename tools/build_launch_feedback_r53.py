"""Deterministic original electrical-discharge and sliding-contact synthesis.

No recordings, speech, official media, network inputs or third-party samples.
The mono assets remain positional. WAV previews and decoded metrics are local
authoring evidence, not a substitute for in-game listening.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import wave
import numpy as np
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 48000


def filtered_noise(rng, n, low, high):
    a = sosfilt(butter(3, [low, high], fs=SR, btype='bandpass', output='sos'), rng.normal(size=n))
    return a / max(1e-8, np.std(a))


def finish(a):
    a = a - np.mean(a)
    fade = min(len(a) // 4, round(SR * .025))
    a[:round(SR*.001)] *= np.linspace(0, 1, round(SR*.001))
    a[-fade:] *= np.linspace(1, 0, fade) ** 2
    # Soft saturation limits isolated crack peaks without flattening the body.
    a = np.tanh(a * .8)
    return a * (.82 / max(abs(a)))


def burst():
    rng = np.random.default_rng(53001)
    t = np.arange(round(SR * 1.85)) / SR
    a = filtered_noise(rng, len(t), 700, 10500) * np.exp(-t / .066) * .64
    a += np.sin(2*np.pi*(54*t + 3.8*(1-np.exp(-t/.035)))) * np.exp(-t/.29) * .7
    a += filtered_noise(rng, len(t), 90, 720) * np.exp(-t/.24) * .17
    for delay, weight in ((.0, .30), (.018, .16), (.046, .12), (.093, .07), (.16, .04)):
        dt = np.maximum(0, t-delay)
        a += filtered_noise(rng, len(t), 1800, 13500) * np.exp(-dt/.006) * (t >= delay) * weight
    chirp = np.sin(2*np.pi*(810*t+1200*.11*(1-np.exp(-t/.11))))
    a += chirp * np.exp(-t/.18) * .055
    # Finite tunnel reflections, keeping the first electrical crack distinct.
    dry = a.copy()
    for delay, weight in ((.063,.18),(.131,.12),(.247,.08),(.411,.035)):
        k=round(delay*SR)
        a[k:] += dry[:-k]*weight
    return finish(a)


def friction(seed):
    rng=np.random.default_rng(seed)
    t=np.arange(round(SR*.31))/SR
    envelope=np.sin(np.pi*np.clip(t/.31,0,1))**.65
    a=filtered_noise(rng,len(t),1200,11500)*.18
    a+=filtered_noise(rng,len(t),160,1200)*.075
    for frequency, weight in ((1360,.035),(2513,.025),(3971,.014)):
        a += np.sin(2*np.pi*(frequency*t+14*np.sin(2*np.pi*19*t))) * weight
    for delay in rng.uniform(.025,.24,5):
        dt=np.maximum(0,t-delay)
        a+=filtered_noise(rng,len(t),2600,14000)*np.exp(-dt/.003)*(t>=delay)*.07
    return finish(a*envelope)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--ffmpeg',required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    assets=ROOT/'src/main/resources/assets/projectseele'
    outputs={'launch_electric_burst_r53':burst()}
    outputs.update({f'launch_rail_friction_r53_{i}':friction(53100+i) for i in range(3)})
    records=[]
    for name, signal in outputs.items():
        preview=args.out/(name+'.wav');dest=assets/'sounds'/(name+'.ogg')
        with wave.open(str(preview),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR)
            f.writeframes(np.rint(signal*32767).astype('<i2').tobytes())
        subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(preview),'-c:a','libvorbis','-q:a','6',str(dest)],check=True)
        decoded=subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-i',str(dest),'-f','f32le','-ac','1','-ar',str(SR),'-'],capture_output=True,check=True)
        samples=np.frombuffer(decoded.stdout,dtype='<f4')
        assert np.isfinite(samples).all() and .1 < max(abs(samples)) < .99
        assert abs(len(samples)-len(signal)) < 1024
        records.append(dict(asset=str(dest.relative_to(ROOT)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
            seconds=len(signal)/SR,decoded_peak=float(max(abs(samples))),decoded_rms=float(np.sqrt(np.mean(samples**2))),
            source='Original deterministic mathematical synthesis; no sampled recording',channels=1,sample_rate=SR))
    p=assets/'sounds.json';catalog=json.loads(p.read_text('utf8'))
    for event,names in {'launch_electric_burst_r53':['launch_electric_burst_r53'],
                        'launch_rail_friction_r53':[f'launch_rail_friction_r53_{i}' for i in range(3)]}.items():
        catalog[event]={'subtitle':'subtitles.projectseele.'+event,'sounds':[{'name':'projectseele:'+n,'stream':False} for n in names]}
    p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n','utf8')
    for lang,labels in {'zh_cn':['发射轨道：电流爆发','发射轨道：高速摩擦'],
                        'en_us':['Launch rails discharge','Launch rails spark and scrape']}.items():
        p=assets/'lang'/(lang+'.json');data=json.loads(p.read_text('utf8'))
        for key,label in zip(('launch_electric_burst_r53','launch_rail_friction_r53'),labels):data['subtitles.projectseele.'+key]=label
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
    receipt=dict(generator=str(Path(__file__).relative_to(ROOT)),assets=records,listening='Pending in-game positional mix and user listening')
    (args.out/'AUDIO_SYNTHESIS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    provenance=assets/'audio/launch_feedback_r53.json';provenance.parent.mkdir(exist_ok=True)
    provenance.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
