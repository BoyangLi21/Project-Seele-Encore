"""Normal-speed native A/B with the recorded WASAPI soundtrack and timestamps."""
from pathlib import Path
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/world_combat_r40/contact_candidate'


def main():
    runs=json.loads((OUT/'side_runs.json').read_text())
    assert len(runs)==2,'Both baseline and candidate must have finished'
    for run in runs:
        media=ROOT/run['media'];evidence=media/'client_evidence.json'
        data=json.loads(evidence.read_text());assert not data['server_failure']
        frames=data['frames'];assert len(frames)>50
        audio=ROOT/run['audio'];meta=json.loads(audio.with_suffix('.capture.json').read_text())
        offset=frames[0]['capture_epoch_ms']/1000-meta['start_epoch_seconds']
        assert offset>=0 and meta['peak']>.001,(offset,meta)
        lines=['ffconcat version 1.0'];duration=0
        for i,row in enumerate(frames):
            dt=frames[i+1]['render_elapsed_seconds']-row['render_elapsed_seconds'] if i+1<len(frames) else 1/24
            assert dt>0
            duration+=dt
            lines.extend(["file '"+(media/row['file']).as_posix()+"'",'option framerate 1000','duration '+format(dt,'.9f')])
        lines.extend(["file '"+(media/frames[-1]['file']).as_posix()+"'",'option framerate 1000'])
        concat=OUT/(run['label']+'_side.ffconcat');concat.write_text('\n'.join(lines)+'\n')
        movie=OUT/('R40_Normal_'+run['label']+'.mp4')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(concat),
            '-ss',str(offset),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-t',str(duration),
            '-c:v','libx264','-preset','medium','-crf','20','-threads','2','-pix_fmt','yuv420p','-fps_mode','vfr',
            '-video_track_timescale','90000','-c:a','aac','-b:a','192k','-movflags','+faststart',str(movie)],check=True)
        receipt={'native_media':str(media),'frames':len(frames),'duration_seconds':duration,'audio':str(audio),
                 'audio_offset_seconds':offset,'audio_alignment':'System epoch plus 20ms capture block / endpoint buffering',
                 'synthetic_frames':False,'playback_speed':1,'test':'Scripted production inputs; empty/contact/heavy/moving scenarios; not autonomous AI duel',
                 'evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest(),'video_sha256':hashlib.sha256(movie.read_bytes()).hexdigest()}
        movie.with_suffix('.json').write_text(json.dumps(receipt,indent=2))
        print(movie,round(movie.stat().st_size/1e6,2),'MB',flush=True)


if __name__=='__main__':main()
