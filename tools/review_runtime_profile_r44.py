"""Same-room A/B with actual loaded vehicles, server tick times and JFR sampling."""
from pathlib import Path
import argparse,json,subprocess,time
from release_combat_r36 import guard
from launch_rendered_client_r17 import java_environment
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';ART=ROOT/'artifacts/rebuild_r44'

def run(legacy):
    guard();out=ART/'runtime_profile'/('legacy' if legacy else 'idle_ticket_fix')/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.r44RuntimeProfileReview=true']+(['-Dprojectseele.keepIdleVehicleTickets=true'] if legacy else [])
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command;spec=freeze(spec,out)
    (out/'launch.json').write_text(json.dumps(spec),'utf8')
    argfile=out/'launch.args';argfile.write_text('\n'.join('"'+s.replace('\\','\\\\').replace('"','\\"')+'"' for s in command[1:]),'utf8')
    backups={p:p.read_bytes() for p in (ROOT/'run/options.txt',ROOT/'run/config/oculus.properties') if p.exists()}
    for p,content in backups.items():
        rules={'renderDistance:':'renderDistance:6','simulationDistance:':'simulationDistance:5','pauseOnLostFocus:':'pauseOnLostFocus:false','enableShaders=':'enableShaders=false'}
        p.write_text('\n'.join(next((value for key,value in rules.items() if line.startswith(key)),line) for line in content.decode('utf8').splitlines())+'\n','utf8')
    ready=WORLD/'r44_runtime_profile_ready.json';result=WORLD/'r44_runtime_profile.json'
    for p in (ready,result):
        if p.exists():p.unlink()
    env=java_environment()[1];env.update(spec['environment']);began=time.time();recorded=False
    try:
        with (out/'client.log').open('w',encoding='utf8') as stream:
            process=subprocess.Popen([command[0],'@'+str(argfile.resolve())],cwd=spec['workingDirectory'],env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            while process.poll() is None:
                if ready.exists() and not recorded:
                    jfr=out/'native_20s.jfr';jcmd=Path(command[0]).with_name('jcmd.exe')
                    response=subprocess.run([str(jcmd),str(process.pid),'JFR.start','name=R44Runtime','settings=profile','duration=20s','filename='+str(jfr.resolve())],capture_output=True,text=True)
                    (out/'jfr_attach.txt').write_text(response.stdout+response.stderr,'utf8');assert response.returncode==0;recorded=True
                if time.time()-began>600:process.terminate();raise TimeoutError('Runtime profile fixture failed to close')
                time.sleep(1)
        assert process.returncode==0 and recorded and result.exists()
        proof=json.loads(result.read_text('utf8'));samples=proof['samples'];times=sorted(r['server_tick_ms'] for r in samples)
        proof['summary']=dict(samples=len(times),median_tick_ms=times[len(times)//2],p95_tick_ms=times[int(len(times)*.95)],loaded_sbw_start=samples[0]['loaded_sbw_entities'],loaded_sbw_end=samples[-1]['loaded_sbw_entities'],tickets=samples[-1]['parking_tickets'])
        (out/'result.json').write_text(json.dumps(proof,indent=2),'utf8');print(out,proof['summary'],flush=True)
    finally:
        for p,content in backups.items():p.write_bytes(content)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--only',choices=('legacy','after'));args=p.parse_args()
    if args.only!='after':run(True)
    if args.only!='legacy':run(False)
