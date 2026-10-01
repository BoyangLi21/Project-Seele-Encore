"""Make a labelled, unprocessed recording comparison; do not install candidates."""
from pathlib import Path
import json, subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/audio/source_audition'
RATE=24000


def decode(path):
    data=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar',str(RATE),'-f','f32le','-'])
    return np.frombuffer(data,dtype='<f4').copy()


def main():
    paths=[ROOT/'src/main/resources/assets/projectseele/sounds/eva_berserk_performed_r40.ogg']
    paths += [OUT/f'Scream {i}.wav' for i in range(1,6)]
    paths += [OUT/'Monster.wav']
    audio=[];timeline=[];time=0
    for path in paths:
        wave=decode(path);maximum=float(np.max(np.abs(wave)))
        length=min(len(wave),RATE*3)
        if len(wave)>length:
            # Keep the loudest full window, not a silent head or sliced phoneme.
            starts=range(0,len(wave)-length+1,RATE//10)
            start=max(starts,key=lambda s:float(np.mean(wave[s:s+length]**2)))
        else:start=0
        take=wave[start:start+length];peak=float(np.max(np.abs(take)))
        take=take*.70/max(peak,.001)
        audio.extend((take,np.zeros(RATE//2,dtype=np.float32)))
        timeline.append(dict(file=str(path),at=time,excerpt_start=start/RATE,duration=len(take)/RATE,
                             source_duration=len(wave)/RATE,source_peak=maximum))
        time+=len(take)/RATE+.5
    preview=OUT/'voice_source_comparison.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(RATE),'-ac','1','-i','-',
                    '-c:a','libmp3lame','-b:a','48k',str(preview)],input=np.concatenate(audio).astype('<f4').tobytes(),check=True)
    (OUT/'voice_source_timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),'utf8')
    print(preview,'seconds',round(time,2),flush=True)


if __name__=='__main__':main()
