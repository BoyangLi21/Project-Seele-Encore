"""Same native optic lifecycle against frozen R42 logic and the R43 candidate."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'


def main(before=False,tempo=False,rig=1):
    guard();assert tempo or rig==1
    label=('before' if before else 'after')+(f'_{rig}' if rig!=1 else '');kind='tempo' if tempo else 'optics';out=ART/kind/label/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-r42-motion-1.json').read_text('utf8'))
    prefixes=('-Dprojectseele.r42Locomotion=','-Dprojectseele.r41StanceContacts=','-Dprojectseele.r41PoseOnly=','-Dprojectseele.combatAwakening=','-Dprojectseele.combatVariant=')
    spec['command']=[x for x in spec['command'] if not x.startswith(prefixes)]
    spec['command'][1:1]=[f'-Dprojectseele.combatVariant={rig}',f'-Dprojectseele.reviewArtifactRoot={ART.resolve().as_posix()}/native_media']
    spec['command'][1:1]=['-Dprojectseele.r43Tempo=true'] if tempo else ['-Dprojectseele.r43OpticsStates=true','-Dprojectseele.r42OpticsReview=true']
    overlay=None
    if before:
        overlay=out/'classes';shutil.copytree(ART/'baseline_classes_r42',overlay)
        hooks=['com/projectseele/visual/CombatR31Review','com/projectseele/visual/TempoR43Review','com/projectseele/client/visual/CombatR31Client',
               'com/projectseele/client/visual/OpticsR43Review','com/projectseele/client/render/LocalTriangleMeshLayer']
        for name in hooks:
            source=ROOT/'build/classes/java/main'/name
            for p in source.parent.glob(source.name+'*.class'):
                target=overlay/p.relative_to(ROOT/'build/classes/java/main');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        old=str(ROOT/'build/classes/java/main');forms=[old,old.replace('\\','/'),old.replace('\\','\\\\')]
        def replace(text):
            for s in forms:text=text.replace(s,overlay.resolve().as_posix())
            return text
        spec['command']=[replace(s) for s in spec['command']];spec['environment']={k:replace(v) for k,v in spec['environment'].items()}
        cp=ROOT/'build/classpath/runClient_minecraftClasspath.txt';saved=out/'minecraftClasspath.txt';saved.write_text(replace(cp.read_text('utf8')),'utf8')
        spec['command']=[f'-DlegacyClassPath.file={saved.resolve().as_posix()}' if s.startswith('-DlegacyClassPath.file=') else s for s in spec['command']]
        for name in ('EvaEyeMaterialsR42','EvaUnit01Renderer'):
            rel=Path('com/projectseele/client/render')/(name+'.class')
            assert (overlay/rel).read_bytes()==(ART/'baseline_classes_r42'/rel).read_bytes()
    launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();began=time.time()
    cfg.write_text(previous.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        reports=list((ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob('r31_combat_*.json'));latest=max(reports,key=lambda p:p.stat().st_mtime)
        assert latest.stat().st_mtime>=began;result=json.loads(latest.read_text('utf8'));assert not result['error'],result['error']
        media=(ROOT/'run'/result['media']).resolve();proof=dict(passed=result['passed'],samples=result['cases']) if tempo else json.loads((media/'optics_r43.json').read_text('utf8'))
        assert len(proof['samples'])==(6 if tempo else 4),proof
        if before and not tempo:assert not proof['passed'],'Baseline must actually reproduce the wrong material'
        else:assert proof['passed'],proof
        record=dict(before=before,media=str(media),proof=proof,production_classes='Frozen R42 with observation hooks only' if before else 'R43 candidate',run=str(out))
        (out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
        (ART/kind/('latest_'+label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(record,ensure_ascii=False),flush=True)
    finally:cfg.write_bytes(previous)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--before',action='store_true');p.add_argument('--tempo',action='store_true');p.add_argument('--rig',type=int,choices=range(5),default=1);args=p.parse_args();main(args.before,args.tempo,args.rig)
