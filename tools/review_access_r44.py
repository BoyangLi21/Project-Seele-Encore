"""Actual reader, held clearance card, exit button and physical threshold traversal."""
from pathlib import Path
import datetime,json,shutil,subprocess,sys,time
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/access/native'

def main():
    guard();OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'result.json').exists():
        old=OUT/('attempt_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));old.mkdir()
        for name in ('client.log','result.json'):
            if (OUT/name).exists():shutil.copy2(OUT/name,old/name)
    result_file=WORLD/'r44_access_review.json'
    if result_file.exists():
        shutil.copy2(result_file,OUT/('result_before_'+str(time.time_ns())+'.json'))
        result_file.unlink()
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command.insert(1,'-Dprojectseele.r44AccessReview=true')
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name
    spec['command']=command
    spec=freeze(spec,OUT)
    prepared=OUT/'launch.json';prepared.write_text(json.dumps(spec),'utf8')
    settings=[ROOT/'run/options.txt',ROOT/'run/config/oculus.properties']
    backups={p:p.read_bytes() for p in settings if p.exists()}
    for p,content in backups.items():
        lines=content.decode('utf8').splitlines()
        changes={'renderDistance:':'renderDistance:6','simulationDistance:':'simulationDistance:5','pauseOnLostFocus:':'pauseOnLostFocus:false','enableShaders=':'enableShaders=false'}
        p.write_text('\n'.join(next((v for k,v in changes.items() if s.startswith(k)),s) for s in lines)+'\n','utf8')
    try:
        began=time.time()
        with (OUT/'client.log').open('w',encoding='utf8') as log:
            result=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(prepared)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=480)
        assert result_file.stat().st_mtime>=began
        proof=json.loads(result_file.read_text('utf8'));proof['client_exit_code']=result.returncode
        (OUT/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(proof,ensure_ascii=False,indent=2),flush=True)
        assert proof['passed'] and result.returncode==0
    finally:
        for p,content in backups.items():p.write_bytes(content)

if __name__=='__main__':main()
