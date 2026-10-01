"""Encode exact native frames with their recorded wall-clock durations."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess

ap=argparse.ArgumentParser();ap.add_argument('--native',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
file=args.native/'client_evidence.json';evidence=json.loads(file.read_text('utf8'));assert not evidence['server_failure']and not evidence['capture_write_failure'];rows=evidence['frames'];ffmpeg=shutil.which('ffmpeg');assert ffmpeg;report=[]
for stage in sorted(set(r['stage']for r in rows)):
    group=[r for r in rows if r['stage']==stage];lines=['ffconcat version 1.0'];duration=0.
    for i,row in enumerate(group):
        delta=group[i+1]['render_elapsed_seconds']-row['render_elapsed_seconds']if i+1<len(group)else 1/24;assert delta>0
        duration+=delta;lines.extend(["file '"+(args.native/row['file']).resolve().as_posix()+"'",'option framerate 1000',f'duration {delta:.9f}'])
    lines.extend(["file '"+(args.native/group[-1]['file']).resolve().as_posix()+"'",'option framerate 1000']);concat=args.out/(stage+'.ffconcat');concat.write_text('\n'.join(lines)+'\n','utf8');movie=args.out/(stage+'.mp4')
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(concat),'-t',str(duration),'-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-pix_fmt','yuv420p','-fps_mode','vfr','-video_track_timescale','90000','-movflags','+faststart',str(movie)],check=True)
    report.append(dict(stage=stage,frames=len(group),duration_seconds=duration,path=str(movie.resolve()),sha256=hashlib.sha256(movie.read_bytes()).hexdigest()))
(args.out/'recorded_stage_movies.json').write_text(json.dumps(dict(source_evidence_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),movies=report,playback_speed=1,synthetic_frames=False,audio=False,actual_watched=False,scope='Native captured frame pixels and recorded render wall-clock times; no artistic pass or audio sync inferred.'),indent=2),'utf8');print(json.dumps(report,indent=2))
