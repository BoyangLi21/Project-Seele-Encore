"""Frozen R45 spoken announcements and a CC0 recorded industrial warning."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];ASSET=ROOT/'src/main/resources/assets/projectseele';OUT=ROOT/'artifacts/rebuild_r45/audio/installation';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'artifacts/rebuild_r45/audio/facility/ja';rows=json.loads((source/'sources.json').read_text('utf8'));backup=OUT/'source_before';backup.mkdir(exist_ok=True);receipt=[]
for r in rows:
 p=source/(r['name']+'.ogg');assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
 target=ASSET/'sounds'/p.name
 if not(backup/p.name).exists():shutil.copy2(target,backup/p.name)
 shutil.copy2(p,target);receipt.append(dict(name=p.name,sha256=r['sha256'],seconds=r['seconds'],language='Japanese facility voice; Chinese subtitles retained'))
(ASSET/'audio').mkdir(exist_ok=True);(ASSET/'audio/facility_voice_r45.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
# The primary source is a real crane warning buzzer, rather than a swept voice tone.
raw=ROOT/'artifacts/rebuild_r45/audio/alarm_candidates/factory_crane_buzzer.mp3';src=json.loads((raw.parent/'sources.json').read_text('utf8'))[0];assert hashlib.sha256(raw.read_bytes()).hexdigest()==src['sha256']
target=ASSET/'sounds/facility_siren.ogg'
if not(backup/target.name).exists():shutil.copy2(target,backup/target.name)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-t','2.7','-af','afade=t=in:d=0.04,afade=t=out:st=2.58:d=0.12,highpass=f=140,lowpass=f=6000,loudnorm=I=-20:TP=-3:LRA=6','-ar','48000','-ac','1','-c:a','libvorbis','-q:a','6',str(target)],check=True)
receipt.append(dict(name=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),source=src['page'],license='CC0',kind='Actual industrial crane warning buzzer'))
(OUT/'installed.json').write_text(json.dumps(dict(files=receipt,character_voice=False,TV_audio_extracted=False,native_sequence='PENDING',language_assumption='User preference optional question unanswered; TV-oriented Japanese facility PA with Chinese subtitles'),ensure_ascii=False,indent=2),'utf8');print('Installed facility PA',len(rows),'+ real industrial warning; native sequence pending')
