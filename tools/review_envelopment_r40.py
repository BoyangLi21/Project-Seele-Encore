"""Natural 50 HP awakening into the paired finale; all private inputs restored."""
from pathlib import Path
import json,sys,time,subprocess,hashlib,argparse,re
from launch_rendered_client_r17 import java_environment
from record_combat_pcm_r34 import capture

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/world_combat_r40/envelopment_native'


def main(label='envelopment_native'):
    global OUT
    assert re.fullmatch(r'[a-z0-9_]+',label);OUT=ROOT/'artifacts/world_combat_r40'/label
    guard=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^javaw?\\.exe$' }).Count"],capture_output=True,text=True,check=True)
    assert int(guard.stdout.strip())==0,'Another Minecraft/build JVM is running'
    OUT.mkdir(parents=True,exist_ok=True);candidate=OUT.parent/'envelopment_arap'
    audit=json.loads((candidate/'actual_mesh_audit.json').read_text());assert audit['worst']['deepest']==0
    local=ROOT/'run/projectseele-local-maps';saved={}
    for name in ['first_battle_r24.json','sachiel_wrap_r14.bin']:
        p=local/name;saved[p]=p.read_bytes() if p.exists() else None
        if p.exists():(OUT/('baseline_'+name)).write_bytes(saved[p])
    spec=json.loads((ROOT/'.Codex/client-r40-contact-side.json').read_text('utf8'))
    spec['command']=[v for v in spec['command'] if not v.startswith(('-Dprojectseele.combatNormals','-Dprojectseele.combatSideView'))]
    spec['command'][1:1]=['-Dprojectseele.combatAwakening=true','-Dprojectseele.combatExchange=true','-Dprojectseele.surfaceAuditR40=true']
    launch=ROOT/'.Codex/client-r40-envelopment.json';launch.write_text(json.dumps(spec))
    log=OUT/'native.log';start=time.time()
    try:
        for p in saved:p.write_bytes((candidate/p.name).read_bytes())
        with log.open('w',encoding='utf8') as stream,capture(OUT/'audio.wav',log):
            process=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,env=java_environment()[1],stdout=stream,stderr=subprocess.STDOUT)
            assert process.returncode==0,process.returncode
        reports=list((ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob('r31_combat_*.json'))
        report=max(reports,key=lambda p:p.stat().st_mtime);assert report.stat().st_mtime>=start
        data=json.loads(report.read_text());(OUT/'result.json').write_bytes(report.read_bytes())
        (OUT/'run.json').write_text(json.dumps(dict(start=start,end=time.time(),media=data['media'],audio=str(OUT/'audio.wav'),
            movie_sha256=hashlib.sha256((candidate/'first_battle_r24.json').read_bytes()).hexdigest(),surface_sha256=hashlib.sha256((candidate/'sachiel_wrap_r14.bin').read_bytes()).hexdigest()),indent=2))
        print(json.dumps(dict(passed=data['passed'],error=data['error'],cases=data['cases'],media=data['media'])),flush=True)
    finally:
        for p,original in saved.items():
            if original is None:p.unlink(missing_ok=True)
            else:p.write_bytes(original)
        assert all((not p.exists()) if raw is None else p.read_bytes()==raw for p,raw in saved.items())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--label',default='envelopment_native');main(p.parse_args().label)
