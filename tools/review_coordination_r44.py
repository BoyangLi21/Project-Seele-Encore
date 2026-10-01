"""Two actual JVM runs: physical delegated test, save, cold reload and dossier completion."""
from pathlib import Path
import argparse,datetime,json,shutil,subprocess,sys,time
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/city_coordination/native'

def run(reload):
    guard();folder=OUT/('reload' if reload else 'prepare')/datetime.datetime.now().strftime('%Y%m%d_%H%M%S');folder.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.r44CoordinationReview=true']+(['-Dprojectseele.r44CoordinationReload=true'] if reload else [])
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command;spec=freeze(spec,folder);prepared=folder/'launch.json';prepared.write_text(json.dumps(spec),'utf8')
    filename='r44_coordination_reload.json' if reload else 'r44_coordination_review.json';path=WORLD/filename
    if path.exists():shutil.copy2(path,folder/'previous.json');path.unlink()
    settings={p:p.read_bytes() for p in (ROOT/'run/options.txt',ROOT/'run/config/oculus.properties') if p.exists()}
    for p,content in settings.items():
        lines=content.decode('utf8').splitlines();rules={'renderDistance:':'renderDistance:6','simulationDistance:':'simulationDistance:5','pauseOnLostFocus:':'pauseOnLostFocus:false','enableShaders=':'enableShaders=false'}
        p.write_text('\n'.join(next((v for k,v in rules.items() if line.startswith(k)),line) for line in lines)+'\n','utf8')
    try:
        began=time.time()
        with (folder/'client.log').open('w',encoding='utf8') as stream:
            result=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(prepared)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=1200)
        assert path.stat().st_mtime>=began
        proof=json.loads(path.read_text('utf8'));proof['client_exit_code']=result.returncode
        (folder/'result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');print('Dossier phase:',folder,proof['passed'],flush=True)
        assert proof['passed'] and result.returncode==0,proof
    finally:
        for p,content in settings.items():p.write_bytes(content)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reload-only',action='store_true');args=parser.parse_args()
    if not args.reload_only:run(False)
    run(True)
