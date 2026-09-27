"""Bounded native input review; restore the owner's shader preference afterwards."""
from pathlib import Path
import argparse,json,time,subprocess,sys
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r42'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rig',type=int,choices=range(5),default=1)
    ap.add_argument('--case',choices=['locomotion','stance','rifle','basic','duel','awakening'],default='locomotion')
    ap.add_argument('--shaders',action='store_true');args=ap.parse_args();guard()
    label=f'{args.case}_{args.rig}_{"shader" if args.shaders else "clear"}'
    dest=OUT/'native'/label/time.strftime('%Y%m%d_%H%M%S');dest.mkdir(parents=True,exist_ok=False)
    spec=json.loads((ROOT/'.Codex/client-r42-motion-1.json').read_text('utf8'))
    remove=('-Dprojectseele.combatVariant=','-Dprojectseele.r42Locomotion=','-Dprojectseele.r41StanceContacts=')
    spec['command']=[x for x in spec['command'] if not x.startswith(remove)]
    spec['command'][1:1]=[f'-Dprojectseele.combatVariant={args.rig}']
    if args.case in ('locomotion','stance','rifle'):spec['command'][1:1]=['-Dprojectseele.r41StanceContacts=true','-Dprojectseele.r41PoseOnly=true']
    if args.case=='rifle':spec['command'][1:1]=['-Dprojectseele.r41PoseWeapon=4','-Dprojectseele.r41HandCamera=true']
    if args.case=='locomotion':spec['command'][1:1]=['-Dprojectseele.r42Locomotion=true']
    if args.case=='duel':spec['command'][1:1]=['-Dprojectseele.combatExchange=true']
    if args.case=='awakening':
        spec['command'][1:1]=['-Dprojectseele.combatAwakening=true','-Dprojectseele.combatExchange=true','-Dprojectseele.r42OpticsReview=true']
        spec['command']=[x for x in spec['command'] if not x.startswith('-Dprojectseele.combatSideView=')]
        candidate=OUT/'first_battle/first_battle_r42.json'
        if candidate.exists():spec['command'][1:1]=[f'-Dprojectseele.firstBattleReviewClip={candidate}']
    launch=ROOT/f'.Codex/client-r42-{label}.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';original=cfg.read_bytes();(dest/'original_oculus.properties').write_bytes(original)
    text=original.decode('utf8');text=text.replace('enableShaders=true','enableShaders=false') if not args.shaders else text.replace('enableShaders=false','enableShaders=true')
    began=time.time();cfg.write_text(text,'utf8')
    try:
        with (dest/'native.log').open('w',encoding='utf8') as log:
            result=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0,('Client failed',result.returncode)
        report=max((ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob('r31_combat_*.json'),key=lambda p:p.stat().st_mtime)
        assert report.stat().st_mtime>=began,'No fresh native result'
        data=json.loads(report.read_text());(dest/'result.json').write_bytes(report.read_bytes())
        (OUT/'native'/('latest_'+label+'.json')).write_text(json.dumps(dict(result=str(dest/'result.json'),media=data.get('media'),passed=data.get('passed')),indent=2),'utf8')
        print(json.dumps({k:data.get(k) for k in ('passed','error','media','cases')},ensure_ascii=False),flush=True)
        if 'stance_r41' in data:print({k:v for k,v in data['stance_r41'].items() if k not in ('events','poses','contact_cases')},flush=True)
        if not data.get('passed'):raise RuntimeError('Native review did not pass; inspect '+str(dest/'result.json'))
    finally:
        cfg.write_bytes(original)


if __name__=='__main__':main()
