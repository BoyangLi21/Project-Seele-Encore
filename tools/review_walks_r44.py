"""Measured whole-width physics with the existing native FakePlayer solver.

This does not certify client packet state, human input, art or vehicle boarding.
Those have independent lifecycle suites; do not merge their coverage labels.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time
from freeze_native_r44 import freeze
from launch_rendered_client_r17 import java_environment
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('cases',type=Path);p.add_argument('--name',required=True)
    p.add_argument('--tv-cage',action='store_true');p.add_argument('--crane-girder',action='store_true');p.add_argument('--legacy-lease-control',action='store_true');p.add_argument('--timeout',type=int,default=900)
    p.add_argument('--tv-personnel',action='store_true')
    p.add_argument('--plant-conditions',type=Path)
    args=p.parse_args();guard();assert args.name.replace('_','').replace('-','').isalnum()
    cases=json.loads(args.cases.read_text('utf8'));assert cases and len({c['id'] for c in cases})==len(cases)
    out=ART/'native_walks'/args.name/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    shutil.copy2(args.cases,out/'cases.json');shutil.copy2(args.cases,WORLD/'r44_walk_cases.json')
    spec=json.loads((ART.parent/'repair_r43/moving_devices/native_dry_route/launch.json').read_text('utf8'))
    cmd=[s for s in spec['command'] if not s.startswith(('-Dprojectseele.','-Xmx','-Xms'))]
    cmd[1:1]=['-Xms512M','-Xmx4G','-Dprojectseele.regionalBuild=r44-collision']
    if WORLD.name=='SEELE_FIELD_R45_REVIEW':cmd[1:1]=['-Dprojectseele.nativeReviewWorld=SEELE_FIELD_R45_REVIEW']
    if args.tv_cage:cmd[1:1]=['-Dprojectseele.r44TvCageReview=true']
    if args.tv_personnel:
        assert args.tv_cage and (WORLD/'r44_tv_personnel_platforms.json').is_file()
        cmd[1:1]=['-Dprojectseele.r44TvPersonnelPlatformsReview=true']
    if args.crane_girder:cmd[1:1]=['-Dprojectseele.r44CraneGirderShapeExport=true']
    if args.legacy_lease_control:cmd[1:1]=['-Dprojectseele.r44AuditLeaseLegacyControl=true']
    if args.plant_conditions:
        query=out/'plant_conditions_input.json';shutil.copy2(args.plant_conditions,query)
        cmd[1:1]=['-Dprojectseele.r44PlantConditionsInput='+query.resolve().as_posix(),
                  '-Dprojectseele.r44PlantConditionsOutput='+(out/'plant_conditions.json').resolve().as_posix()]
    cmd[cmd.index('--world')+1]=WORLD.name;spec['command']=cmd;spec=freeze(spec,out)
    (out/'launch.json').write_text(json.dumps(spec),'utf8')
    argfile=out/'launch.args';argfile.write_text('\n'.join('"'+s.replace('\\','\\\\').replace('"','\\"')+'"' for s in cmd[1:]),'utf8')
    env=java_environment()[1];env.update(spec['environment']);began=time.time()
    with (out/'native.log').open('w',encoding='utf8') as log:
        process=subprocess.Popen([cmd[0],'@'+str(argfile.resolve())],cwd=spec['workingDirectory'],env=env,
            stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        try:code=process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.stdin.write('stop\n');process.stdin.flush()
            try:process.wait(timeout=60)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=15)
            raise
    result=WORLD/'quality_native_walk_results.json';assert result.stat().st_mtime>=began
    if args.plant_conditions:
        observed=out/'plant_conditions.json';assert observed.is_file() and observed.stat().st_mtime>=began,'No fresh requested server plant observations'
    rows=json.loads(result.read_text('utf8'));shutil.copy2(result,out/'result.json')
    if args.crane_girder:
        witness=WORLD/'r44_crane_girder_shapes.json'
        assert witness.is_file() and witness.stat().st_mtime>=began,'Missing fresh native girder collision/outline states'
        shutil.copy2(witness,out/witness.name)
    passed=code==0 and len(rows)==len(cases) and {r['id'] for r in rows}=={r['id'] for r in cases} and all(r['status']=='pass' for r in rows)
    (out/'scope.json').write_text(json.dumps(dict(passed=passed,code=code,cases=len(cases),
        input_sha256=hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(),tv_cage_collision=args.tv_cage,legacy_lease_negative_control=args.legacy_lease_control,
        method='Native FakePlayer.move and vanilla collision/support solver on measured paths',
        actual_client_input=False,client_server_state=False,artistic_acceptance=False,full_device_lifecycle=False),indent=2),'utf8')
    print('Native physics paths',len(rows),'passed',passed,out,flush=True)
    assert passed,[(r['id'],r['status'],r.get('actual')) for r in rows if r['status']!='pass']

if __name__=='__main__':main()
