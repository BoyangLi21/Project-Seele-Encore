"""One normal cold-load of the retained QA after city metadata extension; no gameplay input fabrication."""
from pathlib import Path
import json,subprocess,threading,time
from launch_rendered_client_r17 import java_environment

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r48'
OUT=BASE/'native_session/city_cold_03';GAME=BASE/'native_qa/game'

def main():
    if OUT.exists():raise ValueError('Keep earlier cold-loader evidence')
    OUT.mkdir();spec=json.loads((BASE/'native_session/actual_02/launch.json').read_text('utf8'))
    env=java_environment()[1];env.update(spec['environment']);env.pop('MOD_CLASSES',None)
    proc=subprocess.Popen(spec['command'],cwd=GAME,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
    rows=[]
    with (OUT/'server.log').open('x',encoding='utf8')as log:
        def reader():
            for line in proc.stdout:rows.append(line);log.write(line);log.flush()
        thread=threading.Thread(target=reader,daemon=True);thread.start();start=time.monotonic();loaded=False
        try:
            while proc.poll()is None and time.monotonic()-start<240:
                if any('Done ('in line for line in rows):loaded=True;break
                time.sleep(.5)
            if not loaded:raise RuntimeError('Current city release failed normal cold-load')
            proc.stdin.write('seele eva status\nseele eva dummy status\n');proc.stdin.flush();time.sleep(8)
        finally:
            if proc.poll()is None:
                proc.stdin.write('save-all flush\nstop\n');proc.stdin.flush()
            proc.wait(timeout=60);thread.join(timeout=5)
    errors=[s for i,s in enumerate(rows)if('ERROR'in s or 'Exception'in s)and any('projectseele'in v.lower()for v in rows[max(0,i-2):i+3])]
    result=dict(current_release_cold_loaded=loaded,exit=proc.returncode,all_dimensions_saved=any('All dimensions are saved'in s for s in rows),
        project_errors=errors,scope='Normal cold-load only; no real100 travel, console privilege extension, fake player, reset or source-world changes')
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    if proc.returncode!=0 or errors:raise RuntimeError('Current release cold-load contains project errors')
    print(result)

if __name__=='__main__':main()
