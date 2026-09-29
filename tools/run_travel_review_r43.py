"""Exercise production travel commands in a disposable copy of the delivery world."""
from pathlib import Path
import datetime,json,shutil,subprocess,sys
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/repair_r43/travel_commands'
WORLD='SEELE_R43_TRAVEL_REVIEW'

def main():
    guard();OUT.mkdir(parents=True,exist_ok=True)
    target=ROOT/'run/saves'/WORLD
    if target.exists():
        assert '--retry' in sys.argv,'Review fixture already exists; inspect before retrying'
        assert target.resolve().parent==(ROOT/'run/saves').resolve() and target.name==WORLD
        assert not target.is_junction() and not target.is_symlink()
        previous=OUT/('attempt_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));previous.mkdir()
        for name in ('client.log','result.json'):
            if (OUT/name).exists():shutil.copy2(OUT/name,previous/name)
        shutil.rmtree(target)
    shutil.copytree(ROOT/'artifacts/server-ready-r43-stage/stage/world',target,ignore=shutil.ignore_patterns('session.lock'))
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command.insert(1,'-Dprojectseele.travelReview=true')
    command[command.index('--quickPlaySingleplayer')+1]=WORLD
    spec['command']=command
    prepared=ROOT/'.Codex/client-r43-travel.json';prepared.write_text(json.dumps(spec),'utf8')
    settings=[ROOT/'run/options.txt',ROOT/'run/config/oculus.properties']
    backups={p:p.read_bytes() for p in settings if p.exists()}
    for p,content in backups.items():
        (OUT/(p.name+'.before')).write_bytes(content)
        lines=content.decode('utf8').splitlines()
        replacements={'renderDistance:':'renderDistance:6','simulationDistance:':'simulationDistance:5','pauseOnLostFocus:':'pauseOnLostFocus:false','enableShaders=':'enableShaders=false'}
        lines=[next((v for k,v in replacements.items() if line.startswith(k)),line) for line in lines]
        p.write_text('\n'.join(lines)+'\n','utf8')
    try:
        with (OUT/'client.log').open('w',encoding='utf8') as log:
            result=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(prepared)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        proof=json.loads((target/'r43_travel_review.json').read_text())
        proof['client_exit_code']=result.returncode
        (OUT/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(proof,ensure_ascii=False,indent=2),flush=True)
        assert proof['passed'] and result.returncode==0
    finally:
        for p,content in backups.items():p.write_bytes(content)

if __name__=='__main__':main()
