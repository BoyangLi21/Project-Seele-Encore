"""Fresh frozen-owner clone, actual transport and resolved client sound witness."""
from pathlib import Path
import argparse,json,subprocess,sys,time,shutil
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/repair_r43/airlift_fresh'
WORLD=ROOT/'run/saves/SEELE_R43_AIR_REVIEW'

def main():
    global OUT,WORLD
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);args=p.parse_args()
    if args.attempt>1:
        OUT=OUT/('attempt_'+str(args.attempt));WORLD=WORLD.with_name('SEELE_R43_AIR_REVIEW_V'+str(args.attempt))
        guard();assert not WORLD.exists() and not OUT.exists(),'Never overwrite a completed or interrupted review'
        OUT.mkdir(parents=True);shutil.copytree(ROOT/'artifacts/repair_r43/source_world_backup',WORLD)
        (WORLD/'session.lock').write_bytes(bytes([0xe2,0x98,0x83]))
        spec=json.loads((ROOT/'artifacts/repair_r43/airlift_fresh/launch.json').read_text('utf8'))
        spec['command']=[x for x in spec['command'] if not x.startswith(('-Dprojectseele.airReviewWorld=','-Dprojectseele.reviewArtifactRoot='))]
        spec['command'][1:1]=['-Dprojectseele.airReviewWorld='+WORLD.name,'-Dprojectseele.reviewArtifactRoot='+OUT.resolve().as_posix()]
        spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=WORLD.name
        (OUT/'launch.json').write_text(json.dumps(spec),'utf8')
    guard();assert WORLD.is_dir() and not WORLD.is_symlink()
    config=ROOT/'run/config/oculus.properties';original=config.read_bytes()
    (OUT/'original_oculus.properties').write_bytes(original);began=time.time()
    try:
        config.write_text(original.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
        with (OUT/'native.log').open('w',encoding='utf8') as log:
            run=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(OUT/'launch.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report=WORLD/'r32_airlift_review.json'
        assert report.is_file() and report.stat().st_mtime>=began,'Missing fresh transport result'
        (OUT/'result.json').write_bytes(report.read_bytes());data=json.loads(report.read_text('utf8'))
        print(json.dumps(dict(exit=run.returncode,passed=data.get('passed'),error=data.get('error'),audio=(OUT/'resolved_landing_sounds.json').exists()),ensure_ascii=False),flush=True)
        assert run.returncode==0 and data.get('passed'),'Native airlift failed; preserve all evidence'
        assert (OUT/'resolved_landing_sounds.json').stat().st_mtime>=began,'No fresh client audio witness'
    finally:config.write_bytes(original)

if __name__=='__main__':main()
