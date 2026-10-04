"""Prepare/run Root's existing-structure native jobs; default never launches MC.

Root passes --execute-root after compiling and installing the exact topology.
This uses the actual city and original cargo owners, never a remote shadow body.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('control',type=Path);parser.add_argument('quality',type=Path)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--execute-root',action='store_true');parser.add_argument('--timeout',type=int,default=1800);args=parser.parse_args()
    control=args.control.resolve();quality=args.quality.resolve();c=json.loads(control.read_text());q=json.loads(quality.read_text());out=args.out.resolve()
    assert c['world']==q['world']and c['world_id']==q['world_id']and c['actual_existing_structures']and not c['helper_replacement']
    assert Path(c['world']).resolve()==(ROOT/'run/saves/SEELE_FIELD_R45_REVIEW').resolve();assert not out.exists();out.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-launch-r17.json').read_text());cmd=[s for s in spec['command']if not s.startswith('-Dprojectseele.')]
    props={'regionalBuild':'r44-facility-photos','nativeReviewWorld':'SEELE_FIELD_R45_REVIEW',
        'r45CityCreateDistrict':control.as_posix(),'r45CityRigidQuality':quality.as_posix(),'photoCaptureHoldTicks':'24000',
        'bodyPoseReview':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps/eva_body_r43.json').as_posix(),
        'gameplayReviewDirectory':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps').as_posix()}
    cmd[1:1]=['-Dprojectseele.'+k+'='+v for k,v in props.items()];cmd[cmd.index('--quickPlaySingleplayer')+1]='SEELE_FIELD_R45_REVIEW';spec['command']=cmd
    required=[ROOT/'build/classes/java/main/com/projectseele/world'/f'{name}.class'for name in('CityCreateDistrictR45','CityRigidQualityR45','CityRigidGenerationR45')]
    receipt=dict(world_written=False,mc_launched=False,build_invoked=False,no_surrogate_replacement=True,
        control_sha256=hashlib.sha256(control.read_bytes()).hexdigest(),quality_sha256=hashlib.sha256(quality.read_bytes()).hexdigest(),
        required_classes=[dict(path=str(p),exists=p.exists(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()if p.exists()else None)for p in required])
    (out/'prepared_receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');(out/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
    if not args.execute_root:
        print('Prepared only; compile/check current epoch, install Root-verified topology, then launch explicit Root run.');print(out/'launch.json');return
    guard();assert all(p.exists()for p in required),'Compile the new quality observer first'
    spec=freeze(spec,out);(out/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
    with(out/'native.log').open('w',encoding='utf8')as log:
        result=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(out/'launch.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
    target=Path(q['output']);marker=target/('checkpoint.json'if q['mode']=='interrupt'else'complete.json')
    assert result.returncode == 0 and marker.exists() and not(target/'failed.json').exists(),'Preserve actual first native failure; inspect native.log and quality report'
    report=json.loads(marker.read_text());assert report['passed']and not report['helper_replacement']and report['actual_existing_city_objects']==96
    print('Root native job passed its software/cargo scope:',marker,'; visual/two-client acceptance is separate')


if __name__=='__main__':main()
