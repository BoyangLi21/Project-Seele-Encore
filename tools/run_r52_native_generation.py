"""One hidden dedicated-server session for explicit unfinished chunk targets."""
import json,subprocess,threading,queue,time,hashlib,argparse
from pathlib import Path
from query_blocks import chunk_statuses
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--job-root',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();out=args.job_root.resolve()
    assert out.is_relative_to((base/'native_generation').resolve())
    spec=json.loads((out/'STAGED.json').read_text('utf8'));host=Path(spec['host']);fixture=Path(spec['fixture'])
    assert fixture.resolve()==(base/'native_generation/server/CURRENT_TERRAIN_ONLY').resolve()
    assert host.resolve()==fixture.parent.resolve() and spec.get('generation_only') is True
    assert not(out/'RUN_RESULT.json').exists(),'Keep completed generation evidence; do not restart blindly'
    assert hashlib.sha256((host/'mods/projectseele-0.1.0-all.jar').read_bytes()).hexdigest()==spec['mod_sha256']
    java='C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'
    command=[java,'@generation_jvm_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui']
    child=subprocess.Popen(command,cwd=host,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'RUNNING.json').write_text(json.dumps(dict(pid=child.pid,fixture=str(fixture),source_world_opened=False)),'utf8')
    events=queue.Queue()
    def consume():
        for line in child.stdout:events.put(line)
        events.put(None)
    threading.Thread(target=consume,daemon=True).start()
    def send(command):child.stdin.write(command+'\n');child.stdin.flush()
    target=[(r['x'],r['z'])for r in spec['targets']];batches=[target[i:i+96]for i in range(0,len(target),96)]
    started=time.monotonic();ready=False;batch=-1;phase='boot';next_check=0;batch_started=0;complete=[];failure=None;stop_at=None
    def begin_batch():
        nonlocal batch,phase,next_check,batch_started,stop_at
        batch+=1
        if batch==len(batches):send('save-all flush');send('stop');phase='stopping';stop_at=time.monotonic();return
        for x,z in batches[batch]:send(f'execute in projectseele:geofront run forceload add {x*16} {z*16}')
        batch_started=time.monotonic();next_check=batch_started+10;phase='generating';print(f'Native generation batch {batch+1}/{len(batches)}: {len(batches[batch])} chunks',flush=True)
    try:
        with(out/'server.log').open('w',encoding='utf8')as log:
            while child.poll()is None:
                try:line=events.get(timeout=.3)
                except queue.Empty:line=''
                if line is None:break
                if line:
                    log.write(line);log.flush()
                    if 'Done ('in line and not ready:
                        ready=True;send('gamerule doMobSpawning false');send('gamerule doDaylightCycle false');send('gamerule doWeatherCycle false');begin_batch()
                    if 'Saved the game'in line and phase=='saving':
                        actual=chunk_statuses(fixture,'projectseele:geofront',batches[batch]);missing={str(k):v for k,v in actual.items()if v!='full'}
                        if not missing:
                            for x,z in batches[batch]:send(f'execute in projectseele:geofront run forceload remove {x*16} {z*16}')
                            complete.extend(batches[batch]);print(f'Native FULL readback {len(complete)}/{len(target)}',flush=True);begin_batch()
                        else:
                            phase='generating';next_check=time.monotonic()+10
                            if time.monotonic()-batch_started>180:raise RuntimeError(('Native chunk completion deadline',missing))
                    if 'Exception in server tick loop'in line or 'OutOfMemoryError'in line:raise RuntimeError(line.strip())
                now=time.monotonic()
                if phase=='generating'and now>=next_check:send('save-all flush');phase='saving'
                if now-started>1500:raise TimeoutError('Bounded native generation deadline')
                if stop_at is not None and now-stop_at>90:raise TimeoutError('Native shutdown deadline')
            exit_code=child.wait(timeout=90)
    except BaseException as error:
        failure=repr(error)
        if child.poll()is None:
            try:send('save-all flush');send('stop');child.wait(timeout=90)
            except Exception:child.terminate();child.wait(timeout=20)
        exit_code=child.returncode
    final=chunk_statuses(fixture,'projectseele:geofront',target)
    report=dict(exit_code=exit_code,error=failure,passed=failure is None and exit_code==0 and set(final.values())=={'full'},
                elapsed_seconds=time.monotonic()-started,targets=len(target),full=sum(s=='full'for s in final.values()),
                generated_in_fixture_only=True,world_written=False,mod_sha256=spec['mod_sha256'])
    (out/'RUN_RESULT.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    assert report['passed'],report


if __name__=='__main__':main()
