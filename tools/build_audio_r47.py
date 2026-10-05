"""R47 source-derived audio; no anime media, character voices or world writes."""
from pathlib import Path
import json, math, re, subprocess
import requests
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve, resample_poly

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'src/main/resources/assets/projectseele'
OUT = ROOT / 'artifacts/rebuild_r47/audio_staff/audio'
RATE = 48000

def read(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-ar', str(RATE), '-ac', '1', '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').astype(float)

def band(a, low, high):
    return sosfilt(butter(2, [low, high], btype='bandpass', fs=RATE, output='sos'), a)

def norm(a, peak=.83):
    a = a - a.mean()
    return a * peak / max(1e-6, abs(a).max())

def write(name, a, loop=False):
    if not loop:
        n = min(240, len(a)); a[:n] *= np.linspace(0, 1, n)
        n = min(2400, len(a)); a[-n:] *= np.linspace(1, 0, n)
    target = ASSET / 'sounds' / (name + '.ogg')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(RATE), '-ac', '1', '-i', '-', '-c:a', 'libvorbis', '-q:a', '7', str(target)], input=a.astype('<f4').tobytes(), check=True)
    return dict(name=name, seconds=len(a)/RATE, minimum_sequence_ticks=math.ceil(len(a)/RATE*20)+6, peak=float(abs(a).max()))

def fetch(author, number):
    folder = OUT / 'sources'; folder.mkdir(parents=True, exist_ok=True)
    url = f'https://freesound.org/people/{author}/sounds/{number}/'
    page = folder / f'{number}.html'
    if not page.exists():
        r = requests.get(url, timeout=40); r.raise_for_status(); page.write_text(r.text, encoding='utf8')
    html = page.read_text('utf8')
    if 'creativecommons.org/publicdomain/zero/1.0/' not in html:
        raise ValueError('CC0 not present in retained primary source page: ' + url)
    media = re.findall(r'https://[^\s\"<>]+?-hq\.mp3', html)[0]
    path = folder / f'{number}.mp3'
    if not path.exists():
        r = requests.get(media, timeout=60); r.raise_for_status(); path.write_bytes(r.content)
    return path, dict(author=author, page=url, preview=media, license='CC0 1.0', source_file=str(path.relative_to(ROOT)))

def seam(a, seconds=8):
    a = a[:round(seconds*RATE)].copy()
    n = round(.4*RATE)
    blend = np.linspace(0, 1, n)
    a[:n] = a[-n:]*(1-blend) + a[:n]*blend
    return a[:-n]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Freeze the original catalogue once; regeneration must not process its own derivatives.
    original_events = json.loads((OUT/'sounds.before.json').read_text('utf8'))
    events = json.loads((ASSET/'sounds.json').read_text('utf8'))
    rows=[]; sources=[]
    # Stronger room response: direct speech remains the loudest component.
    tail=2.6; rng=np.random.default_rng(4705); ir=np.zeros(round(tail*RATE)); ir[0]=1
    for delay,gain in [(0.078,.30),(.147,.22),(.233,.16),(.341,.12),(.487,.085)]:
        ir[round(delay*RATE)]+=gain
    diffuse=band(rng.standard_normal(len(ir)),240,4500)
    t=np.arange(len(ir))/RATE
    diffuse*=np.exp(-t*6.91/2.15)*(1-np.exp(-np.maximum(t-.08,0)*12))
    diffuse[t<.08]=0
    diffuse *= .45/max(1e-8,np.linalg.norm(diffuse))
    ir+=diffuse
    previous=json.loads((ASSET/'audio/hangar_pa_reverb_r46.json').read_text('utf8'))
    hangar=[]
    for row in previous:
        name=row['name']; original=name.removeprefix('hangar_').removesuffix('_r46')
        dry=read(ASSET/'sounds'/f'{original}.ogg')
        room=fftconvolve(dry,ir)
        output=write(name,norm(room,.72)); hangar.append(output); rows.append(output)
    (ASSET/'audio/hangar_pa_reverb_r46.json').write_text(json.dumps(hangar,indent=2)+'\n','utf8')
    # Recorded jet whine and valve/pump sounds, with retained CC0 pages.
    jet_path,jet_source=fetch('C-V','704945'); sources.append(jet_source)
    pump_path,pump_source=fetch('kr15h','689263'); sources.append(pump_source)
    jet=band(read(jet_path),38,10500)
    # Select a stable engine-running interval from the field recording.
    spans=[jet[i*RATE:(i+8)*RATE] for i in range(10,min(135,int(len(jet)/RATE)-8),8)]
    active=max(spans,key=lambda a: np.sqrt(np.mean(a*a)))
    engine=norm(seam(active),.77)
    rows.append(write('transport_engine_r47',engine,True))
    pump=band(read(pump_path),60,9000)
    steel=read(ROOT/'artifacts/combat_direction_r36/audio_sources/337832.mp3')
    container=read(ROOT/'artifacts/combat_direction_r36/audio_sources/569413.mp3')
    def clip_peak(a, seconds):
        i=max(0,int(np.argmax(abs(a)))-round(.015*RATE)); return a[i:i+round(seconds*RATE)]
    latch=norm(clip_peak(steel,.46)); mass=norm(band(clip_peak(container,1.2),38,450))
    pump=norm(pump)
    for event,seconds in [('facility_hydraulic',2),('facility_hydraulic_launch',2),('facility_rail_motion',2),('facility_catapult',3)]:
        n=round(seconds*RATE); a=np.resize(pump,n)*.72
        if event=='facility_rail_motion':
            a=norm(band(np.resize(container,n),45,2200))*.65 + a*.32
        if event in ('facility_catapult','facility_hydraulic_launch'):
            a+=np.resize(engine,n)*np.linspace(.12,.55,n)
            m=min(n,len(mass)); a[:m]+=mass[:m]*.65
        name=event+'_r47'; rows.append(write(name,norm(a,.84)))
        events[event]['sounds']=[dict(name='projectseele:'+name,attenuation_distance=256)]
    rows.append(write('personnel_door_open_r47',norm(latch,.65)))
    rows.append(write('personnel_door_close_r47',norm(np.concatenate([latch[:round(.18*RATE)]*.35,latch]),.70)))
    # Kneeling/loading has a lower structural body beneath the existing recorded strain.
    load_mass=norm(band(container[:round(1.2*RATE)],38,450))
    joint=[]
    for index,sound in enumerate(original_events['eva_joint_load']['sounds']):
        original=sound['name'].split(':',1)[1]
        load=read(ASSET/'sounds'/f'{original}.ogg')
        n=max(len(load),round(.42*RATE)); out=np.zeros(n)
        out[:len(load)]+=load*.65
        out[:min(n,len(load_mass))]+=load_mass[:min(n,len(load_mass))]*.27
        name=f'eva_joint_load_r47_{index}'; rows.append(write(name,norm(out,.57)))
        joint.append(dict(name='projectseele:'+name,attenuation_distance=192))
    events['eva_joint_load']['sounds']=joint
    # Preserve actual contact transients; increase low structural body and brief decay.
    for event in ('eva_foot_concrete','eva_foot_soil','eva_land','eva_rifle_fire','eva_impact','eva_impact_heavy'):
        new=[]
        for index,sound in enumerate(original_events[event]['sounds']):
            original=sound['name'].split(':',1)[1]; a=read(ASSET/'sounds'/f'{original}.ogg')
            body=band(a,38,260); tail=fftconvolve(body,np.exp(-np.arange(round(.24*RATE))/RATE*24)) / 120
            out=np.pad(a,(0,max(0,len(tail)-len(a))))
            out[:len(tail)]+=tail*(.55 if event!='eva_rifle_fire' else .33)
            name=f'{event}_r47_{index}'; rows.append(write(name,norm(out,.86)))
            new.append(dict(name='projectseele:'+name,attenuation_distance=384))
        events[event]['sounds']=new
    roar=read(ASSET/'sounds/eva_berserk_performed_r40.ogg')
    short=roar[:round(1.05*RATE)].copy()
    rows.append(write('eva_attack_roar_r47',norm(band(short,48,7800),.86)))
    events['eva_attack_roar']=dict(subtitle='subtitles.projectseele.eva_attack_roar',sounds=[dict(name='projectseele:eva_attack_roar_r47',attenuation_distance=384)])
    for event in ('transport_engine','personnel_door_open','personnel_door_close'):
        events[event]=dict(subtitle='subtitles.projectseele.'+event,sounds=[dict(name='projectseele:'+event+'_r47',attenuation_distance=256)])
    movement=read(ASSET/'sounds/facility_rail_motion_r47.ogg')[:round(.66*RATE)].copy()
    rows.append(write('pressure_door_motion_r47',norm(movement,.70)))
    events['pressure_door_motion']=dict(subtitle='subtitles.projectseele.pressure_door_motion',sounds=[dict(name='projectseele:pressure_door_motion_r47',attenuation_distance=48)])
    (ASSET/'sounds.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n','utf8')
    (OUT/'manifest.json').write_text(json.dumps(dict(new_sources=sources,existing_sources=['R36 registered CC0 steel/container/stone/soil field recordings','R40 colorsCrimsonTears performed monster roar CC0','R45 original Japanese facility wording / standard neural facility voice'],outputs=rows,hangar=dict(tail_seconds=2.6,early_reflections=[.078,.147,.233,.341,.487],direct_to_reverberant_energy_db=float(10*np.log10(1/np.sum(ir[1:]**2)))),world_written=False,character_voice=False,auditory_acceptance='Pending user listening; only asset derivation and finite peak metrics recorded'),ensure_ascii=False,indent=2)+'\n','utf8')
    print('R47 audio assets:',len(rows),'PA clips:',len(hangar))

if __name__=='__main__': main()
