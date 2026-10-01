"""Encode real independent-client frames at their captured wall-clock speed."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);args=ap.parse_args()
    assert args.label.replace('_','').isalnum()
    folder=ROOT/'artifacts/rebuild_r44/network_runtime'/args.label
    source=Path(json.loads((folder/'media.json').read_text())['folder'])
    rows=json.loads((source/'frames.json').read_text());out=folder/'movies';out.mkdir(exist_ok=True)
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    reports=[]
    for rig in range(5):
        frames=[r for r in rows if r['variant']==rig];assert len(frames)>50
        script=['ffconcat version 1.0'];duration=0;fingerprint=hashlib.sha256()
        for index,row in enumerate(frames):
            image=source/row['file'];assert image.exists()
            dt=(frames[index+1]['wall_ns']-row['wall_ns'])/1e9 if index+1<len(frames) else 1/row['fps']
            assert 0<dt<2,(rig,index,dt)
            duration+=dt;fingerprint.update(image.read_bytes())
            script.extend(["file '"+image.as_posix()+"'",'option framerate 1000','duration '+format(dt,'.9f')])
        script.extend(["file '"+(source/frames[-1]['file']).as_posix()+"'",'option framerate 1000'])
        listing=out/f'rig_{rig}.ffconcat';listing.write_text('\n'.join(script)+'\n','utf8')
        movie=out/f'R44_rig_{rig}_actual_network.mp4'
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(listing),
            '-an','-c:v','libx264','-preset','fast','-crf','21','-threads','2','-pix_fmt','yuv420p',
            '-fps_mode','vfr','-video_track_timescale','90000','-movflags','+faststart',str(movie)],check=True)
        reports.append(dict(rig=rig,video=str(movie),frames=len(frames),duration_seconds=duration,
            captured_frames_sha256=fingerprint.hexdigest(),video_sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),
            capture='Actual separate server/client process, normal entity, actual key inputs',
            speed=1,synthetic_frames=False,audio='Not captured in this diagnostic; silent clip',
            artistic_acceptance=False))
        print('Encoded actual rig',rig,round(duration,2),'seconds',flush=True)
    (out/'manifest.json').write_text(json.dumps(reports,indent=2),'utf8')


if __name__=='__main__':main()
