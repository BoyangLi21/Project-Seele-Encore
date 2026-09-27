"""Encode actual timed native frames and WASAPI game audio at normal speed."""
from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/world_combat_r40';OUT=ART/'delivery_media'


def encode(runfile,title):
    run=json.loads(runfile.read_text());media=Path(run['media'])
    if not media.is_absolute():media=(ROOT/'run'/media).resolve()
    evidence=media/'client_evidence.json';data=json.loads(evidence.read_text());assert not data['server_failure']
    frames=data['frames'];audio=Path(run['audio']);audio=audio if audio.is_absolute() else ROOT/audio
    record=json.loads(audio.with_suffix('.capture.json').read_text());offset=frames[0]['capture_epoch_ms']/1000-record['start_epoch_seconds'];assert offset>=0
    lines=['ffconcat version 1.0'];seconds=0
    for i,row in enumerate(frames):
        delta=frames[i+1]['render_elapsed_seconds']-row['render_elapsed_seconds'] if i+1<len(frames) else 1/24
        assert delta>0;seconds+=delta
        lines.extend(["file '"+(media/row['file']).as_posix()+"'",'option framerate 1000',f'duration {delta:.9f}'])
    lines.extend(["file '"+(media/frames[-1]['file']).as_posix()+"'",'option framerate 1000'])
    concat=OUT/(title+'.ffconcat');concat.write_text('\n'.join(lines)+'\n')
    movie=OUT/(title+'.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(concat),'-ss',str(offset),'-i',str(audio),
                    '-map','0:v:0','-map','1:a:0','-t',str(seconds),'-c:v','libx264','-preset','medium','-crf','19','-threads','2','-pix_fmt','yuv420p',
                    '-fps_mode','vfr','-video_track_timescale','90000','-c:a','aac','-b:a','192k','-movflags','+faststart',str(movie)],check=True)
    receipt=dict(source_media=str(media),frames=len(frames),seconds=seconds,normal_speed=True,synthetic_frames=False,
                 audio='Unreplaced selected-speaker WASAPI recording; capture reported discontinuities, not a claim of final listening acceptance',
                 audio_offset_seconds=offset,sha256=hashlib.sha256(movie.read_bytes()).hexdigest())
    movie.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print(movie,flush=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    encode(ART/'phrase_candidate/candidate_run.json','R40_Normal_Attacks_and_Duel')
    encode(ART/'envelopment_native_final/run.json','R40_Awakening_and_Sachiel_Finale')


if __name__=='__main__':main()
