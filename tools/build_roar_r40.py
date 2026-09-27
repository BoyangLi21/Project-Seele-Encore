"""Replace the oscillator-era roar with one CC0 performed vocal take."""
import json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/world_combat_r40/audio';ASSETS=ROOT/'src/main/resources/assets/projectseele'

def main():
    source=ART/'roar_cc0_source.mp3';provenance=json.loads((ART/'source.json').read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest()!=provenance['sha256']:raise RuntimeError('Source changed')
    target=ASSETS/'sounds/eva_berserk_performed_r40.ogg'
    # Preserve the performed attack and breath, with a modest size shift and
    # restrained upper rasp. No looping, oscillator or added synthetic scream.
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-ac','1','-af',
        'asetrate=44100*0.88,aresample=48000,highpass=f=48,lowpass=f=7000,acompressor=threshold=0.25:ratio=2:attack=8:release=110:makeup=1.25,afade=t=in:d=0.009,afade=t=out:st=1.94:d=0.18,alimiter=limit=0.88:level=false',
        '-c:a','libvorbis','-q:a','7',str(target)],check=True)
    path=ASSETS/'sounds.json';sounds=json.loads(path.read_text(encoding='utf8'))
    sounds['eva_berserk_roar']={'subtitle':'subtitles.projectseele.eva_berserk_roar','sounds':[{'name':'projectseele:eva_berserk_performed_r40','attenuation_distance':384,'stream':False}]}
    path.write_text(json.dumps(sounds,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    provenance.update(output=str(target.relative_to(ROOT)),output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),processing='0.88 resample pitch, 48–7000 Hz passband, mild compression and end fades',auditory_acceptance='No audio-inspection tool available; performed source and file integrity verified, subjective likeness is not certified.')
    (ART/'manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf8')
    print(target)
if __name__=='__main__':main()
