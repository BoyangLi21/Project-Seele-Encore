"""Prepare or (root only) launch real-client native public gate lifecycle cases."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,time
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
CASES=ART/'facility_transit_r44/public_station_gates_v2/native_cases.json'


def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=160)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--out',type=Path)
    p.add_argument('--cases',type=Path,default=CASES);args=p.parse_args()
    assert 0<=args.start<args.end<=160
    data=json.loads(args.cases.read_text(encoding='utf8'));assert len(data)==160
    out=args.out or ART/'public_gate_client_lifecycle'/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(args.cases,out/'native_cases.json')
    spec=json.loads((ROOT/'.Codex/client-r42-lifts.json').read_text(encoding='utf8'))
    prefixes=('-Dprojectseele.regionalBuild=','-Dprojectseele.r40Lift','-Dprojectseele.r41Lift','-Dprojectseele.r44Lift',
        '-Dprojectseele.r43Lift','-Dprojectseele.r44PublicGate','-Dprojectseele.liftFrameFile=')
    spec['command']=[v for v in spec['command'] if not v.startswith(prefixes)]
    spec['command'][1:1]=['-Dprojectseele.regionalBuild=r44-public-gate-client',
        '-Dprojectseele.r44PublicGateReview=true',f'-Dprojectseele.r44PublicGateStart={args.start}',
        f'-Dprojectseele.r44PublicGateEnd={args.end}',
        '-Dprojectseele.r44PublicGateCases='+(out/'native_cases.json').resolve().as_posix()]
    spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=WORLD.name
    spec=freeze(spec,out);launch=out/'launch.json';launch.write_text(json.dumps(spec),encoding='utf8')
    scope={'start':args.start,'end':args.end,'expected_current_cases':args.end-args.start,'denominator':160,
        'actual_case_source':str(args.cases.resolve()),'case_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        'actual_player':'Integrated real client; keyUp movement and ordinary MTR entityInside/scheduled tick only',
        'no_test_switch_calls':True,'hold':'Actual closed-minus-open leaf volume, real stationary body>=50ticks and producer held counter proof',
        'score_read':'All existing mtr_ objectives plus native balance/entry-zone absence, existing player scores; no creating getters',
        'restore':'Original inventory, health, mode, flying, dimension/position/yaw/pitch and original vehicle if present',
        'scope_limits':['Cold restart','Other clients/server','Actual native boarding/APG/whole501 routes','Whole-station artistic acceptance']}
    (out/'scope.json').write_text(json.dumps(scope,indent=2),encoding='utf8')
    print('Prepared real client native gate range:',args.start,args.end,'launch',launch,flush=True)
    if args.prepare_only:return
    guard();config=ROOT/'run/config/oculus.properties';old=config.read_bytes();began=time.time()
    config.write_text(old.decode('utf8').replace('enableShaders=true','enableShaders=false'),encoding='utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        result=WORLD/'r44_public_gate_client_review.json';assert result.stat().st_mtime>=began
        report=json.loads(result.read_text(encoding='utf8'));shutil.copy2(result,out/'result.json')
        assert not report['error'],report['error'];assert len(report['cases'])==args.end-args.start
        assert all(r.get('actual_client_keys_auto_open') and r.get('actual_native_scheduled_refused_close')
            and r.get('actual_client_keys_walked_out') and r.get('actual_unoccupied_native_closed')
            and r.get('all_mtr_objectives_and_player_scores_unchanged') for r in report['cases'])
        print('Actual client gate range passed:',args.start,args.end,out,flush=True)
    finally:config.write_bytes(old)


if __name__=='__main__':main()
