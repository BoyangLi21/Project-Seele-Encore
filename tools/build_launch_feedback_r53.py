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


def finish(a, peak=.82):
    a = a - np.mean(a)
    fade = min(len(a) // 4, round(SR * .025))
    a[:round(SR*.001)] *= np.linspace(0, 1, round(SR*.001))
    a[-fade:] *= np.linspace(1, 0, fade) ** 2
    # Soft saturation limits isolated crack peaks without flattening the body.
    a = np.tanh(a * .8)
    return a * (peak / max(abs(a)))


def burst():
    rng = np.random.default_rng(53001)
    t = np.arange(round(SR * 2.1)) / SR
    # A short contactor strike, a broad electrical body, then the heavy rail
    # impulse. Avoid the old long high-band hiss and exposed sine chirp.
    a = filtered_noise(rng, len(t), 450, 5800) * np.exp(-t/.013) * .30
    a += filtered_noise(rng, len(t), 160, 1900) * np.exp(-t/.105) * .27
    a += np.sin(2*np.pi*(46*t+1.5*(1-np.exp(-t/.055)))) * np.exp(-t/.31) * .68
    a += filtered_noise(rng, len(t), 55, 260) * np.exp(-t/.34) * .24
    for delay, weight in ((.021, .10), (.052, .07), (.088, .04)):
        dt = np.maximum(0, t-delay)
        a += filtered_noise(rng, len(t), 1100, 5700) * np.exp(-dt/.004) * (t >= delay) * weight
    coil = np.sin(2*np.pi*102*t) + .28*np.sin(2*np.pi*204*t)
    a += coil * (1-np.exp(-t/.008)) * np.exp(-t/.14) * .055
    # Reflections lose brightness as they recede, instead of duplicating the
    # same sharp crack into a metallic machine-gun pattern.
    dry = a.copy()
    dull = sosfilt(butter(2, 1500, fs=SR, output='sos'), dry)
    for delay, weight in ((.073,.16),(.179,.10),(.337,.065),(.563,.03)):
        k=round(delay*SR)
        a[k:] += dull[:-k]*weight
    return finish(a)


def friction(seed):
    rng=np.random.default_rng(seed)
    duration=.74
    t=np.arange(round(SR*duration))/SR
    attack=np.sin(.5*np.pi*np.clip(t/.055,0,1))**2
    release=np.sin(.5*np.pi*np.clip((duration-t)/.15,0,1))**2
    envelope=attack*release
    # Twelve-tick emission cadence is 0.6 s. These longer, tapered contacts
    # overlap gently even at the highest ordinary playback pitch (1.1).
    a=filtered_noise(rng,len(t),100,650)*.15
    a+=filtered_noise(rng,len(t),450,3100)*.12
    roughness=.78+.14*np.sin(2*np.pi*17.3*t+rng.uniform(0,6.28))
    roughness+=.08*np.sin(2*np.pi*41.7*t+rng.uniform(0,6.28))
    a*=roughness
    for frequency, weight in ((482,.026),(817,.020),(1391,.011)):
        phase=2*np.pi*frequency*t+rng.uniform(0,2*np.pi)
        a += np.sin(phase+.21*np.sin(2*np.pi*6.1*t))*weight
    for delay in rng.uniform(.05,.65,9):
        dt=np.maximum(0,t-delay)
        a+=filtered_noise(rng,len(t),1500,6200)*np.exp(-dt/.0025)*(t>=delay)*.028
    # Do not peak-normalize rail friction to the launch impact's level.
    return finish(a*envelope,peak=.34)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--ffmpeg',required=True)
    ap.add_argument('--assets',type=Path,default=ROOT/'src/main/resources/assets/projectseele')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    assets=args.assets
    (assets/'sounds').mkdir(parents=True,exist_ok=True)
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
        records.append(dict(asset='assets/projectseele/sounds/'+dest.name,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
            seconds=len(signal)/SR,decoded_peak=float(max(abs(samples))),decoded_rms=float(np.sqrt(np.mean(samples**2))),
            source='Original deterministic mathematical synthesis; no sampled recording',channels=1,sample_rate=SR))
    p=assets/'sounds.json';catalog=json.loads(p.read_text('utf8')) if p.exists() else {}
    for event,names in {'launch_electric_burst_r53':['launch_electric_burst_r53'],
                        'launch_rail_friction_r53':[f'launch_rail_friction_r53_{i}' for i in range(3)]}.items():
        distance=192 if event=='launch_electric_burst_r53' else 128
        existing={s['name']:s for s in catalog.get(event,{}).get('sounds',[]) if isinstance(s,dict)}
        catalog[event]={**catalog.get(event,{}),'subtitle':'subtitles.projectseele.'+event,
                        'sounds':[{**existing.get('projectseele:'+n,{}),'name':'projectseele:'+n,
                                   'stream':False,'attenuation_distance':distance} for n in names]}
    p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n','utf8')
    for lang,labels in {'zh_cn':['发射轨道：电流爆发','发射轨道：高速摩擦'],
                        'en_us':['Launch rails discharge','Launch rails spark and scrape']}.items():
        p=assets/'lang'/(lang+'.json');p.parent.mkdir(exist_ok=True)
        data=json.loads(p.read_text('utf8')) if p.exists() else {}
        for key,label in zip(('launch_electric_burst_r53','launch_rail_friction_r53'),labels):data['subtitles.projectseele.'+key]=label
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
    receipt=dict(generator=str(Path(__file__).resolve().relative_to(ROOT)),revision='2026-10-20',
                 assets=records,listening='Pending in-game positional mix and user listening')
    (args.out/'AUDIO_SYNTHESIS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    provenance=assets/'audio/launch_feedback_r53.json';provenance.parent.mkdir(exist_ok=True)
    provenance.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
