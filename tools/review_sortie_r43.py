"""Real mission-gate and three-unit sortie workflow on fresh private R42 copies."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'


def main(before=False,attempt=1):
    guard();label='before' if before else 'after';out=ART/'sortie'/label/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    name=('SEELE_R43_GATE_BEFORE' if before else 'SEELE_R43_MECHANICS_REVIEW')+(f'_V{attempt}' if attempt>1 else '');world=ROOT/'run/saves'/name
    assert not world.exists(),'Preserve the previous mechanical run; inspect it before preparing another copy'
    shutil.copytree(ART/'source_world_backup',world)
    spec=json.loads((ROOT/'.Codex/client-r42-lifts.json').read_text('utf8'))
    spec['command']=[s for s in spec['command'] if not s.startswith(('-Dprojectseele.regionalBuild=','-Dprojectseele.r40LiftStart=','-Dprojectseele.r40LiftEnd='))]
    spec['command'][1:1]=['-Dprojectseele.regionalBuild=r43-sortie',f'-Dprojectseele.r43ReviewWorld={name}']+(['-Dprojectseele.r43GateBefore=true'] if before else [])
    index=spec['command'].index('--quickPlaySingleplayer');spec['command'][index+1]=name
    if before:
        overlay=out/'classes';shutil.copytree(ART/'baseline_classes_r42',overlay)
        for name in ['com/projectseele/visual/SortieR32Review','com/projectseele/visual/AutoSortieGateR43','com/projectseele/client/visual/SortieR32Client']:
            source=ROOT/'build/classes/java/main'/name
            for p in source.parent.glob(source.name+'*.class'):
                dest=overlay/p.relative_to(ROOT/'build/classes/java/main');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        old=str(ROOT/'build/classes/java/main');forms=[old,old.replace('\\','/'),old.replace('\\','\\\\')]
        def replace(text):
            for s in forms:text=text.replace(s,overlay.resolve().as_posix())
            return text
        spec['command']=[replace(s) for s in spec['command']];spec['environment']={k:replace(v) for k,v in spec['environment'].items()}
        saved=out/'minecraftClasspath.txt';saved.write_text(replace((ROOT/'build/classpath/runClient_minecraftClasspath.txt').read_text('utf8')),'utf8')
        spec['command']=[f'-DlegacyClassPath.file={saved.resolve().as_posix()}' if s.startswith('-DlegacyClassPath.file=') else s for s in spec['command']]
    launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8');began=time.time()
    cfg=ROOT/'run/config/oculus.properties';original=cfg.read_bytes();cfg.write_text(original.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        file=max((world/'Review').glob('r32_sortie_*.json'),key=lambda p:p.stat().st_mtime);assert file.stat().st_mtime>=began
        proof=json.loads(file.read_text('utf8'));(out/'result.json').write_bytes(file.read_bytes())
        if before:assert not proof['pass'] and 'no_task_does_not_queue_or_prepare' in proof.get('failure',''),proof.get('failure')
        else:assert proof['pass'],proof.get('failure')
        record=dict(before=before,result=str(out/'result.json'),world=str(world),passed=proof['pass'],failure=proof.get('failure'))
        (ART/'sortie'/('latest_'+label+'.json')).write_text(json.dumps(record,indent=2),'utf8');print(record,flush=True)
    finally:cfg.write_bytes(original)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--before',action='store_true');p.add_argument('--attempt',type=int,default=1);args=p.parse_args();main(args.before,args.attempt)
