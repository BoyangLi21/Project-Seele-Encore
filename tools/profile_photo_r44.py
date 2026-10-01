"""Attach a short JFR to the exact child PID after a fixed review view is ready."""
from pathlib import Path
import json
import shutil
import subprocess
import time
from launch_rendered_client_r17 import java_environment


def run(spec, out, stream, world):
    command=spec['command']
    args=out/'profile_launch.args'
    args.write_text('\n'.join('"'+s.replace('\\','\\\\').replace('"','\\"')+'"' for s in command[1:]),'utf8')
    env=java_environment()[1];env.update(spec['environment'])
    ready=world/'station_photo_ready.json';began=time.time();attached=False;attempted=False;attach_error=None
    gpu_tool=shutil.which('nvidia-smi');gpu_started=None;gpu_samples=[];last_gpu_sample=0
    process=subprocess.Popen([command[0],'@'+str(args.resolve())],cwd=spec['workingDirectory'],env=env,
                             stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'profile_process.json').write_text(json.dumps(dict(pid=process.pid,launch=str(args.resolve()),
        java=command[0],world=str(world),view_count=1,preserves_requested_render_distance=True),indent=2),'utf8')
    while process.poll() is None:
        if not attempted and ready.exists() and ready.stat().st_mtime>=began:
            attempted=True
            executable=Path(command[0]).with_name('jcmd.exe')
            jfr=out/'stable_view_20s.jfr'
            try:
                result=subprocess.run([str(executable),str(process.pid),'JFR.start','name=R44StablePhoto',
                    'settings=profile','duration=20s','filename='+str(jfr.resolve())],capture_output=True,text=True,timeout=20)
                (out/'jfr_attach.txt').write_text(result.stdout+result.stderr,'utf8')
                attached=result.returncode==0
                if attached:gpu_started=time.time()
                if not attached:attach_error='Exact review PID rejected JFR'
            except (OSError,subprocess.TimeoutExpired) as error:
                attach_error=repr(error)
                (out/'jfr_attach_failure.txt').write_text(attach_error,'utf8')
        if gpu_tool and gpu_started is not None and time.time()-gpu_started<22 and time.time()-last_gpu_sample>=1:
            last_gpu_sample=time.time()
            try:
                result=subprocess.run([gpu_tool,'--query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total',
                    '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4,creationflags=subprocess.CREATE_NO_WINDOW)
                gpu_samples.append(dict(wall_epoch=last_gpu_sample,return_code=result.returncode,csv=result.stdout.strip(),error=result.stderr.strip()))
            except (OSError,subprocess.TimeoutExpired) as error:
                gpu_samples.append(dict(wall_epoch=last_gpu_sample,error=repr(error)))
        # The native fixture owns graceful timeout/position and option restoration.
        # A failed attach must not target some later process with a reused PID.
        time.sleep(.5)
    (out/'gpu_samples.json').write_text(json.dumps(dict(tool=gpu_tool,samples=gpu_samples,
        fields=['timestamp','name','utilization.gpu','utilization.memory','memory.used MiB','memory.total MiB'],
        limit='Adapter-wide samples include any other GPU users; not a per-draw GPU timing or an exclusive Minecraft measurement'),indent=2),'utf8')
    if process.returncode!=0:raise RuntimeError('Native profile client exited '+str(process.returncode))
    if attach_error:raise RuntimeError(attach_error)
    if not attached or not (out/'stable_view_20s.jfr').is_file():
        raise RuntimeError('No completed stable-camera JFR; not a performance pass')
