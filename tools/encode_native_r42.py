"""Encode the actual latest native frames at their recorded wall-clock times (silent)."""
from pathlib import Path
import hashlib,json,subprocess,shutil

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42';OUT=ART/'delivery_media'


def main():
    pointer=json.loads((ART/'native/latest_awakening_1_shader.json').read_text('utf8'));assert pointer['passed']
    media=(ROOT/'run'/pointer['media']).resolve();evidence=media/'client_evidence.json'
    data=json.loads(evidence.read_text('utf8'));assert not data['server_failure'] and not data['capture_write_failure']
    rows=data['frames'];assert len(rows)>100;OUT.mkdir(exist_ok=True)
    lines=['ffconcat version 1.0'];duration=0
    for i,row in enumerate(rows):
        dt=rows[i+1]['render_elapsed_seconds']-row['render_elapsed_seconds'] if i+1<len(rows) else 1/24
        assert dt>0;duration+=dt
        lines.extend(["file '"+(media/row['file']).as_posix()+"'",'option framerate 1000',f'duration {dt:.9f}'])
    lines.extend(["file '"+(media/rows[-1]['file']).as_posix()+"'",'option framerate 1000'])
    concat=OUT/'native_first_battle.ffconcat';concat.write_text('\n'.join(lines)+'\n','utf8')
    movie=OUT/'R42_FirstBattle_Silent_Native.mp4';ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(concat),
                    '-t',str(duration),'-an','-c:v','libx264','-preset','medium','-crf','20','-threads','2',
                    '-pix_fmt','yuv420p','-fps_mode','vfr','-video_track_timescale','90000','-movflags','+faststart',str(movie)],check=True)
    (OUT/'native_first_battle.json').write_text(json.dumps(dict(media=str(media),frames=len(rows),seconds=duration,
        playback_speed=1,synthetic_frames=False,audio=False,scope='Native test arena, actual natural awakening and paired scene; this capture does not contain game audio.',
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),video_sha256=hashlib.sha256(movie.read_bytes()).hexdigest()),indent=2),'utf8')
    print(movie,round(movie.stat().st_size/1e6,2),'MB',flush=True)


if __name__=='__main__':main()
