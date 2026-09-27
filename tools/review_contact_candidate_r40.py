"""Native normal attacks plus an active Sachiel exchange; restore private profiles."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,sys
from launch_rendered_client_r17 import java_environment,run_prepared
from record_combat_pcm_r34 import capture

ROOT=Path(__file__).resolve().parents[1]


def main(candidate,variant=1):
    guard=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^javaw?\\.exe$' }).Count"],capture_output=True,text=True,check=True)
    assert int(guard.stdout.strip())==0,'Close the previous Minecraft/build JVM first'
    out=ROOT/'artifacts/world_combat_r40/phrase_candidate';out.mkdir(parents=True,exist_ok=True)
    label=('candidate' if candidate else 'baseline')+(f'_v{variant}' if variant!=1 else '');saved={}
    for name in [f'eva_gameplay_r32_{variant}.json','sachiel_gameplay_r32.json']:
        path=ROOT/'run/projectseele-local-maps'/name;saved[path]=path.read_bytes()
        assert saved[path]==(out/('baseline_'+name)).read_bytes(),('Private source differs',name)
    spec=json.loads((ROOT/'.Codex/client-r40-contact-side.json').read_text('utf8'))
    spec['command']=[f'-Dprojectseele.combatVariant={variant}' if s.startswith('-Dprojectseele.combatVariant=') else s for s in spec['command']]
    if variant!=1:spec['command']=[s for s in spec['command'] if not s.startswith('-Dprojectseele.combatVideo=')]
    spec['command'][1:1]=['-Dprojectseele.combatDuel=true']
    launch=ROOT/'.Codex/client-r40-phrases.json';launch.write_text(json.dumps(spec))
    log=out/(label+'_native.log');audio=out/(label+'_audio.wav');start=time.time()
    try:
        if candidate:
            for path in saved:path.write_bytes((out/path.name).read_bytes())
        with log.open('w',encoding='utf8') as stream,capture(audio if variant==1 else None,log):
            import contextlib
            # run_prepared inherits stdout; use an outer redirected Python
            # invocation so both JVM output and the audio start marker agree.
            result=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py',
                '--prepared-file',str(launch)],cwd=ROOT,env=java_environment()[1],stdout=stream,stderr=subprocess.STDOUT)
            assert result.returncode==0,result.returncode
        reports=list((ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob('r32_normal_*.json'))
        report=max(reports,key=lambda p:p.stat().st_mtime);assert report.stat().st_mtime>=start
        data=json.loads(report.read_text());(out/(label+'_result.json')).write_bytes(report.read_bytes())
        receipt=dict(start=start,end=time.time(),media=data['media'],audio=str(audio.relative_to(ROOT)),
                     profiles={p.name:hashlib.sha256((out/p.name).read_bytes() if candidate else b).hexdigest() for p,b in saved.items()})
        (out/(label+'_run.json')).write_text(json.dumps(receipt,indent=2))
        print(json.dumps(dict(report=str(report),media=data['media'],error=data['error'],cases=data['cases'])),flush=True)
    finally:
        for path,original in saved.items():path.write_bytes(original)
        assert all(p.read_bytes()==b for p,b in saved.items())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',action='store_true');p.add_argument('--variant',type=int,choices=range(5),default=1);args=p.parse_args();main(args.candidate,args.variant)
